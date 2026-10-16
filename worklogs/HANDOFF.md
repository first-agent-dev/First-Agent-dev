# HANDOFF.md — next agent/session

> Read [`knowledge/llms.txt`](../knowledge/llms.txt) §MUST READ FIRST.
> Current local delivery is distinct from final I03/deployed acceptance.

## Current state — I02 LOCAL SHIPPED / I03 IMPLEMENTATION IN PROGRESS, 2026-10-16 / E235

Branch `arena/86633f17-first-agent-dev` only. Retained I02 runtime/test proof snapshot
`a32a72fc58db4b9a5b048a9b6475649bcf3e32b4`. E230/E231 finalized planning; E232 adds the first
I03 source/test chunk described below. Retained I02 implementations/evidence remain unchanged.
I02 is **locally implemented and diff-reviewed, pending E2E tests as I03 ships**.
Read the [final local record](planning-topology-and-executable-contracts-loop/notes/i02-local-acceptance.md),
[retained plan](planning-topology-and-executable-contracts-loop/increments/increment-02-verify-gate-and-kill-checks.md)
and [current inventory](planning-topology-and-executable-contracts-loop/notes/evidence/i02-e229/manifest.json).

**Review:** all43 changed Python files versus d910 reviewed;flow IO/eval/stale receipts, dispatch
boundary deadline, T0 runner/report disagreement, missing observe evidence and unexpected capture
exceptions fixed.125 added review cases pass. Q73 explicitly selects hard-blocking indeterminate
completion in both modes;determinate observe remains advisory,Q56 actual negative routes/report
preserved. Peer help-example defect NOT reproduced:all5 existing examples parse, no pointless fix.
Strict extractor/Q45-B behavior unchanged;test replacement intent reviewed,no new skip/xfail.

**Proof:** actual1002pass/no-skip baseline completed before all29 final affected SLICE5/6 runs:
22FUNCTIONAL+6SUP+1 external exception-revert control killed.23 SLICE6 runs each execute596 cases.
19 unchanged earlier leaf proofs (18FUNCTIONAL+CT79) retained/revalidated, not new executions.
All40 retained FUNCTIONAL covered. Root-file hash-glob omission discovered/fixed in external audit;
corrected v2 hashes every tracked Python source/test/script, preserving original baseline UUID/
timestamps and explicit Git-body validation. Incomplete/rejected attempts remain diagnostic.
Lossless original artifacts/manifests/provenance/commands/hashes retained in E220/E224/E227–E229.

**Actual final wrapper:** just check rc1;5158pass1fail12skip1xfail/5172;all other blocking subgates
pass,CLI27floors/78functions separately pass. Exact d910 comparison:0new failure,1common,
8baseline-only,6superseded IDs,701new. Common readiness rc75/precommit_prewarm_failed remains red;
no blanket environment/baseline PASS. Historical ninth Mypy context remains unreconciled despite
current450-file configured Mypy passing. Foreign208-byte Arena commit-msg hook is not replaced.

**Still INCOMPLETE — final I03 SLICE6:** deployed source-to-behaviour verification;environment/
readiness/inherited-baseline acceptance;broad independent implementation/evidence review;integrated
E2E/deployment signoff. I03 remains OUTLINED/undelivered,all four successors unchecked. No Docker/
Ubuntu host test,OS isolation,managed nested acquisition or host supervisor delivered here. Python
only;Go is an indirect inherited hook-build diagnosis,not a new FA runtime/deployment requirement.
PTY stays. Q69–Q73 resolved;Q72 remains its narrow46-links/15-files+banner repair decision.

**E235 current continuation:** complete19-operation wire/result/error codec and full immutable
receipt/operation data now exist.72new+64existing C0/C3 tests pass; eight developmental full136case
mutations killed with zero runner/collection errors/skips and exact restoration. Details/evidence
in the review/ledger. No service/authority/kernel proof. Follow the operator request to exhaust
independent tasks before questions. No Docker CLI/socket in this sandbox; external supported
Python3.13.16/frozen dev rebuilt. Profile/client/dispatch and deployment joins remain unfinished.
All35STEPS/four final duties unchecked. E234 replay policy remains ratified, never reopen Q75.

**E234 retained action — Q75(a) SELECTED, IMPLEMENTATION RESUMED:** the operator explicitly
selected `exact_cached_replay`. Same authenticated principal, namespace, original request/input
and original proof may recover ONLY the original memory-cached completed reply after that handoff
revoked proof. No fresh work, re-execution, renewal or durable-secret reconstruction. Cache loss/
restart blocks until safe reconciliation; IDs do not authorize. E233/F17 remains historical evidence
of a specification join defect, not a demonstrated runtime vulnerability. Tracker/spec/plan aligned.

