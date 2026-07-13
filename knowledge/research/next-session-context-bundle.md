---
title: "Next Session Context Bundle — ADR-13/14 Ready for Implementation"
source:
  - "knowledge/adr/ADR-13-stateful-bash-eventstream-runtime.md"
  - "knowledge/adr/ADR-14-multitask-subagents-worktree-isolation.md"
  - "knowledge/research/adr-13-14-implementation-plan-2026-07-11-v2-production.md"
  - "knowledge/research/two-papers-first-pass-2026-07-11.md"
  - "knowledge/research/two-papers-deep-dive-2026-07-11.md"
  - "knowledge/research/paper2-missed-high-roi-outside-box.md"
  - "implementation-plan-review-gaps-logic-errors.md"
  - "final-architecture-lockin-2026-07-11.md"
  - "architecture-foundation-lockin-questions-v2.md"
  - "answers-just-bash-worktree-metaharness.md"
compiled: "2026-07-11"
chain_of_custody: "All research notes, ADR drafts, skeleton code, and Q&A rounds from 2026-07-10 to 2026-07-11. No external unverified claims."
goal_lens: "Provide complete context for new session agent to start implementing ADR-13/14 without re-reading all history"
tier: stable
---

# Next Session Context Bundle

This file is the single entry point for next session. Read this first, then open linked files on demand. Do not load everything.

## Must Read First (5 files, in order, as per llms.txt §MUST READ FIRST but updated for ADR-13/14)

1. `knowledge/adr/ADR-13-stateful-bash-eventstream-runtime.md` — Final decision: EventStream Runtime FastAPI + PtyPool libtmux direct, prompt caching per role, compaction foundation, defensive worktree checks Tier 1
2. `knowledge/adr/ADR-14-multitask-subagents-worktree-isolation.md` — WorktreeManager Shared→Isolated, Profiles dynamic, instant grep FTS5 trigram, JSON envelope full schema, skill globs
3. `knowledge/research/adr-13-14-implementation-plan-2026-07-11-v2-production.md` — Production-ready rollout with 6 phases + Phase 0.5 Formal Blackboard + Structured Telemetry (1-2 entries tops), senior eng principles, defensive checks, feature flags, thread safety, graceful degradation
4. `final-architecture-lockin-2026-07-11.md` — Consolidated decisions from 2 Q&A rounds: just-bash vs libtmux, worktree transition easy via abstraction, metaharness main stateful rest stateless
5. `implementation-plan-review-gaps-logic-errors.md` — 16 logic gaps A-P that cause sloppy code, with fixes, must be addressed before PR

## By-Demand Index (Open Only Relevant)

### Core Implementation Files (PR-ready skeletons, need to be moved to repo)

- `src/fa/runtime/__init__.py`, `pty_pool.py`, `pty_pool_v2_production.py`, `bash_executor.py`, `server.py` (skeleton-runtime-server.py) — EventStream Runtime, PtyPool shared Server, LRU fail-fast, no global singleton, DI via SessionState, graceful fallback pexpect
- `src/fa/workspace/__init__.py`, `worktree_manager.py` — WorktreeManager ABC, SharedDir v0.1 + Isolated future, defensive checks (path exists, worktree list contains, branch already checked out fail-fast), sanitized branch names
- `src/fa/memory/__init__.py`, `fts_index.py` — InstantGrepIndex FTS5 trigram with DELETE then INSERT, mtime tracking, stale cleanup, fallback porter with WARNING
- `src/fa/blackboard/__init__.py`, `blackboard.py` — NEW Phase 0.5 Formal Blackboard with content_hash, toolchain_digest, schema_version, parent_id, read_set, write_set, assumptions, version_dependencies, queryable, detect_conflict
- `src/fa/telemetry/__init__.py`, `telemetry.py` — NEW Phase 0.5 Minimal Structured Telemetry TelemetryEvent structured, not raw 100k logs, offload full outputs to ArtifactStore + 500-char preview, artifact_id
- `src/fa/inner_loop/prompt_composer.py`, `prompt_composer_v2.py` — PromptParts cacheable split, cache-key = role_id + hash(names+schemas) + hash(agents_map), to_anthropic (cache_control), to_openai (prompt_cache_key)
- `src/fa/inner_loop/profiles.py` — PROFILES dict dynamic toolset researcher 600 tokens vs full 3000, globs frontmatter alwaysApply false
- `src/fa/inner_loop/subagent_runner.py` — SubagentRunner stateless, scrubbed env extra_allow X_FA_PROXY_TOKEN foundation for Gap 7 arbiter, filtered history, JSON validation cached, artifact write
- `src/fa/inner_loop/compaction/__init__.py`, `foundation.py` — CompactionManager Stage 1 warning 70% + offload 8000, foundation for ADR-15 full 5-stage

