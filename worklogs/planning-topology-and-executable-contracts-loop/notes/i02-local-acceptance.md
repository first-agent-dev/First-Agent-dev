# I02 local acceptance record — PENDING DIFF REVIEW / NOT ACCEPTED

2026-10-16, current closeout scope E223. I02 remains IN PROGRESS. Local proof exists, but the
plan-versus-diff review has not been started by this documentation update. No SHIPPED,
deployed-host, OS-isolation or I03 completion claim. Q69–Q72 remain resolved.

## E223 — operator-approved local closeout and final I03 acceptance ownership

I02 retains implementation of its local contracts, local C1/C2/C3/producer-sensitivity checks,
honest result records and plan-versus-diff review. Resolve review findings and refresh affected
local proof before closing I02. Intentional replacement-test meaning is reviewed here; a newly
introduced I02 defect cannot be hidden as deferred inherited infrastructure.

**Moved explicitly to final I03 SLICE6, all INCOMPLETE:** deployed functional/source-to-behaviour
verification; environment/readiness and inherited baseline acceptance review; broad independent
implementation/evidence review; integrated E2E and deployment signoff. Exact successors are in
[migration bank §9](i02-to-i03-scope-migration-2026-10-15.md#9-e223-closeout-acceptance-transfer--2026-10-16),
[I03 plan](../increments/increment-03-execution-workspace-foundation.md) and
[I03 spec §9](i03-execution-workspace-spec-2026-10-15.md#9-final-deployed-acceptance--q63).

This ratified transfer supersedes E220–E222's broader I02 closeout requirements; it is not an
acceptance result, blanket baseline PASS or permission to weaken checks. The old E222 correction
identified Gitleaks' indirect Go hook-build dependency correctly, but still retained per-case
operator/broad-review gates now transferred to I03. No Go provisioning or deployed test is an
I02 local shipping prerequisite. Keep actual red/unknown outcomes below for final I03 review.
Historical ledger entries and original compressed proof artifacts are not rewritten.

**Next action is paused:** push this documentation change, then wait for the operator's next
command before any plan-versus-diff review or code tweak. The local record is not finalized.

## Version, durable evidence and scope

Proof snapshot: `c4cb55fe4d0a63a4ac43c62acacdac54b9404bad` on
`arena/86633f17-first-agent-dev`; production checkpoint `0f7814d10faada80453adcadb0444567bb46f2d4`.
Isolated executable comparison baseline: `d9109f489c84cb7f1ab3568b609d96e5b2b61ae2`,
with exact Git HEAD/index restored, frozen dependencies and no tracked source changes.
This record and its register/checkbox reconciliation are later documentation-only changes.

[Evidence inventory](evidence/i02-e220/manifest.json) records original-byte and compressed-byte
SHA256s. Lossless gzip archives retain full original JUnit reports, native nodeid manifests,
run IDs, commands, mutation results, input hashes, terminal logs and audit runner history.
For example, `gzip -dc` an archive into a scratch directory, verify its uncompressed SHA256
against the inventory, then inspect the XML/JSON. Archives are evidence, not new runtime code
or a turnkey public gate. Do not rerun the archived fixed-output-path audit scripts verbatim.
The whole-repository baseline's historical plugin has nodeids but **no native UUID binding**;
it is usable for failure comparison, not silently upgraded to a current gate proof.

## Completed ordered local proof

Unmutated union of all seven declared path sets plus D3/D5/D8 tests: **877 passed,
0 skipped/errors**, 143.74s.
Original run ID `0c930883c4f94f54af55b13b29725ecd`, completion epoch `1792134034.499576`.
The v3 continuation verified the original XML/run ID, exact 877-nodeid manifest and identical
frozen inputs before launching its first mutation. It reused that actual completed baseline;
it did not relabel it as a new run. All 43 following invocations started after completion.

**40 retained FUNCTIONAL + CT79 CONSTRAINT + 2 supplemental: all PROVEN.** Every run used
its complete declared test paths, a unique native JUnit UUID and successful actual overlay
import probe. Exact manifests matched, with executed assertion failures and no skips/errors.
SLICE6's 16 normative and 2 supplemental runs each executed all **487** public cases,
without `-k` subsets or a preassigned contract-to-test map. CT61 resolved one target/two call
edits; all other declared directives resolved one target/one edit. Script-root CT83 used the
production script overlay/bootstrap/provenance protocol. Tracked Python inputs, plan/schema
hashes and Git status were unchanged at final audit exit0, before this documentation edit.

| Mutation | Scope / class | Passed / failed | Seconds |
| :--- | :--- | ---: | ---: |
| CT44 | SLICE1 / FUNCTIONAL | 4 / 32 | 2.77 |
| CT45 | SLICE1 / FUNCTIONAL | 33 / 3 | 4.42 |
| CT48 | SLICE1 / FUNCTIONAL | 34 / 2 | 4.84 |
| CT49c | SLICE1 / FUNCTIONAL | 33 / 3 | 4.75 |
| CT49d | SLICE1 / FUNCTIONAL | 32 / 4 | 17.24 |
| CT49e | SLICE1 / FUNCTIONAL | 33 / 3 | 4.42 |
| CT50 | SLICE2 / FUNCTIONAL | 27 / 9 | 2.37 |
| CT50b | SLICE2 / FUNCTIONAL | 32 / 4 | 2.18 |
| CT51 | SLICE2 / FUNCTIONAL | 31 / 5 | 1.89 |
| CT52 | SLICE2 / FUNCTIONAL | 14 / 22 | 1.73 |
| CT78 | SLICE2b / FUNCTIONAL | 31 / 94 | 5.95 |
| CT79 | SLICE2b / CONSTRAINT | 108 / 17 | 3.08 |
| CT55 | SLICE3 / FUNCTIONAL | 4 / 23 | 2.44 |
| CT56 | SLICE3 / FUNCTIONAL | 17 / 10 | 2.34 |
| CT57 | SLICE3 / FUNCTIONAL | 4 / 23 | 3.04 |
| CT81 | SLICE3 / FUNCTIONAL | 9 / 18 | 2.48 |
| CT60 | SLICE4 / FUNCTIONAL | 17 / 27 | 4.08 |
| CT61 | SLICE4 / FUNCTIONAL | 40 / 4 | 7.68 |
| CT62 | SLICE4 / FUNCTIONAL | 32 / 12 | 3.07 |
| CT65 | SLICE5 / FUNCTIONAL | 105 / 10 | 60.76 |
| CT66 | SLICE5 / FUNCTIONAL | 110 / 5 | 60.53 |
| CT67 | SLICE5 / FUNCTIONAL | 113 / 2 | 64.84 |
| CT68 | SLICE5 / FUNCTIONAL | 113 / 2 | 64.97 |
| CT82 | SLICE5 / FUNCTIONAL | 81 / 34 | 9.78 |
| CT83 | SLICE5 / FUNCTIONAL | 114 / 1 | 30.38 |
| CT71 | SLICE6 / FUNCTIONAL | 453 / 34 | 184.49 |
| CT72 | SLICE6 / FUNCTIONAL | 474 / 13 | 246.22 |
| CT73 | SLICE6 / FUNCTIONAL | 416 / 71 | 49.60 |
| CT75 | SLICE6 / FUNCTIONAL | 425 / 62 | 44.80 |
| CT76 | SLICE6 / FUNCTIONAL | 479 / 8 | 169.40 |
| CT77 | SLICE6 / FUNCTIONAL | 456 / 31 | 231.89 |
| CT77b | SLICE6 / FUNCTIONAL | 473 / 14 | 239.28 |
| CT77c | SLICE6 / FUNCTIONAL | 479 / 8 | 236.05 |
| CT86 | SLICE6 / FUNCTIONAL | 455 / 32 | 36.00 |
| CT87 | SLICE6 / FUNCTIONAL | 416 / 71 | 34.66 |
| CT90 | SLICE6 / FUNCTIONAL | 485 / 2 | 228.87 |
| CT91 | SLICE6 / FUNCTIONAL | 415 / 72 | 35.78 |
| CT92 | SLICE6 / FUNCTIONAL | 421 / 66 | 153.20 |
| CT93 | SLICE6 / FUNCTIONAL | 465 / 22 | 191.57 |
| CT94 | SLICE6 / FUNCTIONAL | 474 / 13 | 193.71 |
| CT95 | SLICE6 / FUNCTIONAL | 479 / 8 | 199.38 |
| SUP-CONTEXT | SLICE6 / SUPPLEMENTAL | 484 / 3 | 145.52 |
| SUP-GUARD | SLICE6 / SUPPLEMENTAL | 485 / 2 | 196.07 |

Sum of overlapping measured mutation durations: **3188.53s**,
four workers after the baseline (not a wall-clock measurement). Q53(c) limitation remains:
a complete-path failure proves sensitivity to the declared producer mutation, not unique
semantic attribution to that contract. No per-contract selected-nodeid oracle is introduced.
The D3/D5/D8 supplemental controls from E219 are also retained in the evidence directory.

### Rejected/diagnostic history, not closure proof

- First external baseline accidentally used gate-owned recursion environment:876pass1skip,
  rejected before any mutation. No skip or recursion-marker policy was changed.
- v2 completed the valid877 baseline, then23 valid earlier producer reports, but its external
  harness incorrectly required exactly one edit (CT61 legitimately has two), and omitted
  script-root overlay setup for CT83. That attempt was not a completed audit. v3 corrected
  only the external runner and reran **all43**, preserving the original baseline identity.
- E218's699 baseline/18 mutations overlapped; those results remain diagnostic for STEP17.
  E212/earlier486-case results remain older-version evidence. None substitutes for this audit.

## Actual final repository gates

Actual `just check` invoked actual `just test` and exited **1**. Test terminal summary:
**5033 passed,1 failed,12 skipped,1 xfailed;5047 total;570.71s;83.18% coverage**.
Native UUID-bound candidate report and complete baseline/candidate identity/outcome comparison
are archived under `repository/`; every failure is call-phase, not a collection/setup error.

| Blocking subgate | Actual result |
| :--- | :--- |
| lock-check | PASS |
| lint: Ruff/format/deptry/Pylint-gap | PASS;901 formatted files |
| configured Mypy strict | PASS;450 source files |
| configured Pyrefly | PASS; not a whole-project warning-free claim |
| authoring-check | PASS |
| dependency/producer-consumer/log-kind/no-mock-dataclass contracts | PASS |
| shell syntax | PASS |
| test + coverage + CLI-floor recipe | FAIL at test; coverage itself met80% |
| CLI-floor independently after failed test | PASS;27 floors,78 scanned functions |

Advisory Vulture ran; it is not a blocking substitute. Twelve unchanged skips are missing
shellcheck; one unchanged Q19 xfail records absent OS containment, still an I03 obligation.
No new skip/xfail was added to turn a failure green.

## Exact baseline comparison — inherited inputs for final I03 acceptance review

Baseline4477:4455pass9fail12skip1xfail,872.47s,82.21% coverage. Candidate5047 above:
**0 candidate-only failures,1 common failure,8 baseline-only failures,6 superseded old
nodeids,576 new nodeids**. Missing identities are not passes; their replacements follow.
Full identities, messages and phase are retained in the comparison JSON, not inferred from totals.
E223 moves formal acceptance dispositions for this inherited inventory to I03 SLICE6 STEP10.
Local diff review still checks the intent/coverage of I02 test changes; no new I02 regression is
excused by this transfer, and the observed baseline/candidate results are not relabeled PASS.

Common failure: `tests/test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication`
(call-phase in both). Actual readiness returns75, `precommit_prewarm_failed`. No Go SDK is
installed; pre-commit's Go bootstrap hits blocked `go.dev` and fails SSL/URLError. Pinned
[Gitleaks v8.30.1 go.mod](https://github.com/gitleaks/gitleaks/blob/v8.30.1/go.mod) specifies
**Go1.24.11** (checked via GitHub API). That is an indirect hook-build dependency,
not a new FA language/runtime/deployment requirement. A trusted SDK plus reachable/cached
build dependencies is one possible way to repair this inherited test environment, **not an
unconditional I02 prerequisite**. E223 assigns its environment/packaging and formal inherited
baseline acceptance disposition to I03 SLICE6 STEP10; no passing disposition is inferred here.
Preserve actual rc1, the hook/test and foreign208-byte Arena commit-msg hook.
No I02 deployed-host test or I03 implementation is introduced by this diagnosis.

Eight baseline-only failures, individually proposed dispositions:

1. `test_deploy_scripts.py::test_historical_workspace_docs_have_top_level_superseded_banner`:
   candidate PASS; exact banner-fixture path migration approved by Q72. Assertion retained.
2. `test_doc_links.py::test_repo_has_no_broken_internal_file_links`: candidate PASS;
   exactly46 link targets/15 archived files approved Q72; assertion retained; E19 untouched.
3. `test_s10a_cli_coverage.py::test_s10a_authoring_check_runs_on_a_real_workspace`:
   candidate PASS after actual export/private-type/claim-guard repair; no path exemption.
4. `test_workflow_deadline.py::test_generous_deadline_runs_the_full_pipeline`: candidate PASS;
   explicit-plan fixture migration preserves successful valid-admission route.
5. `test_workflow_deadline.py::test_no_deadline_runs_the_full_pipeline`: same preserved route,
   candidate PASS, not omission of the no-deadline case.
6. `test_workflow_no_eval_terminal.py::test_eval_requested_but_no_verdict_fails[linear]`:
   candidate PASS; Q55-required eval and silent-judgment failure preserved.
7. `test_workflow_no_eval_terminal.py::test_planner_coder_without_eval_is_also_unjudged`:
   old identity replaced under Q55; no absent case counted as passing (mapping below).
8. `test_workflow_no_eval_terminal.py::test_scratch_pipeline_succeeds_but_is_marked_unjudged`:
   old identity replaced with noncoder-only planning under Q55/CT95 (mapping below).

Six old-ID dispositions (all replacements actually PASS):

| Old identity (file prefix as above) | Actual replacement / retained intent |
| :--- | :--- |
| `test_plan_reference.py::test_absent_plan_degrades_silently` | `test_absent_coder_plan_is_blocked_before_dispatch`; deliberate CT95 rejection before provider, not silent fallback |
| `test_workflow_no_eval_terminal.py::test_planner_coder_without_eval_is_also_unjudged` | `test_omitted_eval_is_inserted_and_silent_judgment_fails[roles0]` and `[roles1]`; Q55 eval insertion and unsuccessful silent judgment, including coder-only and planner/coder routes |
| `test_workflow_no_eval_terminal.py::test_scratch_pipeline_succeeds_but_is_marked_unjudged` | `test_noncoder_planning_succeeds_but_is_marked_unjudged`; legitimate no-coder/no-eval path retained |
| `test_plan_grammar_live_chain.py::test_the_live_payload_carries_the_planning_skill` | same base name `[plan-authoring]` and `[feature-planning]`; cold behavior retained, warm added |
| `test_plan_grammar_live_chain.py::test_the_skeleton_the_model_is_shown_is_the_text_the_parser_accepts` | same two skill parameters; exact displayed/on-disk identity retained |
| `test_plan_grammar_live_chain.py::test_the_taught_skeleton_yields_slices_carrying_verify_commands` | same two skill parameters; actual parser command extraction retained |

The unchanged CLI ergonomics per-role override case passes in both Python3.13 runs; no
source repair or forced-red obligation is inferred from its older Python-dependent failure.

Eight recorded baseline Mypy diagnostics also have individual, non-waiver dispositions:
`plan_ids.py:877` set inference → explicit `set[int]`; skill-grammar `:70` Any return →
JSON-object narrowing; runner `:88`,`:89`,`:321` contradictory enum identity diagnostics →
membership negatives preserving assertions; runner `:150` empty-result inference → explicit
`tuple[CommandResult,...]`; mutation-overlay `:145` private shutil reexport → direct stdlib
import; mutation-overlay `:556` enum negative → membership assertion. Exact eight original
diagnostics and final actual configured450-file clean result are archived. No ignores or
blanket baseline waiver added. Broader/direct invocation diagnostics remain separate historical
contexts, not falsely described as the configured gate result.

The older E194 record counted9 diagnostics/5 files, including `test_inject_condensates.py`.
The exact isolated d910 run reproduces8/4, not that ninth case; the original ninth diagnostic
message is not available in this evidence bundle. That file is unchanged against d910 and
clean in the current configured gate. **Historical ninth identity/context reconciliation remains
for final I03 baseline acceptance review**, not an invented source fix, pass, or waiver. E174 reporter failure likewise was
not repaired here: both final complete runs produced normal terminal summaries without it.

Separate source-root readiness observation remains `hook_seat_collision` rc75 because Arena's
foreign commit-msg hook is not FA-managed. It is preserved, not resolved by supplying Go or
by the clean-candidate integration fixture. No source-root ready claim or hook-replacement
authorization is inferred; any required compatible deployed seating is an I03 environment/
readiness review item, not a requirement to replace Arena's hook before local I02 closeout.

## Closure checklist and handoff — retained local I02

- [x] Completed unmutated baseline before all43 current producer runs; STEP17 and amended CT66.
- [x] D1/D2/D3/D4-local-readers/D5/D8 reconciled with named source, tests and actual controls.
- [x] Actual just wrappers and exact identity/phase comparison retained, not successful wrappers.
- [ ] Complete plan-versus-diff review against retained I02 plan/d910, including intended local
  logic, meaningful tests/replacement intent, Q45-B/parser compatibility and unintended changes.
- [ ] Fix review findings and refresh affected local checks/proofs; no new I02 defects deferred.
- [ ] Finalize this local record with review outcome/findings/resolution and local closeout status.
  No broad independent review, inherited-baseline acceptance or deployment signoff required here.

## Transferred acceptance checklist — INCOMPLETE under final I03 SLICE6

- [ ] Deployed functional/source-to-behaviour verification — STEP9/10 and deployed-functional DoD.
- [ ] Environment/readiness and inherited baseline acceptance review — STEP10 and environment/
  release-gate DoD; includes this record's exact baseline/changed-ID/Mypy/hook observations.
- [ ] Broad independent I02+I03 implementation/evidence review — STEP7 before fixtures/helpers,
  STEP10 and final broad-review DoD; repeat/finalize after material changes.
- [ ] Integrated E2E/deployment signoff — CT88/CT89, STEP10 and final acceptance record.

No source/case/evidence is deleted by transfer, and no red/unknown outcome becomes PASS. Q72
still approves only its exact46 link fixes/15files and one banner path migration; E19 stays intact.
I03 acquisition, mandatory all-project execution boundary, PTY descendants/publication/recovery
and former SLICE7 deployment/host package remain **undelivered**. Local I02 SHIPPED, once earned,
will mean implemented and diff-reviewed, not deployment-validated. Broad assurance and final
operator deployment signoff belong to I03. **Wait for the next command before starting review.**

### Documentation-only follow-up verification

After the frozen audit exited, records/STEP17 were reconciled and lossless evidence archived;
no production/test source changed. Correct post-edit checks:156passed (doc links, parser,
skill grammar, kill directives);13passed77deselected (deployment claim/ownership guards);
309Markdown files have no broken internal links; diff whitespace clean. Two preceding
mistyped test-file invocations exited4 with no tests and are rejected, not counted green.


## E221 — closure reassessment, 2026-10-16

Historical reassessment: mandatory-Go/environment-stop and broad-review/per-case I02 closure
conclusions are superseded by E223 above; actual hash/collection/test results remain unchanged.
The closing paragraph below records the old assessment, not current closeout requirements.

Starting commit `4b78084214de2d01f83bb522f8b4ce69cce975eb`, clean tree and matching remote.
Read-only validation recomputed compressed/original SHA256s for all81 archived artifacts,
reparsed the877-case baseline,43 mutation reports and5047-case candidate with their actual
native UUIDs, and checked ordering and exact mutation manifests. All runtime/test Python
hashes still match the proof snapshot. The only changed watched input is the E220 plan's
status/evidence text; all seven contract/path/command/kill-directive signatures are identical.
These are validations of existing runs, **not new executions or new report identities**.

All11 distinct SLICE6 STEP exit selectors were freshly collected (normal environment,
`python -m pytest ... --collect-only`). In STEP order, deduplicating STEP5/6/7's same command:
`verify_plan`:2; `coder_stage or baseline`:2; `reconciliation`:1;
`role_loops or repair or indeterminate`:66; `real_workflow`:1;
`candidate or admission_artifact`:179; `admission or precheck`:197;
`linear_admission or adaptive_admission or role_order or direct_budget`:63;
`plan_preflight or direct_api_plan_guard or plan_help or acquisition_unavailable`:100;
`baseline or t0 or repeated_configured_coders or eval_replan`:45;
`ct91_public or acquisition_unavailable or plan_ref_mismatch`:50.
Every collected nodeid is in the actual completed877-pass baseline. Collection was nonempty
and rc0 for each command; this is not a claim that selected groups were freshly executed.

Fresh regression command:
`uv run --frozen --no-sync pytest tests/test_plan_ids.py tests/test_plan_reference.py tests/test_slice_id_validation.py -q`
→ **115passed1.95s**, rc0. The actual `git diff d9109f4 c4cb55f -- src/fa/inner_loop/plan_ids.py`
contains only `inside = set()` → `inside: set[int] = set()`. No extractor/source-position
behavioral change is inferred from that annotation; independent Q45-B review remains required.

No new implementation gap was identified by these bounded checks. Go is still absent from
the configured executable PATH; the foreign208-byte commit-msg hook remains intact. Do not
repeat the known bootstrap failure or manufacture green readiness. Need a provisioned trusted
Go>=1.24.11/build-dependency environment, then execute the real readiness integration and
final gates. Operator dispositions (including the unreproduced historical ninth context and
separate source-root hook-seat collision), independent review and DoD signoff still remain.
No checklist or overall status is upgraded by this reassessment; I02 remains **NOT ACCEPTED**.
