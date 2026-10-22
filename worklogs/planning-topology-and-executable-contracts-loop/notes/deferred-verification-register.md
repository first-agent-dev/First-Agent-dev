# Deferred verification register — what I01 promises that nothing yet proves live

Status: living list. Owner: planner. Created 2026-10-07 (operator decision: collect the
targets now, write the tests later, distributed across increments; no e2e/live run before
I02 closes).

**Owner migration, 2026-10-15 (E201):** I02 retains direct local gate/admission proofs; final
deployed I02+I03 acceptance belongs to foundation I03. Old I03 coder-brief/tracker readers follow
the named deferred slice-loop/tracker/L2-eval successor. Historical evidence/ticks below are not
re-run or closed by this owner edit; no live verdict is assigned.

**E223 closeout scope:** local D1/D2/D3/D4a/D5/D8 proof remains I02 evidence; before moving on,
only the plan-versus-diff review of retained implementation/test intent is required. Deployed
verification, environment/readiness/inherited baseline acceptance (including D7 inventory), broad
independent implementation/evidence review and integrated deployment signoff are incomplete final
I03 SLICE6 obligations per [migration bank §9](i02-to-i03-scope-migration-2026-10-15.md#9-e223-closeout-acceptance-transfer--2026-10-16).
No historical result or deferred successor is upgraded; D4b/D6 ownership is unchanged. This
planning change does not start/complete the diff review or turn any inherited failure green.

**E229 current local state:** I02 is locally implemented and diff-reviewed, pending E2E as I03
ships. Five failure-path findings were fixed; Q73 was explicitly ratified. The final local record
contains current1002-case baseline/affected proof refresh and actual red wrapper/comparison.
D4b/D6 and all four final I03 acceptance obligations remain incomplete; no new live verdict.

## Current local reconciliation — E220, 2026-10-16

**I02 local rows D1/D2/D3/D4a/D5/D8 are reconciled with executed evidence below.**
This is not operator acceptance or an I03/live-host verdict. See [local closeout/evidence record](i02-local-acceptance.md).

- **D1a:** the original persisted adjusted-report C1 case passes in the actual final suite;
  its E145 kill remains historical. Current verifier/eval producers also have fresh full-path
  sensitivity. No claim that its historical kill was rerun separately.
- **D1b/D3 — CLOSED local C1:** `test_plan_grammar_live_chain.py` now has8passing cases,
  including both `[plan-authoring]` cold and `[feature-planning]` warm routes through shipped
  provider factory/real chain/drive_session; only `ProviderChain.request` mocked. Displayed
  skeleton identity and actual parser extraction are asserted. E219 removed the real skill
  reader:6fail2pass, no setup errors/skips. Fresh ordered877 baseline and final repository
  suite include all8. This proves the prompt/grammar seam, **not actual hosted-model output**;
  historical “model actually wrote” wording below must not be read as a live-model claim.
- **D2 — CLOSED local caller/kill:** `_validate_plan_admission` calls actual `precheck` before
  coder. Fresh ordered CT91 full487-path:415pass72fail,35.78s, PROVEN, native UUID/provenance,
  no errors/skips, original source bytes unchanged. Refusal/repair/WARN cases named below
  remain present; the former ordering blocker is now discharged, not waived.
- **D4a — CLOSED local readers / D4b — OPEN successor compatibility:** schema §7 now states
  the actual partition. `commands_for(None)`/plan_commands feed `verify_plan`; direct
  `SliceRecord.commands`, `.test_paths`, `.section`, `.contract_class` feed verifier,
  baseline/controller and kill validation. Actual C1/baseline/runner/ownership cases execute
  in the877 baseline and relevant full-path kills. `commands_for(slice)`, `section(slice)`,
  `tests_for(slice)` wrappers are preserved compatibility surfaces, not invented live callers.
  `tests_note`/CT10b and steps_mode-driven coder brief remain explicit incomplete slice-loop
  successor work, not foundation I03 completion and not a dummy I02 reader. No new accessor.
- **D5 — CLOSED local C1:** `test_planner_emits_schema4.py`12pass includes real shipped
  provider factory/registry/drive_session and request-boundary assertions for both actual
  planner prompt blocks. E219 blanked actual planner role prompt:1fail11pass after real
  provider invocation; no errors/skips. Static constant tests alone are not counted live.
- **D8 — CLOSED metadata guard:** `test_skill_grammar_emit.py`23pass includes export→schema7
  named-consumer guard over the actual11 exports. E219 unknown export:1fail22pass, no errors/
  skips; no extra production API or unapproved general verification-debt policy introduced.

The measured historical entries below retain their provenance; present-tense “test to write”
and “zero callers” descriptions are superseded only by this named local evidence. D4b/D6 and
I03 deployed-host obligations stay open. The optional executable-register policy remains
**unratified/unbuilt**.

**Why this exists.** I01 ships a parser, a pre-check engine, and two prompt blocks. Almost
all of it is proven by *static* tests over fixture text. Under SD-C (E93) static conformance
is necessary and **never sufficient**: it proves a string, not a behaviour. I01 deliberately
ships no live-path test (E103). The risk that creates is not that I01 is wrong — it is that
the deferral is **forgotten**. This register is the anti-forgetting device: every promised
behaviour is listed with the increment that owns its live proof.

Rule for using it: **an increment may not be marked DONE while it owns an unticked row
here.** Adding a feature to I01's surface means adding a row.

---

## D1 — The coverage gate actually sees slices  ·  owner: **I02**  ·  priority: HIGHEST

- **Promise.** A planner-written plan yields a non-empty `.slices`, so the coverage gate at
  `src/fa/inner_loop/workflow_controller.py:332` stops silently no-opping.
- **The original defect was exactly this.** An unparseable plan made the gate no-op
  **silently** (ledger E-entry at `ledger.md:181`: "Live defect, not archival"). A static
  test cannot distinguish "the gate passed" from "the gate did nothing".

**Corrected 2026-10-08 (E145): this row conflated two claims. The first is already closed.**

### D1a — the gate runs, and observes slices, in a real workflow · **CLOSED**

Closed by code already in the tree, not by new work. `tests/test_slice_id_validation.py:199`
`test_live_workflow_persists_the_adjusted_report` boots the real `run_workflow` with a real
`plan_path`, and asserts on the **persisted** `eval_report.json` — the same file the repair
loop and the operator read. The invented `SLICE404` is absent from disk and
`unreported_slices == ["SLICE5", "SLICE5a"]`, neither of which can happen unless
`extract_plan_ids(plan_text).slices` returned a non-empty set at `workflow_controller.py:332`.

**Kill-check executed, not asserted:** replacing that line with `declared = ()` turns the file
red — `6 failed, 7 passed`, including the live test — and restores byte-identical. This is
precisely the kill-check this row demanded. D1a therefore needs no test from I02.

### D1b — a plan the **model actually wrote** parses · owner: **I02** · **CLOSED 2026-10-08 (E147)**

Closed by `tests/test_plan_grammar_live_chain.py` (C1, 5 oracles): boots the real
`drive_session` with only `ProviderChain.request` mocked, arms expansion level 2 with a `src/`
read, and captures the bytes that actually crossed the boundary. The skeleton on the wire is
byte-for-byte the skeleton on disk, and that skeleton parses to `SLICE1` carrying
`('uv run pytest tests/test_<area>.py -q',)`. **Kill-check PROVEN:** removing the
`read_skill_for_injection` call in `coder_loop.py`'s L2 block reddens 3 of the 5, restored
byte-identical.

**Measured, and deliberately not asserted:** the payload itself does **not** parse, because the
skill body crosses the wire JSON-escaped (`\n` literals, `\u00a7` for §), so no `## SLICE`
heading sits at a line start. That is correct — the parser's input is the markdown plan the
model *writes*, never the prompt it reads. A test asserting the payload parses would have been
asserting a falsehood; the real risk was drift, so the oracle is identity.

*Original statement of the row, retained:*

What remains is the half the original row buried: everything above feeds the parser a
*fixture*. No test shows that a plan produced by following the injected skill skeleton yields
a non-empty slice set. That is the chain in **D3**, and it is the live precondition of the
whole verify gate: SLICE6 reads a slice's commands from the plan, so if a model-authored plan
does not parse into slices carrying `verify` fences, the gate silently does nothing — the
original defect one storey up. **Close D1b before SLICE5/SLICE6, not after.**

## D2 — production `precheck` admission caller · **CLOSED local ordered proof (E220)**


**Historical E218 observation, superseded by the E220 reconciliation above:** `_validate_plan_admission` now calls the real `precheck` before
public coder dispatch. `tests/test_verify_gate_live.py::test_ct91_public_repair_retries_latest_draft_then_promotes`,
`::test_ct91_public_block_never_reaches_t0_coder_eval`,
`::test_ct91_public_structural_zero_slice_near_miss_is_repairable` and
`::test_ct91_public_warn_alone_admits_without_planner_credit` cover real-session refusal/repair
and WARN behavior. Fresh CT91 removal of that production call:415passed72failed, exact487-case
public bank,47.98s, PROVEN/provenance/UUID/no skips/errors;22 source/test hashes unchanged.
See E218. The caller and kill effect are observed, but the audit was launched concurrently with its
baseline. Final closure waits for STEP17’s ordered serial rerun; no local DoD/I03 acceptance.
The earlier measurements and requested proof below are historical.

- **Promise.** 12 rules (`slice-without-tests`, `step-without-exit`, `deps-undefined-slice`,
  `deps-cycle`, `heading-near-miss`, `contract-reference-undeclared`,
  `contract-declared-twice`, `contract-declaration-lost`, `step-marker-unknown`,
  `step-near-miss`, `slice-count-at-ceiling`, `orphaned-slice-field`), as listed by
  `plan_ids.precheck` (`src/fa/inner_loop/plan_ids.py:1257-1271`).
- **Measured 2026-10-07; source rechecked 2026-10-14.** `precheck` still has **zero production
  call sites outside `plan_ids.py` and the test suite.** SLICE6 CT91 and STEPs 9/10/12 plan I02
  as the consumer, but that is a plan only; there is no runtime wiring and D2 is not closed.
  The historical schema §7 consumer statement named I03; the I02 plan now reconciles it explicitly.
- **Risk.** A lint nobody runs is decoration. Every rule here remains unfalsifiable in production.
- **Test to write (I02 SLICE6).** The admission step refuses coder dispatch on a determinate
  `precheck` FAIL through the real workflow and invokes bounded repair per Q57. **Kill-check:**
  deleting the production `precheck` call must let a known-bad corpus plan reach coder or make the
  named C1 oracle fail. Keep WARN advisory; reduced I02 now has seven actual sections,
  so the former local eight-slice exception is no longer needed. Do not invent a ceiling FAIL.
  Leave D2 OPEN until this code/test proof passes.

## D3 — The skill → prompt → plan → parser chain  ·  owner: **I02** (gate), register now

- **Measured chain, all four links verified by source read 2026-10-07:**
  1. `src/fa/inner_loop/expansion.py:136` `select_l2_skill` picks `feature-planning` (warm)
     or `plan-authoring` (cold);
  2. `src/fa/inner_loop/coder_loop.py:895` calls `read_skill_for_injection(skill_name, …)`
     with the **default `file_name="SKILL.md"`** — i.e. the *full* skill body, skeleton
     included — inside `_drive_session_inner` (the live path under `drive_session`);
  3. the model writes a plan following that skeleton;
  4. `extract_plan_ids` parses it; the gate at `workflow_controller.py:332` reads it.
- **Why it matters.** This is the loop CT14 claims to close. Link 2 is live *today*; links
  3–4 are only ever exercised on fixture text.
- **Note the asymmetry.** The coder-stage ceremony at `coder_loop.py:247` injects
  `INJECT.md`, not `SKILL.md`, and `plan-authoring/` **has no `INJECT.md`** (only
  `feature-planning/` does). Any test that assumes one injection path will be wrong.
- **Test to write.** Assert the injected block for both skills contains the skeleton, and
  that the skeleton text the model is shown is the same text CT14 conforms against.

## D4 — Read-API consumers · owner: **I02** gate readers, **deferred slice-loop successor** coder brief

Current split is D4a (actual local readers, closed) / D4b (compatibility and deferred
coder-brief consumers, incomplete), as enumerated in the E220 reconciliation above and schema
§7. The old “none has a call site” description is no longer true. Preserve wrappers and
strict semantics; do not manufacture consumers or add accessors (SD-B).

## D5 — The two prompt blocks (SLICE1c)  ·  owner: **I02**

`src/fa/inner_loop/prompt.py` carries the plan-grammar blocks. Verified today by string
assertions. Not proven: that the composed prompt actually reaching the provider contains
them. **Test to write.** Capture the payload at the mocked `ProviderChain.request` boundary
and assert the grammar block is present — a real live-path assertion that needs no network.

## D6 — `canonical_slice_id`'s deliberate leniency  ·  owner: **I04** (eval)

`workflow_controller.py:336` still normalises legacy `S<n>` at the eval-report boundary
(E106 — one namespace there, so no ambiguity). Pinned statically by
`tests/test_slice_id_validation.py::test_legacy_s_ids_normalise_to_canonical_space`. Live
proof belongs with the eval consumer in I04.

## D7 — Protected baseline guards · operator disposition Q72 (2026-10-16)

Historical E19 required the doc-link and historical-banner failures to remain red. The agent
initially over-scoped their repair in E215; E216 records that error and blocking stop. The
operator then explicitly selected **“Approve these E19 repairs”** in Q72: exactly46 relative-
link target corrections in15 archived files and one banner-fixture path migration. E19’s
required-red rule is superseded **only for these two repaired causes**. Both real integrity
checks and their assertions remain active; new broken links/missing historical banners must
still fail. No skip, failure-count waiver or acceptance is implied.

`test_cli_ergonomics::test_workflow_per_role_overrides_parse` was also listed in the older trio.
It is unchanged; Python-version-dependent green is an observation, not a source fix or a
forced-failure requirement. Record its actual final baseline/candidate outcome separately.

## D8 — The exported surface can drift away from schema §7  ·  owner: **I02**

- **Found by I01's DoD walk, 2026-10-07.** `parse_slice_id` was in `plan_ids.__all__` and
  absent from the schema document entirely; `canonical_slice_id` was absent from §7. Both
  are now documented, but nothing *prevents* the next export from drifting the same way.
- **Test to write (I02).** Assert `plan_ids.__all__` is a subset of the names specified in
  `notes/artifact-schema-and-grammar.md` §7, and that each carries a `consumer:`
  annotation. **Kill-check:** adding a name to `__all__` without a §7 entry must fail it.
- **Why not now.** I01 is complete; attaching a new contract to a closed increment is the
  drift this project exists to prevent. I02 is the surface's next consumer.

---

## Proposal — make this register executable (needs a decision)

A markdown list rots: someone adds an accessor and forgets the row. The cheap production
pattern is a **verification-debt guard** — one test that reads this file, extracts the row
ids (`D#`) and their owning increments, and cross-checks them against the live surface:
every name in `plan_ids.__all__` with no production call site must appear in some row. Then
adding an unwired feature fails the build until it is either wired or registered.

Cost: one small test, one parser for this file's headings. Benefit: the deferral can no
longer be silent — which is the exact failure mode D1 exists to prevent, applied to the
register itself. **Not built**: it is a new policy choice and would need its own `CT#`.