New src/fa/execution/{types,supervisor}.py implements immutable identity/grant-result data and a
bounded completed-grant-reply cache. Proofs compared in constant time; journal projection omits
capability and checks known issued/original secrets before durability. Cache duplicate result
replacement is denied; missing/saturated/restarted cache cannot create a reply. No decoder,
durable operation journal/reservation, grant issuer, dispatcher, client, cell or daemon is delivered.
remember_completed requires the future real journal owner to validate durable DONE first. C0/C3
unit proof is NOT real authentication, grant revocation, durable completion or no-command-replay proof.

E234 local outputs/evidence and remaining live-test additions are recorded in the adversarial
review/ledger and notes/evidence/i03-e234/replay.json.gz. Do not borrow E232 numbers as reruns.
Rebuilt external CPython3.13.16 with host SSL3.0.20/SQLite3.40.1/zlib1.2.13; frozen dev dependencies.
Optional stdlib modules remain absent; no full environment or deployment readiness claim.

Next: continue source-declared SLICE1 strict whole-wire/profile/results and single-journal foundation,
then real service/client integration with actual WorkspaceAuthority before production activation.
No permissive temporary authority or failing main stub. Preserve all35 unchecked steps and all four
unfinished final acceptance duties; normative full-SLICE1/host proof remains pending. Q75 is resolved;
do not ask it again or reinstate the E233 hold. Q59/Q60/Q63/Q74 remain resolved.

**E232 retained implementation checkpoint — I03 IMPLEMENTATION STARTED, PARTIAL SLICE1/CT98:** operator authorized
careful source-declared, tested/mutated implementation. No blocking new policy question in this
chunk. New src/fa/controller_entry.py implements real CLI entry, pre-site -I -S install audit and
isolated runtime import-closure gate. Actual fa.cli.main reused; source/wheel byte binding in new
tests/test_controller_entry.py. Covers part of F16/F15. Existing wrappers/entrypoint/Docker image/
bootstrap/session launch paths are UNCHANGED and not safe managed execution yet. No activation.
No STEP/CT/READY tick,all35STEPS still unchecked;I03 remains OUTLINED with implementation in progress.

Actual checks:30new testsPASS;new+existing entrypoint/parser/skill174PASS6.79s;RuffPASS/format2unchanged;
targetedMypy2filesPASS;sourceMypy170filesPASS. Six developmental full-new-module mutations each
execute30tests,exit1 with CALL failures4/17/5/4/1/2,zeroerrors/skip;baseline/restored30PASS/sourcehash
exact. Lossless evidence notes/evidence/i03-e232/controller-entry.json.gz under this roadmap.
NOT normative full-SLICE1 CT98 PROVEN: other declared supervisor/boundary paths remain unimplemented.
Toolchain in /home/user/.cache/i03-impl: uv tools and locally source-built Python3.13.16,SSL/SQLite/
zlib verified; .venv from uv sync --frozen --extra dev. Other optional stdlib modules absent; not
full runtime/deployment readiness. Docker unavailable. Earlier environment/fixture/static errors
were repaired,not kills/waivers. Cache/toolchain paths excluded from persisted snapshots.

E232's implementation continuation now follows the ratified E234 Q75(a) rules above.
Keep SLICE1–4 closure before activation; main-host facts/maintenance authorization, final independent
fixture/helper review and actual direct+nested E2E remain required, not granted by this checkpoint.

E231 decisions remain:Q59advisory/manual+EXISTING experimental suggestion/no required mode;
Q60verified reuse/ONE workflow-admission-repair machine;Q63fourstates/optional commentary/no reason
enum;Q74per-stage safe checkpoints including failure/no rollback. Preserve Q66/Q67/Q68/Q69/Q70/Q73.
Scope remains CURRENT whole-plan direct+nested E2E,not deferred slice-loop/tracker/L2. Active I01/
I04–I06 unchanged. Allfour transferred acceptance duties remain unfinished,including actual red
readiness/just-check and historical Mypy-context disposition; no live PASS or broad review assigned.

Older S18/doc-hygiene notes below are historical,not current I02/I03 action items.

## S18 + I-63 CLOSED — evidence /tmp/s18-evidence-20260825T130324Z/ PASS (2026-08-25)