### Tests (PR-ready)

- `tests/test_pty_persistence.py` — cd persistence, env persistence, ANSI strip, Ctrl+C
- `tests/test_worktree_defensive.py` — SharedDir, branch already checked out detection, defensive exists
- `tests/test_prompt_caching_per_role.py` — cache keys differ per role, cacheable split
- `tests/test_tool_batching.py` — grouping read-only vs sequential, ThreadPool parallel <0.25s
- `tests/test_instant_grep.py` — trigram substring search <50ms
- `tests/test_blackboard_conflict.py` — two subagents write same file → conflict detected
- `tests/test_telemetry_structured.py` — structured fields, no raw 100k drowning, sanitizes secrets

### Research Context (For Deep Dive, Not Required for Implementation)

- `knowledge/research/two-papers-first-pass-2026-07-11.md` — First pass of 2 PDFs (MACOG 18p + Code as Harness 102p), focus points
- `knowledge/research/two-papers-deep-dive-2026-07-11.md` — Deep dive on I-IR §4.3, Implementation Notes §4.10, Constrained Decoding §4.5, Counterexample-Guided Repair §4.6, and Code as Harness relevant mechanisms per feedback
- `knowledge/research/paper2-missed-high-roi-outside-box.md` — Outside-the-box 1-2 entries: Formal Shared Harness Substrate + Minimal Structured Telemetry, topology complexity vs formality, harness as distillation surface
- `final-review-gaps-high-roi-metaharnesses-july2026.md` — 12 gaps vs SOTA trends July 2026
- `adr-13-14-final-with-gaps-addressed.md` — Gap-by-gap answers with verification
- `answers-just-bash-worktree-metaharness.md` — Q1 just-bash vs libtmux, Q2 worktree transition easy, Q3 metaharness

### Decisions Already Locked (From Q&A)

From `architecture-foundation-lockin-questions-v2.md` and final Q&A round:

- **Stateful impl:** libtmux / wmux wrapper (direct_fastapi chosen in final Q&A: direct FastAPI EventStream Runtime, not pexpect phased)
- **Worktree model:** v0.1 no worktree shared dir stateless subprocess.run 100% stable 0 code eliminate scope creep, future separate dirs .fa/worktrees/<id>, easy transition via WorktreeManager abstraction
- **Roles:** main stateful planner-coder-eval workflow, rest stateless (research, chat, code-review). Prompt assembly hybrid BASE + AGENTS.md map (lazy) + memory_summary.md progressive + task + tools cacheable prefix 10% cost. Toolset per role dynamic (main chooses tools at spawn)
- **Parallelism:** 1 subagent limit v0.1 to eliminate scope creep, future 2-3 (2 research, 1 code-review)
- **Structured output:** JSON envelope full schema (Goal, Verification, Risks) per turn/per task, instructions for subagents creating artifacts, task_worklog.md per task Goal/Evidence/Steps/Verification, for PR → PR body
- **ADR scope:** two_split ADR-13 PTY Manager + ADR-14 Multitask Subagents
- **Memory:** llms.txt map + short summary + direct link, agent should be able to find place to search. Cursor instant grep N-gram trigram DB — implement via FTS5 trigram
- **Toolset per role:** dynamic
- **Orchestration:** hybrid planner writes spawn in Plan, coder executes as step
- **Worklog:** task_worklog.md per task (deferred detailed design but direction locked)
- **Subagent JSON:** full schema
- **Memory index:** FTS5 trigram
- **Skill writing:** manual approval
- **KPI measurement:** manual count baseline 124 steps

From final Q&A round (6 questions):

- Prompt caching per role: yes_now cache-key = role_id + hash(tool_defs)
- Compaction foundation: stage1_only warning + offload 8000 as foundation for ADR-15
- Skill globs: add_globs alwaysApply false frontmatter
- Arbiter foundation: single_token_now with separate var for future per-subagent random
- Tool batching: yes_parallel read-only via ThreadPool max 5 high priority
- EventStream Runtime: direct_fastapi (skip pexpect phase)

