# HANDOFF.md — next agent/session

> Read [`knowledge/llms.txt`](../knowledge/llms.txt) §MUST READ FIRST.
> This file records the verified state and the next bounded action.
> Previous 1426-line S14-era version archived to `worklogs/archive/HANDOFF-S14-era-20260825.md`.

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

## Next bounded action

1. Update `knowledge/llms.txt` BY-DEMAND INDEX to reflect archived plans and formal substrate (Blackboard+fs_search).
2. Run `python scripts/check_doc_links.py` and fix broken links from archiving (implementation-plans → archive moves).
3. Produce docs_only patch assuming I-63 merged: includes BACKLOG dedup, pr-notes pointer, root cleanup, HANDOFF rewrite, llms.txt update, link fixes.
4. Ask operator per borderline plan (S1-S4) before archiving.

## Session close protocol

- Evidence: `/tmp/s18-evidence-20260825T130324Z/` PASS, corpus 17, WIRING_EXIT 0.
- Doc hygiene: b_full in progress, 17 plans archived, BACKLOG merged, pr-notes deduped, root cleaned, HANDOFF rewritten.
- No code changes in this session beyond doc moves — docs_only.