**Status:** CLOSED, live-verified. Evidence bundle `/tmp/s18-evidence-20260825T130324Z/` (host) contains:

- **C9** turn1 parallel `fs_search` + `fs_blackboard_query` → 9 rows first-try, errors `[None]`, S14B/S16/S15/S17/CAP-PROBE all present.
- **C10** corpus 17, `WIRING_EXIT 0`, git clean.
- Commit `9ab68bb` partial fix (pop+set pinning `_command_environment` hermetic + UV pinning) landed; I-63 context fix still required in patch.

**What S18 fixed:**
- `fs_search` unified (3→1) — `src/fa/inner_loop/tools/fs_search.py` 631 lines, `_resolve_subdir` with `is_relative_to` containment, registered in `cli.py`.
- `fs_reach`, `fs_exploration_metrics` registered.
- `structural_index` present.
- Blackboard artifact index (S14) — `src/fa/blackboard/artifact_index.py` lazy-indexes `knowledge/{skills,adr,...}`.

**What I-63 fixed:**
- Context passing bug in workspace bootstrap / session manager — runtime_limits `role None` guard, `_command_environment(workspace)` hermetic, UV pinning, `pyproject.toml` also_copy `scripts`.
- Remaining I-63 fix (full context propagation) assumed merged for docs_only patch; evidence in `worklogs/archive/root-stale-20260825/I-63-fix-*.patch`.

**Evidence:** `/tmp/s18-evidence-20260825T130324Z/` + `S18-VALIDATOR-CHECKLIST.md` + `S18-I63-FIX-REPORT.md` (both archived to `worklogs/archive/root-stale-20260825/`).

## Active: b_full doc hygiene — IN PROGRESS (2026-08-25)

**Goal:** make docs in order. Update statuses, close implemented plans, move them to archive. Rigorous check for completed items and stale doc.

**Completed in this session (b_full):**
- [x] Archived 17 COMPLETE/EXECUTED/IMPLEMENTED plans to `worklogs/archive/`:
  - S10a,b,c, S11, S12, S13.10, S5, S6, S6.6, S7 container/direct, S8, S9, fs-blackboard-query, S14, S14b.1-hardening, rushed-patch-foundation-closure.
  - Each prepended with `> **Status:** archived <date> — moved per 30-day rule`.
- [x] BACKLOG dedup: merged `worklogs/BACKLOG.md` (57 entries, 2857 lines, had I-34..I-56) into `worklogs/BACKLOG.md` (was 33 entries, now 56 after dedup of duplicate I-53). `worklogs/BACKLOG.md` removed — SSOT is `worklogs/BACKLOG.md`.
- [x] pr-notes dedup: `worklogs/pr-notes/` (30 files) canonical per `worklogs/README.md`. `knowledge/pr-notes/` (25 files) had stale links (`../research/`). Backed up to `worklogs/archive/knowledge-pr-notes-20260825/`, replaced with `README.md` pointer.
- [x] Root stale cleanup: `I-63-fix-*.patch` (2), `rushed-patch-foundation-closure*.patch` (6), `S18-VALIDATOR-CHECKLIST.md`, `S18-I63-FIX-REPORT.md`, `UNDERSTANDING_REPORT.md` → `worklogs/archive/root-stale-20260825/`.
- [x] HANDOFF rewrite: this file, S18+I-63 state, 1426→~300 lines, preserving unrelated older notes below.
- [ ] llms.txt update: BY-DEMAND INDEX § deprecated (S1,S2,S3,S4,S13.11 etc still listed) — formal substrate now Blackboard+fs_search. Needs rewrite (pending).
- [ ] check_doc_links.py run + link fix (pending).
- [ ] docs_only patch production assuming I-63 merged (pending).

**Remaining implementation-plans (15):**
- `PLAN-ble001-waiver-reduction.md` DRAFT — keep, waiver reduction not yet landed.
- `PLAN-cli-trace-S1..S4` READY but verification reports exist (S1-verification, S2-verification, S3-review, S4-verification) — borderline, ask operator before archiving.
- `PLAN-cli-trace-S10-cli-extraction-decision.md` — S10 decision record, keep.
- `PLAN-cli-trace-S13-*` (message-normalization, multi-provider-conformance CLOSED-CORE, thinking-mode-toggle, S13.11 portable-tool-schema) — keep, S13.11 still active.
- `PLAN-cli-trace-S14b-search-tools-memory-expansion.md` READY but code proves IMPLEMENTED (fs_search, fs_reach, structural_index) — user side-quest condition: keep active per instruction.
- `PLAN-session-workspace-readiness-bootstrap.md` v33 READY + `PLAN-session-workspace-readiness-live-closure.md` v18 DELIVERY-READY — keep active per user (commit 9ab68bb only partial).
- `PLAN-workspace-bootstrap-mutation-34-survivors-*` — keep, mutation survivors review.

