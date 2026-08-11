# Doc Inventory for User Review — Criterion #8 (Docs Update)

> Generated: 2026-07-16
> Purpose: Complete list of all human/agent-facing documentation files for your review and correction before any edits are made per workplan criterion #8.

---

## How to Use This List

- **Review each file** and mark it as: ✅ keep as-is, ✏️ needs update, 🗑️ prune/merge, or ➡️ move
- **Add notes** on what changes are needed for files marked ✏️
- Once you've corrected the list, I'll perform the actual doc updates

---

## 1. Root-Level Docs

| # | File | Lines | Status | Notes |
|---|------|-------|--------|-------|
| 1 | `AGENTS.md` | 279 | ✏️ | Needs update for blackboard/DB integration, session_db authority |
| 2 | `HANDOFF.md` | 295 | ✏️ | Must reflect current state: criteria #1-7, #9 done; #8 in progress |
| 3 | `README.md` | 123 | ? | Review for accuracy |

---

## 2. Knowledge Core Docs

| # | File | Lines | Status | Notes |
|---|------|-------|--------|-------|
| 4 | `knowledge/project-overview.md` | 420 | ✏️ | Four pillars description should mention SessionDatabase authority |
| 5 | `knowledge/reference.md` (was architecture.md) | 228 | done | Merged patterns into reference.md §Patterns |
| 6 | `knowledge/reference.md` (was glossary.md) | 228 | done | Merged entries into reference.md §Terms |
| 7 | `knowledge/llms.txt` | 81 | ✏️ | Mark as deprecated in favor of blackboard.query(); note the mapping |
| 8 | `knowledge/skills/doc-maintenance/SKILL.md` (was MAINTENANCE.md) | ~80 | done | Converted to loadable skill |
| 9 | `knowledge/README.md` | ? | ✏️ | Update memory system overview to mention SessionDatabase authority |
| 10 | `knowledge/reference.md` (was FEATURES.md) | 228 | done | Merged features into reference.md §Features |

---

## 3. Knowledge/Instructions

| # | File | Lines | Status | Notes |
|---|------|-------|--------|-------|
| 11 | `knowledge/instructions/README.md` | ? | ? | Review for accuracy |
| 12 | `knowledge/instructions/01-install.md` | 577 | ✏️ | Verify all paths are correct (session_db, global_history.db) |
| 13 | `knowledge/instructions/02-operations.md` | 1104 | ✏️ | Add section on session.db structure, JSONL mirrors, global_history.db, fa stats --global-history |

---

## 4. Knowledge/ADR

| # | File | Lines | Status | Notes |
|---|------|-------|--------|-------|
| 14 | `knowledge/adr/DIGEST.md` | 735 | ? | Review for accuracy |
| 15 | `knowledge/adr/README.md` | ? | ? | Review index completeness |
| 16 | `knowledge/adr/ADR-1-v01-use-case-scope.md` | ? | ? | Review |
| 17 | `knowledge/adr/ADR-2-llm-tiering.md` | ? | ? | Review |
| 18 | `knowledge/adr/ADR-3-memory-architecture-variant.md` | ? | ✏️ | Likely needs update for session_db authority model |
| 19 | `knowledge/adr/ADR-4-storage-backend.md` | ? | ✏️ | Likely needs update — storage is now SQLite-first |
| 20 | `knowledge/adr/ADR-5-chunker-tool.md` | ? | ? | Review |
| 21 | `knowledge/adr/ADR-6-tool-sandbox-allow-list.md` | ? | ? | Review |
| 22 | `knowledge/adr/ADR-7-inner-loop-tool-registry.md` | ? | ✏️ | References event_log — should mention session_db as authority |
| 23 | `knowledge/adr/ADR-8-hook-registry.md` | ? | ? | Review |
| 24 | `knowledge/adr/ADR-9-llm-provider-client.md` | ? | ? | Review |
| 25 | `knowledge/adr/ADR-10-deterministic-harness-invariants.md` | ? | ? | Review |
| 26 | `knowledge/adr/ADR-11-authoring-guardrails.md` | ? | ? | Review |
| 27 | `knowledge/adr/ADR-12-secret-isolation.md` | ? | ? | Review |
| 28 | `knowledge/adr/ADR-13-workspace-isolation.md` | ? | ? | Review |
| 29 | `knowledge/adr/ADR-14-stateful-bash-eventstream-runtime.md` | ? | ✏️ | Likely needs update for session_db event storage |
| 30 | `knowledge/adr/ADR-15-multitask-subagents-worktree-isolation.md` | ? | ? | Review |
| 31 | `knowledge/adr/ADR-17-context-management-and-compaction.md` | ? | ? | Review |
| 32 | `knowledge/adr/ADR-template.md` | ? | ? | Review |

---

## 5. Knowledge/Skills