## Current State of Repo (From HANDOFF.md As Of 2026-07-01)

- Workspace Isolation ADR-13 implemented: /repo RO mount + /sessions per-session git clone --local
- Live per-turn console output EventBus + OutputEvent + ConsoleRenderer
- API-key isolation hardened to egress-injection proxy ADR-12 Option C: keys live ONLY in fa-egress-proxy container, agent holds no key, reaches providers via proxy FA_EGRESS_PROXY_URL + X-FA-Proxy-Token, container separation boundary, defense-in-depth fail-closed bash-gate deny secret-path reads, model-egress redaction chokepoint
- Work on hold: loop-improvement-workplan.md Tier 2.2,2.5,2.6,5,1.3,6,2.4,7; mutation-survivors-workplan.md 163 survivors; fa-workflow-loop-implementation-plan; BACKLOG I-12/I-13/I-14 ADR-11 authoring guardrails PR3+; I-24 ADR-12 follow-ups

## Next Session Protocol (For New Agent)

1. Follow AGENTS.md Pre-flight checklist: Step 1 Recency surface `git log -n 5 --since="7 days" --oneline -- knowledge/ docs/ AGENTS.md`, Step 2 Term expansion `grep -i "^\| \*\*\*\*" knowledge/glossary.md`, Step 3 Symmetric reading `grep -ril "" knowledge/research/` open every file, Step 4 Subtraction-check, Step 5 Goal-lens declaration.

2. Read Must Read First 5 files in order from this bundle, not all by-demand.

3. Implement Phase 0 Quick-win (0.5 day) first: cap 8000 + warning + instant_grep skeleton + send_ctrl_c + chronicle_search + usage.

4. Then Phase 0.5 Formal Blackboard + Structured Telemetry (1.5 days): Blackboard content-hashed + transactional, Telemetry structured not raw, change contract template.

5. Then Phase 1 Foundation Abstractions (1 day): WorktreeManager defensive, Profiles, SubagentEnvelope, PromptComposer per role, FeatureFlags.

6. Then Phase 2 Tool Batching + FTS5 (1 day): ThreadPool parallel read-only with Lock, FTS5 trigram DELETE then INSERT, stale cleanup.

7. Then Phase 3 EventStream Runtime In-Process PtyPool (2-3 days): shared Server, LRU fail-fast never reuse main, sentinel, ANSI strip, fallback pexpect with WARNING.

8. Then Phase 4 Remote Extraction only if Phase 3 instability or need 2-3 parallel.

9. Then Phase 5 Subagent Runner + Worklog + Eval-Harness (1-2 days): filtered history, JSON validation cached, task_worklog.md, proxy_token separate var, 1 subagent limit, mini eval-harness 5 tasks, measure 124→30-40.

10. Update knowledge/llms.txt BY-DEMAND INDEX, knowledge/adr/DIGEST.md, HANDOFF.md§Next per MAINTENANCE.md link integrity, markdown-link-check.

11. No shell=True without # nosemgrep + ADR-6 reference, no Level-0 TCB import external lib per ADR-11.

## Verification Steps for Next Session

- [ ] Read this bundle + 5 Must Read First files
- [ ] Grep TODO GAP in implementation-plan-review-gaps-logic-errors.md and fix Gaps A-P
- [ ] Run pytest tests/test_worktree_defensive.py -v, test_prompt_caching_per_role.py, test_tool_batching.py, test_instant_grep.py, test_pty_persistence.py, test_blackboard_conflict.py, test_telemetry_structured.py
- [ ] Manual: curl POST http://localhost:8001/execute with cd /tmp && pwd → /tmp (if FastAPI mode)
- [ ] Manual: fa run --role planner --task "Read repository and tell what you found" measure steps before/after target 30-40 vs 124 baseline
- [ ] Update llms.txt, DIGEST.md, HANDOFF.md per MAINTENANCE.md

## References for New Session

- All files listed in By-Demand Index above are PR-ready skeletons, need to be moved from workspace root /home/user/ to actual repo paths and adapted to existing code style (ATX headings, short lines ~150 chars, fenced code blocks with language tag)
- Tests are skeletons, need to import from actual src/fa/... paths
- Implementation plan v2 production is superset of v1, includes senior eng principles