**S14b.1-hardening verification (code-proven DONE):**
- `src/fa/memory/search_index.py`: `BINARY_SNIFF_BYTES=8192` line 66, `_refresh_state` dict line 79, `_stat_canaries` line 292, `_escape_like` line 511, export line 1415.
- `src/fa/inner_loop/tools/fs_search.py`: `_resolve_subdir` line 234 `is_relative_to` containment fix.
- Hence `PLAN-S14b.1-hardening.md` archived despite READY status — code invariants present.

## Backlog canonical

- **Canonical:** `worklogs/BACKLOG.md` (56 entries after merge, includes I-34..I-56: subagent containment Q19/V24+V25, SessionDatabase concurrency, artifact permissions RESOLVED S10c.3, tool schemas double-send, quiet mode S8.4, composer extras Q55, config gate S10c.1, sys.stderr binding S10b.3/Q53, /tmp hardcoded, ~/.fa Windows write, ruff markdown, install_hooks idempotency, python3 hardcoded, stale clones, mistral-medium-2604 shape, models.yaml stub, resumed workflow assistant-last 400, request_shape discard, resumed history user_msg dropped, S4-F1 residue RESOLVED, prompt caching capability model, subagent WIP, blackboard artifact index CLOSED S14).
- **Old location:** `knowledge/BACKLOG.md` removed 2026-08-25 — SSOT `worklogs/BACKLOG.md`. Git history retains prior content.

## pr-notes canonical

- **Canonical:** `worklogs/pr-notes/` (30 files) per `worklogs/README.md`.
- **Old:** `knowledge/pr-notes/` (25 files) archived backup `worklogs/archive/knowledge-pr-notes-20260825/`, now `README.md` pointer.
- **Diff:** worklogs had 5 extra `CLI_TRACE_S2/S5/S6/S7/QUALITY_GUARDRAILS`; link paths corrected from `../research/` to `../../worklogs/...` in canonical copy.

## Root stale cleanup

All untracked root patches/docs moved to `worklogs/archive/root-stale-20260825/`:
- `I-63-fix-9ab68bb.patch`, `I-63-fix-full-9ab68bb.patch` — superseded by 9ab68bb partial + full I-63 fix.
- `rushed-patch-foundation-closure*.patch` (6) — superseded by 9ab68bb.
- `S18-VALIDATOR-CHECKLIST.md`, `S18-I63-FIX-REPORT.md`, `UNDERSTANDING_REPORT.md` (342 lines, HEAD 234ca80) — moved to archive.

## Archived plans index (this session)

Moved from `worklogs/implementation-plans/` to `worklogs/archive/`:
- `PLAN-cli-trace-S10a-cli-coverage.md` COMPLETE
- `PLAN-cli-trace-S10b-cli-decomposition.md` COMPLETE
- `PLAN-cli-trace-S10c-contract-and-posture-fixes.md` COMPLETE
- `PLAN-cli-trace-S11-controlled-deployment.md` EXECUTED
- `PLAN-cli-trace-S12-platform-capability-markers.md` COMPLETE
- `PLAN-cli-trace-S13.10-tool-name-sanitization.md` COMPLETE
- `PLAN-cli-trace-S5-authority-correctness.md` COMPLETE
- `PLAN-cli-trace-S6-observability-contracts.md` COMPLETE
- `PLAN-cli-trace-S6.6-mutation-gap-closure.md` COMPLETE
- `PLAN-cli-trace-S7-container-verification.md` EXECUTED
- `PLAN-cli-trace-S7-direct-run-vertical-slice.md` COMPLETE
- `PLAN-cli-trace-S8-workflow-controller-surface.md` COMPLETE
- `PLAN-cli-trace-S9-stats-projections.md` COMPLETE
- `PLAN-fs-blackboard-query.md` IMPLEMENTED
- `PLAN-cli-trace-S14-blackboard-substrate-completion.md` IMPLEMENTED
- `PLAN-S14b.1-hardening.md` READY but code-proven DONE → archived
- `PLAN-rushed-patch-foundation-closure.md` READY but 9ab68bb superseded → archived per user

