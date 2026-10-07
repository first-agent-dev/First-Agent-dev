# Deferred verification register — what I01 promises that nothing yet proves live

Status: living list. Owner: planner. Created 2026-10-07 (operator decision: collect the
targets now, write the tests later, distributed across increments; no e2e/live run before
I02 closes).

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
- **Proven today.** Statically, by CT11/CT31 over fixture text.
- **Not proven.** That a plan produced by the *real* loop reaches that line at all.
- **The original defect was exactly this.** An unparseable plan made the gate no-op
  **silently** (ledger E-entry at `ledger.md:181`: "Live defect, not archival"). A static
  test cannot distinguish "the gate passed" from "the gate did nothing".
- **Test to write.** Boot `drive_session` (mock only `ProviderChain.request`), have the
  mocked provider return a plan written to the skill skeleton, assert the coverage gate
  observed a non-empty slice set. **Kill-check:** deleting the `extract_plan_ids` call at
  `workflow_controller.py:332` must fail it.

## D2 — `precheck` is implemented but wired to nothing  ·  owner: **I03**

- **Promise.** 11 rules (`slice-without-tests`, `step-without-exit`, `deps-undefined-slice`,
  `deps-cycle`, `heading-near-miss`, `contract-reference-undeclared`,
  `contract-declared-twice`, `contract-declaration-lost`, `step-marker-unknown`,
  `step-near-miss`, `slice-count-at-ceiling`, `orphaned-slice-field`).
- **Measured 2026-10-07.** `precheck` has **zero call sites outside `plan_ids.py` and the
  test suite.** Its consumer is named — schema §7:388, "I01 SLICE3 + the I03 admission
  step" — so SD-B is satisfied, but nothing executes it in production.
- **Risk.** A lint nobody runs is decoration. Every rule here is currently unfalsifiable in
  the live system.
- **Test to write (I03).** The admission step refuses to start a coder run on a plan with a
  FAIL diagnostic, through the real loop. **Kill-check:** deleting the `precheck` call in
  the admission step must let a known-bad corpus plan through.

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

## D4 — The read API has no production reader  ·  owner: **I02** (most), **I03** (`section`)

`commands_for(slice)`, `commands_for(None)`, `section`, `contract_class`, `tests_for`,
`SliceRecord.tests_note`, `SliceRecord.test_paths`, `plan_commands`. Each carries a named
consumer in schema §7, none has a call site outside tests. Live proof arrives with the
consumer; until then each is a typed promise. **Do not add more accessors** (SD-B).

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

## D7 — Guards that must stay red  ·  owner: every increment

Three gates are expected-red by design (E19) and must **never** be "fixed":
`test_doc_links::test_repo_has_no_broken_internal_file_links` (46 broken links at
2026-10-07), `test_deploy_scripts::…superseded_banner`,
`test_cli_ergonomics::test_workflow_per_role_overrides_parse`. A green one is the
regression.

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