| # | File | Status | Notes |
|---|------|--------|-------|
| 33 | `knowledge/skills/README.md` | ? | Review |
| 34 | `knowledge/skills/tests-writing/SKILL.md` | ? | Review |
| 35 | `knowledge/skills/pr-creation/SKILL.md` | ? | Review |
| 36 | `knowledge/skills/mutation-clearing/SKILL.md` | ? | Review |
| 37 | `knowledge/skills/repo-audit/SKILL.md` | ? | Review |
| 38 | `knowledge/skills/skill-writing/SKILL.md` | ? | Review |

---

## 6. Knowledge/Templates

| # | File | Status | Notes |
|---|------|--------|-------|
| 39 | `knowledge/templates/config.yaml.example` | ✅ | Already fixed (removed /workspace) |
| 40 | `knowledge/templates/fa.env.template` | ✅ | Already fixed (removed /workspace) |
| 41 | `knowledge/templates/models.yaml.example` | ? | Review |

---

## 7. Knowledge/Trace

| # | File | Status | Notes |
|---|------|--------|-------|
| 42 | `knowledge/trace/codebase_map.json` | ? | Review for accuracy |
| 43 | `knowledge/trace/exploration_log.md` | ? | Review |
| 44 | `knowledge/trace/exploration_tree.yaml` | 🗑️ | Marked "superseded" — candidate for pruning |

---

## 8. Knowledge/Codemaps

| # | File | Status | Notes |
|---|------|--------|-------|
| 45 | `knowledge/codemaps/inner-loop-hooks-runtime-pipeline.md` | ? | Review |
| 46 | `knowledge/codemaps/model-freedom-control-runtime-pipeline.md` | ? | Review |
| 47 | `knowledge/codemaps/observability-logging-analytics-pipeline.md` | ? | Review |
| 48 | `knowledge/codemaps/provider-runtime-config-cooldown-pipeline.md` | ? | Review |

---

## 9. Knowledge/Anti-Patterns

| # | File | Status | Notes |
|---|------|--------|-------|
| 49 | `knowledge/anti-patterns/README.md` | ? | Review |
| 50 | `knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md` | ? | Review |
| 51 | `knowledge/anti-patterns/AP-002-stale-routing-index-counts.md` | ? | Review |
| 52 | `knowledge/anti-patterns/AP-003-shallow-fix-no-mechanism.md` | ? | Review |
| 53 | `knowledge/anti-patterns/AP-004-symptom-chasing-without-model.md` | ? | Review |

---

## 10. Knowledge/Prompts

| # | File | Status | Notes |
|---|------|--------|-------|
| 54 | `knowledge/prompts/README.md` | ? | Review |
| 55 | `knowledge/prompts/RESOLVER.md` | ? | Review |
| 56 | `knowledge/prompts/architect-fa-compact.md` | ? | Review |
| 57 | `knowledge/prompts/architect-fa.md` | ? | Review |
| 58 | `knowledge/prompts/ci-qa-implementation-session-start.md` | ? | Review |
| 59 | `knowledge/prompts/coder-recovery.md` | ? | Review |
| 60 | `knowledge/prompts/handoff-summarizer.md` | ? | Review |
| 61 | `knowledge/prompts/prompting.md` | ? | Review |
| 62 | `knowledge/prompts/research-briefing.md` | ? | Review |
| 63 | `knowledge/prompts/research-topic.md` | ? | Review |
| 64 | `knowledge/prompts/tool-shapes.yaml` | ? | Review |

---

## 11. Knowledge/PR-Notes (18 files)

| # | File | Status | Notes |
|---|------|--------|-------|
| 65 | `knowledge/pr-notes/README.md` | ? | Review |
| 66 | `knowledge/pr-notes/PR_BODY.md` | ? | Review |
| 67 | `knowledge/pr-notes/PR_BODY_GUARDRAILS_V2.md` | ? | Review |
| 68 | `knowledge/pr-notes/PR_NOTE_DOCKER_DOCS_CONSOLIDATION.md` | ? | Review |
| 69 | `knowledge/pr-notes/PR_NOTE_DOCKER_RUNTIME.md` | ? | Review |
| 70 | `knowledge/pr-notes/PR_NOTE_DOCS_IA_RESTRUCTURE.md` | ? | Review |
| 71 | `knowledge/pr-notes/PR_NOTE_FA_PROBE.md` | ? | Review |
| 72 | `knowledge/pr-notes/PR_NOTE_HOOKS_AND_WRAPPER_HELP.md` | ? | Review |
| 73 | `knowledge/pr-notes/PR_NOTE_HOOK_WORKFLOW_CLOSURE.md` | ? | Review |
| 74 | `knowledge/pr-notes/PR_NOTE_LIVE_OUTPUT.md` | ? | Review |
| 75 | `knowledge/pr-notes/PR_NOTE_LOGGING_CLEANUP.md` | ? | Review |
| 76 | `knowledge/pr-notes/PR_NOTE_LOOP_FOUNDATION.md` | ? | Review |
| 77 | `knowledge/pr-notes/PR_NOTE_OPS_AND_DOCS.md` | ? | Review |
| 78 | `knowledge/pr-notes/PR_NOTE_SANDBOX_MUTATION_CLOSURE.md` | ? | Review |
| 79 | `knowledge/pr-notes/PR_NOTE_STATS.md` | ? | Review |
| 80 | `knowledge/pr-notes/PR_NOTE_SYSTEM_PROMPTS_V2.md` | ? | Review |
| 81 | `knowledge/pr-notes/PR_NOTE_UPDATE_SCRIPTS_FIX.md` | ? | Review |
| 82 | `knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md` | ? | Review |
| 83 | `knowledge/pr-notes/chain-exhaustion-retry.md` | ? | Review |
| 84 | `knowledge/pr-notes/ci-smoke-fix.md` | ? | Review |
| 85 | `knowledge/pr-notes/network-resilience-fix.md` | ? | Review |
| 86 | `knowledge/pr-notes/redteam-sandbox-harden.md` | ? | Review |
| 87 | `knowledge/pr-notes/secret-paths-bypass.md` | ? | Review |
| 88 | `knowledge/pr-notes/workspace-isolation.md` | ? | Review |