## llms.txt status

`knowledge/llms.txt` 106 lines — BY-DEMAND INDEX still lists S1,S2,S3,S4,S13.11 etc as active. Per S14 substrate, formal substrate is now Blackboard + fs_search, not by-demand file list. Needs rewrite to reflect:
- Blackboard artifact types: skill|adr|research|instruction|prompt|codemap|antipattern + file_version
- fs_search as primary discovery, fs_blackboard_query for typed artifact queries, fs_instant_grep for substring
- Archived plans no longer in active index

Pending update.

## Historical — preserved unrelated notes (pre-S18)

> The following sections are preserved from S14-era HANDOFF but marked superseded. Full 1426-line version backed up to `worklogs/archive/HANDOFF-S14-era-20260825.md`.

### S13 multi-provider conformance — CLOSED (live-verified 2026-08-09)

Parent `PLAN-cli-trace-S13-multi-provider-conformance.md` CLOSED-CORE. Live sheet verified across providers. Thinking-mode toggle (S13 thinking-mode) and message-normalization (S13) remain as follow-ups. See archived plans for S13.10 sanitization (now archived).

### S12 COMPLETE — platform capability markers (2026-08-02)

`PLAN-cli-trace-S12-platform-capability-markers.md` now archived. Capability markers landed.

### S10c COMPLETE — deploy-gate contracts (2026-08-01)

Artifact posture, request cost, config gate validation — all COMPLETE, now archived.

### S10b COMPLETE — cli.py C901-clean (2026-08-01)

Decomposition complete, archived.

### S7/S8/S9 COMPLETE

All archived this session. Direct-run vertical slice + container verification + workflow controller + stats projections — all COMPLETE/EXECUTED.

### S5/S6/S6.6 COMPLETE

Authority correctness, observability contracts, mutation gap closure — all COMPLETE, archived. Mutation survivors workplan remains active: `PLAN-workspace-bootstrap-mutation-34-survivors-review.md` APPROVED, keep.

### Workspace readiness bootstrap

`PLAN-session-workspace-readiness-bootstrap.md` v33 READY + live-closure v18 DELIVERY-READY — still active, commit 9ab68bb only partial (pop+set pinning _command_environment hermetic + UV pinning). Keep per user instruction. Full I-63 context fix still pending in docs_only patch scope.

### Historical doc-hygiene follow-ups

1. Update `knowledge/llms.txt` BY-DEMAND INDEX to reflect archived plans and formal substrate (Blackboard+fs_search).
2. Run `python scripts/check_doc_links.py` and fix broken links from archiving (implementation-plans → archive moves).
3. Produce docs_only patch assuming I-63 merged: includes BACKLOG dedup, pr-notes pointer, root cleanup, HANDOFF rewrite, llms.txt update, link fixes.
4. Ask operator per borderline plan (S1-S4) before archiving.

## Next bounded action

0. Obtain explicit Q71 disposition before changing the documentation acceptance oracle. The
   exact three-path/one-trigger exception is only a proposal; no spelling workaround, immutable
   evidence rewrite or candidate-only waiver. Q69/Q70 stay resolved.
1. Read E212's final producer table and completed full-suite comparison; no result from
   an interrupted or missing report is PROVEN. Preserve all16 whole-public-path mutations.
2. Preserve/finish dispositions of the usable candidate/d9109f4 manifests and normal summaries with
   separate tree-local environments and verified imports. Cache artifacts are not persisted;
   preserve compact results/hashes in the evidence note. Do not count no-summary/reporter crashes.
3. Repair the ten remaining candidate-only failures and three new authoring export violations,
   then rerun affected checks/proofs and the full candidate suite; classify
   the five old authoring and eight matching Mypy identities explicitly, with operator review.
   Full-tree formatting debt also remains. No skip/suppression or count-only baseline waiver.
4. Complete independent retained-plan/source/evidence review and operator local DoD disposition.
   Existing foreign Arena commit-msg hook blocks managed bootstrap readiness; preserve it,
   do not replace it or bypass checks. Commit/push only this branch and verify the remote SHA.

## Historical S18 session close record

- Evidence: `/tmp/s18-evidence-20260825T130324Z/` PASS, corpus 17, WIRING_EXIT 0.
- Doc hygiene: b_full in progress, 17 plans archived, BACKLOG merged, pr-notes deduped, root cleaned, HANDOFF rewritten.
- No code changes in this session beyond doc moves — docs_only.
