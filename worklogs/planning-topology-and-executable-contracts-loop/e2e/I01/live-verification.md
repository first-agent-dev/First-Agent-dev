# I01 live verification — final I03 acceptance package

**Status: PLANNED — every case is `NOT RUN`.** This sheet is part of the project-scoped
final I03 acceptance package. The operator requires live-host E2E for every change in I01–I03;
these I01-origin cases make the I01 part visible without changing the frozen I02/I03 baseline.
They are plans, not evidence that a host run happened.

**Source scope:** all 42 declared CTs in
`worklogs/planning-topology-and-executable-contracts-loop/increments/increment-01-plan-grammar-and-extractor.md`,
plus the I01-relevant deferred obligations D1a, D1b, D2, D3, D4, D5 and D8. D6 is owned by I04;
D7 records historical E19 baseline-guard disposition and is not an I01 production change.
Producer-to-case lineage is frozen in `producer-baseline.json` and mapped in `producer-coverage.json`.
The existing I02-origin/I03 baseline remains unchanged.

**Fixture/review sequence:** no fixtures or helpers are assigned yet. STEP7 independent review
must approve these case oracles before STEP8 implements any helper/fixture. Live runs remain
blocked until I01–I03 are merged to `main` and deployed. Record provider mode (`REAL` or
`CONTROLLED`) and use only approved disposable workspaces. Do not capture credentials or full
secret-bearing prompts.

## I01-LIVE-01 — real authoring chain reaches the parser and verification gate

| Field | Value |
| --- | --- |
| Case ID | `I01-LIVE-01` |
| Kind | surface / authoring-chain join |
| Increment origin | I01 |
| CTs | CT14, CT21, CT21b, CT22, CT23, CT24, CT31, CT32, CT40, CT41, CT42, CT43 |
| Deferred obligations | D1b, D3, D5 |
| Producers | schema §4; both planning `SKILL.md` files; `feature-planning/INJECT.md`; planner plan section in `src/fa/inner_loop/prompt.py`; the actual skill→prompt→provider→plan→parser path |
| Local proof | `tests/test_plan_grammar_live_chain.py`, `tests/test_planner_emits_schema4.py`, `tests/test_skill_grammar_emit.py`, `tests/test_skill_conformance.py` (local proof only; not live acceptance) |
| Expected live observation | On the approved deployed host, exercise both selectable planning skills through their actual production selection/injection paths and the real provider. At the provider boundary, verify the schema grammar blocks and selected full skill skeleton are present without recording secrets. Preserve the model-authored plan artifact; assert it is not a fixture, parses to non-empty slices with `TESTS:` and `STEPS:`, retains the required Grounding/Evidence/Assumptions/Risks content, and passes the production admission check. Observe the real workflow run the declared verification command and persist the corresponding slice/report outcome. Record `REAL` provider mode and the selected skill for each run. |
| Negative control | In a reviewed controlled-provider companion run, suppress one grammar block/skeleton producer and demonstrate that the payload/oracle detects its absence or that the resulting invalid plan is refused before coder dispatch. The control is not a live PASS. |
| Fixture / run sheet | Not assigned; STEP8 only after independent STEP7 review. Run sheet anchor: `#i01-live-01`. |
| Live result | NOT RUN |
| Commentary | |

#### Attempts — I01-LIVE-01

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## I01-LIVE-02 — parser records and accessors drive persisted workflow behavior

| Field | Value |
| --- | --- |
| Case ID | `I01-LIVE-02` |
| Kind | surface |
| Increment origin | I01 |
| CTs | CT1, CT2, CT3, CT4, CT4b, CT4c, CT5, CT6, CT7, CT11, CT12, CT13, CT16, CT17, CT18, CT19, CT20, CT33 |
| Deferred obligations | D1a, D4, D8 |
| Producers | `extract_plan_ids`, `SliceRecord`, section/command/test-path/contract accessors, `_slice_spans`, contract block/entry parsing, command ownership, both `.slices` workflow-controller readers, and the exported plan API documented in schema §7 |
| Local proof | `tests/test_plan_ids.py`, `tests/test_slice_id_validation.py`, `tests/test_skill_grammar_emit.py` (local proof only; not live acceptance) |
| Expected live observation | On the deployed image, run a user-authored, canonical multi-slice plan through the ordinary installed workflow/controller path. Include lettered slice IDs, a `CONSTRAINT` contract with rationale and continuation, scoped `TESTS:` paths, `STEPS:` modes, dependencies, and verification fences inside/outside slice spans. Assert the persisted report and actual command outputs correspond to the right slices, with no cross-slice commands or phantom tests. A read-only host probe of the installed parser may supplement this observable workflow result to check exact record spans, classes, accessor outputs, and the exported API; it is not the sole oracle. The current increment and schema example remain parseable under the deployed installed version. |
| Negative control | Use a retired `S#` heading and a `verify` fence outside any slice. The old heading must not be guessed as a slice, and the unowned command must not be attributed to a slice or reported as executed. |
| Fixture / run sheet | Not assigned; STEP8 only after independent STEP7 review. Run sheet anchor: `#i01-live-02`. |
| Live result | NOT RUN |
| Commentary | |

#### Attempts — I01-LIVE-02

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## I01-LIVE-03 — precheck diagnostics fail closed before coder dispatch

| Field | Value |
| --- | --- |
| Case ID | `I01-LIVE-03` |
| Kind | surface / admission join |
| Increment origin | I01 |
| CTs | CT8, CT9, CT10, CT25, CT26, CT27, CT34, CT35, CT36, CT37, CT38, CT39 |
| Deferred obligations | D2 |
| Producers | `precheck` and its 12 named rules: `slice-without-tests`, `step-without-exit`, `deps-undefined-slice`, `deps-cycle`, `heading-near-miss`, `contract-reference-undeclared`, `contract-declared-twice`, `contract-declaration-lost`, `step-marker-unknown`, `step-near-miss`, `slice-count-at-ceiling`, and `orphaned-slice-field`; production admission caller and bounded repair path |
| Local proof | `tests/test_plan_precheck.py`, `tests/test_verify_gate_live.py` (local ordered proof only; not deployed evidence) |
| Expected live observation | On the approved host, submit one controlled invalid-plan variant for each named diagnostic through the public workflow/admission path. Assert the persisted diagnostics identify the rule and source line; a determinate failure receives only the bounded repair allowed by Q57; no coder dispatch occurs while any FAIL or indeterminate admission remains. A repaired plan reaches coder only after a fresh clean revalidation. At exactly seven slices, record the specified WARN and do not turn it into a blocking FAIL. Capture no raw credentials or prompt secrets. |
| Negative control | In a reviewed disposable mutation build, remove the production admission→`precheck` call; a known-bad plan must then reach the coder or make the named oracle fail. Restore byte-identical source after the sensitivity check. This kill check is not a deployed-host result. |
| Fixture / run sheet | Not assigned; STEP8 only after independent STEP7 review. Run sheet anchor: `#i01-live-03`. |
| Live result | NOT RUN |
| Commentary | |

#### Attempts — I01-LIVE-03

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