---

## 12. Knowledge/Research (60+ files — selected)

| # | File | Status | Notes |
|---|------|--------|-------|
| 89 | `knowledge/research/authoring-hardening-workplan-v2-2026-07-16.md` | ✏️ | Update criterion #8 status |
| 90 | `knowledge/research/task-completion-session-2026-07-16.md` | ✏️ | Update completion status |
| 91 | `knowledge/research/state-assessment-2026-07-16.md` | ? | Review |
| 92 | `knowledge/research/phase1-closure-review-wiring.md` | ? | Review |
| (remaining ~57 research notes) | ? | Likely no update needed — historical reference |

---

## 13. Other Knowledge Files

| # | File | Status | Notes |
|---|------|--------|-------|
| 93 | `knowledge/BACKLOG.md` | ? | Review for accuracy |
| 94 | `knowledge/STAGE_0_0.5_VERIFICATION.md` | ? | Review |
| 95 | `knowledge/STAGE_1_VERIFICATION.md` | ? | Review |
| 96 | `knowledge/ci-guardrails-reference.md` | ? | Review |
| 97 | `worklogs/implementation-plans/loop-improvement-workplan.md` | ? | Review |
| 98 | `worklogs/implementation-plans/mutation-survivors-workplan.md` | ? | Review |
| 99 | `knowledge/review-stage-0-0.5-vs-plan.md` | ? | Review |

---

## 14. Config & Infrastructure (non-knowledge)

| # | File | Status | Notes |
|---|------|--------|-------|
| 100 | `.env.fa.template` | ✅ | Already fixed |
| 101 | `.github/CODEOWNERS` | ? | Review |
| 102 | `scripts/fa.service` | ? | Review |
| 103 | `Dockerfile.fa` | ? | Review |
| 104 | `docker-compose.fa.yml` | ? | Review |

---

## High-Priority Files for Criterion #8

Based on the blackboard/DB/main-loop integration research, these files **definitely** need updates:

1. **`knowledge/reference.md` (was architecture.md)** — Merged into reference.md §Patterns + §Session Data Layout
2. **`knowledge/reference.md` (was glossary.md)** — Merged into reference.md §Terms
3. **`knowledge/instructions/02-operations.md`** — Needs section on session.db, JSONL mirrors, global_history.db, fa stats
4. **`knowledge/llms.txt`** — Mark as deprecated in favor of blackboard.query()
5. **`AGENTS.md`** — Session loadout should mention session_db and blackboard
6. **`knowledge/reference.md` (was FEATURES.md)** — Merged into reference.md §Features
7. **`knowledge/project-overview.md`** — Update substrate description with SessionDatabase authority
8. **`knowledge/adr/ADR-4-storage-backend.md`** — SQLite is now the authority, not just JSONL
9. **`knowledge/adr/ADR-7-inner-loop-tool-registry.md`** — EventLog now writes to session_db first
10. **`knowledge/adr/ADR-14-stateful-bash-eventstream-runtime.md`** — Events now stored in SQLite

---

## Files Confirmed Already Updated This Session

- ✅ `scripts/fa-post-setup.sh` — Fixed hardcoded `/workspace`
- ✅ `scripts/fa-update.sh` — Fixed host-side pytest
- ✅ `.env.fa.template` — Removed stale `/workspace` reference
- ✅ `knowledge/templates/fa.env.template` — Removed stale `/workspace` reference
- ✅ `src/fa/feature_flags.py` — Declared phantom flag
- ✅ `tests/test_dead_flags.py` — Updated for 13 fields, 0 phantom
- ✅ `tests/test_subagent_termination_wiring.py` — Fixed 5 tests
