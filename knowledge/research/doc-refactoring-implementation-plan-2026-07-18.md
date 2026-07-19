# Documentation Refactoring Implementation Plan

> **Created:** 2026-07-18  
> **Purpose:** Criterion #8 — docs update for authoring-hardening workplan  
> **Scope:** Restructure agent-facing documentation to reflect session_db authority model, create `worklogs/`, condense core docs, convert MAINTENANCE to skill  
> **Verifiable:** Every step has a verification command

---

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Core doc set | 3 files: AGENTS.md, project-overview.md (rename), reference.md (merged) | Agent reads 3 files max for session bootstrap; currently 8+ fragmented |
| architecture.md | Prune — salvage insights into reference.md | Agent never references it per user observation; 273 lines of conceptual reference unused in sessions |
| FEATURES.md | Merge into reference.md; content also feeds new README.md | Redundant with both glossary and README pitch |
| glossary.md | Merge into reference.md | Combined with features + architecture insights = single lookup file |
| 02-operations.md | Prune from agent routing surface (llms.txt, knowledge/README.md). File stays for human operators | 1105-line Russian AIO manual — not agent-facing. Session data layout section extracts into reference.md |
| llms.txt | Legacy routing fallback — minimal update only | New DB interactions (blackboard.query) are untested; don't oversell |
| README.md | Becomes rich flashy project presentation (current FEATURES.md style + badges + diagram) | User request: "readme should become a rich flashy presentation" |
| worklogs/ | Flat + archive structure | User chose this; dump finished items unsorted in archive, clean structure for active work |
| HANDOFF.md | Move to worklogs/ (no stub) | User chose no stub; update all refs |
| MAINTENANCE.md | Convert to skill (session closure) | User wants agent to read this as a skill at session end, increasing compliance |
| Anti-patterns | Keep all 4, add AP-005 | Keep and integrate per user decision |
| ADR-4/7/14 | Defer amendments | Not priority per user |
| Codemaps | Defer (codegraph later) | Not priority per user |
| Prompts | Defer formalization | Not priority per user |
| Trace | Defer pruning | Not priority per user |
| session_db authority | Current truth + dual-role note | Docs reflect code as-is: SQLite = authority, JSONL = human-readability mirror |

---

## Phase 0 — Reconnaissance (no edits)

### Step 0.1: Extract salvageable content from architecture.md

Read architecture.md and identify content worth preserving:
- [ ] §Трёхслойная модель (3-layer model) — core conceptual model, referenced from 2 research notes
- [ ] §Базовые паттерны (П1 Feedback Loop, П2 Planning, П3 Escalation, П4 Knowledge accumulation)
- [ ] §Архитектура памяти table (working/persistent/procedural/episodic → CogSci mapping)
- [ ] §Provenance и chain of custody — already covered in project-overview.md §1.2.5 and knowledge/README.md
- [ ] §Стабильное vs volatile знание table — useful, short
- [ ] §Чему учит Agent (what works/poorly) — general advice, not FA-specific
- [ ] §Правило 80% — general advice

**Salvage decision:** Move П1-П4 patterns, memory taxonomy table, stable/volatile table into reference.md §Patterns. The 3-layer model is already implicit in AGENTS.md and ADR-7; a 2-line summary suffices. Provenance is already in project-overview. General advice (80% rule, what works) does not save search rounds or tool calls — prune.

### Step 0.2: Extract session data layout from 02-operations.md

Identify the session data structure information that agents need:
- [ ] Session run directory layout (~/.fa/session-log/<run_id>/)
- [ ] Workspace artifacts layout (<workspace>/.fa/)
- [ ] Cross-run artifacts (~/.fa/global_history.db, config.yaml, models.yaml)
- [ ] `fa stats --global-history` usage

This is ~50 lines of new content for reference.md. The 1105-line operations manual stays as a file but is removed from agent routing.

### Step 0.3: Map all cross-references for moves

Files that will move and need reference updates:

| File moving | New location | Ref count (grep) |
|-------------|-------------|-------------------|
| HANDOFF.md | worklogs/HANDOFF.md | ~40 refs |
| knowledge/BACKLOG.md | worklogs/BACKLOG.md | ~15 refs |
| knowledge/pr-notes/ | worklogs/pr-notes/ | ~8 refs |
| knowledge/MAINTENANCE.md | (deleted, replaced by skill) | ~19 refs |
| knowledge/architecture.md | (deleted, salvaged) | ~6 agent-facing refs |
| knowledge/glossary.md | (deleted, merged) | ~27 refs |
| knowledge/overview/FEATURES.md | (deleted, merged) | ~4 refs |
| knowledge/loop-improvement-workplan.md | worklogs/implementation-plans/ | ~5 refs |
| knowledge/mutation-survivors-workplan.md | worklogs/implementation-plans/ | ~3 refs |
| knowledge/review-stage-0-0.5-vs-plan.md | worklogs/archive/ | ~2 refs |
| knowledge/STAGE_0_0.5_VERIFICATION.md | worklogs/archive/ | ~1 ref |
| knowledge/STAGE_1_VERIFICATION.md | worklogs/archive/ | ~1 ref |

**Verification:** `grep -rn '<old-path>' --include='*.md' --include='*.txt' --include='*.yaml' . | wc -l` before and after

### Step 0.4: Identify research/ notes to move to worklogs

Session work artifacts currently in knowledge/research/ that belong in worklogs/:

**→ worklogs/implementation-plans/:**
- `authoring-hardening-workplan-v2-2026-07-16.md`
- `fa-workflow-loop-implementation-plan-2026-06-29.md`
- `fa-workflow-operator-maintainer-next-actions-memo-2026-06-30.md`
- `substrate-modernization-plan-2026-07-14.md`
- `substrate-gap-closure-workplan-round2-2026-07-15.md`
- `substrate-slice0-slice1-implementation-plan-2026-07-15.md`
- `substrate-slice2-patch-design-2026-07-15.md`
- `substrate-slice3-patch-design-2026-07-15.md`
- `substrate-slice4-patch-design-2026-07-15.md`
- `adr-13-14-implementation-plan-2026-07-11-v3-reduced.md`
- `phase1-foundation-detailed-implementation-plan.md`
- `loop-improvement-workplan.md` (from knowledge/ root)
- `mutation-survivors-workplan.md` (from knowledge/ root)

**→ worklogs/archive/ (finished work, unsorted):**
- `task-completion-session-2026-07-16.md`
- `task-declaration-session-2026-07-16.md`
- `state-assessment-2026-07-16.md`
- `tier1-declaration-2026-07-16.md`
- `review-stage-0-0.5-vs-plan.md` (from knowledge/ root)
- `STAGE_0_0.5_VERIFICATION.md` (from knowledge/ root)
- `STAGE_1_VERIFICATION.md` (from knowledge/ root)
- `ci-guardrails-reference.md` (from knowledge/ root)
- `substrate-decision-freeze-2026-07-15.md`
- `substrate-slice1-closure-pass-and-slice2-init-2026-07-15.md`
- `substrate-slice5-6-7-closure-2026-07-15.md`
- `substrate-slice9-closure-2026-07-15.md`
- `substrate-slice9-patch-design-2026-07-15.md`
- `substrate-state-assessment-2026-07-15-round3.md`
- `phase1-closure-review-wiring.md`
- `phase1-foundation-final-decisions.md`
- `phase1-foundation-review-gaps.md`
- `authoring-hardening-workplan-2026-07-16.md` (superseded by v2)
- `next-session-context-bundle.md`

**Stay in knowledge/research/:** All cross-reference notes, inspiration notes, ADR research, architecture research, deployment research. These are reference material, not session work artifacts.

---

## Phase 1 — Create reference.md (merged glossary + features + architecture salvage + session_db)

**This is the keystone edit.** One file replaces three deleted files and adds new session_db content.

### Step 1.1: Create knowledge/reference.md

Structure:

```markdown
# Reference — Terms, Features, and Session Architecture

> Single lookup file for agents. Replaces glossary.md, FEATURES.md, and architecture.md.
> For routing, see AGENTS.md §Query Routing. For vision/axes, see project-overview.md.

## § Terms

[All glossary.md entries, preserving table format. Add new entries below.]

### New terms (session_db authority model)

| Term | Description |
|------|-------------|
| **SessionDatabase** | Per-run authoritative SQLite database at `~/.fa/session-log/<run_id>/session.db`. Three tables: `event_log` (authoritative events), `blackboard` (content-hashed entries with read_set/write_set), `session_meta` (key-value metadata). Thread-safe via `threading.Lock` + short-lived connections + WAL. Created by `EventLog.__init__`, shared with `Blackboard` and `SessionState`. |
| **Blackboard** | Typed append-only content-hashed store for session state. Entries carry `id`, `type`, `content_hash`, `read_set`, `write_set`, `assumptions`, `version_dependencies`. Writes to `session.db.blackboard` (authority) + `workspace/.fa/blackboard/blackboard.jsonl` (best-effort mirror). Cannot exist without `SessionDatabase`. Gated by `FeatureFlags.blackboard_enabled` (default `True`). Conflict detection via `detect_conflict()` checks read/write set overlaps. |
| **Transaction** | Accumulates `read_set`/`write_set` during a session. Always initialized (unlike Blackboard, which is conditional). Feeds into Blackboard entries for conflict detection. |
| **ArtifactStore** | Content-addressed store at `<workspace>/.fa/artifacts/`. Stores elided tool result payloads as `tool-result-<sha256[:16]>.json`. Keeps event_log lean. |
| **GlobalHistoryStore** | Derived analytics projection at `~/.fa/global_history.db`. Single `runs` table with per-run summary (tokens, cost, duration, tool breakdown). Populated at session end, best-effort, never crashes main. Active consumer: `fa stats --global-history`. NOT imported by hot-path code for correctness. |
| **Dual-write authority** | Write discipline: (1) write to SQLite authority first (raises on failure), (2) advance state only after commit, (3) write JSONL mirror best-effort. Both `EventLog` and `Blackboard` follow this pattern. JSONL is the primary human-readability surface; SQLite is the machine authority. |
| **ContextVar DI** | Dependency injection pattern via `contextvars.ContextVar`. `set_current_session(state)` in `drive_session()`; tool handlers call `get_current_session()` → access `session.blackboard`, `session.session_db`, etc. Decouples tools from session lifecycle. |
| **FeatureFlags** | Runtime feature toggles loaded from `~/.fa/config.yaml`. 13 fields, all with production consumers. Gate Blackboard and Telemetry initialization. Defaults safe (blackboard_enabled=True, telemetry_enabled=True). |
| **EventLog** | Append-only event writer. Creates `SessionDatabase` at init. `append()` writes to `session_db.append_event_row()` (authority) + `events.jsonl` (mirror). `read_all()` reads from DB first, falls back to JSONL. |

## § Features

[FEATURES.md content, updated. Key new features:]

### Session Database Authority

Every `fa run` session creates a per-run SQLite database (`session.db`) that is the single source of truth for hot-path runtime state:

- **event_log table** — every tool call, LLM interaction, system event. Authoritative; `events.jsonl` is a best-effort mirror for `cat`/`grep`/`diff`.
- **blackboard table** — content-hashed entries with read_set, write_set, assumptions, version_dependencies. Conflict detection before write. `blackboard.jsonl` is a best-effort mirror.
- **session_meta table** — key-value metadata.

JSONL files exist as human-readable mirrors for ad-hoc inspection. They are NOT authoritative — if they disagree with session.db, session.db wins.

### Blackboard Conflict Detection

When `edit_file` or `write_file` writes, the Blackboard checks for conflicts: if entry B's `read_set` overlaps with a prior entry A's `write_set`, and A was written after B started reading, `detect_conflict()` returns a structured failure. This prevents the "parent HEAD switched" bug (Claude #55708).

### Cross-Run Analytics

`fa stats --global-history` reads from `~/.fa/global_history.db` — a derived projection populated at session end. Not hot-path authority; purely analytics.

## § Patterns

[Salvaged from architecture.md — only content that saves search rounds or tool calls:]

### Feedback Loop (П1)

Action → Observation → Reflection → Next Action. The core agent pattern. Tests after edits, linter, typechecker = the feedback loop made deterministic.

### Planning Before Execution (П2)

1. Parse requirements. 2. Explore codebase. 3. Plan (files, risks, tests). 4. Execute step-by-step. 5. Deliver.

### Memory Taxonomy

| Type | Purpose | FA Location | CogSci Analog |
|------|---------|-------------|---------------|
| Session | Current task context | SessionState, observations | Working |
| Persistent | Cross-session facts | knowledge/ (filesystem-canon) | Semantic |
| Procedural | Step-by-step procedures | skills/ (SKILL.md) | Procedural |
| Episodic | Session outcomes | global_history.db, HANDOFF.md | Episodic |

### Stable vs Volatile Knowledge

| Type | Location | Policy |
|------|----------|--------|
| Stable (architecture, ADRs, glossary) | knowledge/adr/, knowledge/ | Synthesize once at review, rarely changes |
| Semi-stable (research) | knowledge/research/ | Update on significant findings |
| Volatile (session logs) | ~/.fa/session-log/ | Synthesize only on demand; project to global_history.db |

## § Session Data Layout

[Extracted from 02-operations.md + new session_db content:]

### Per-run artifacts (~/.fa/session-log/<run_id>/)

| File | Role | Authority? |
|------|------|-----------|
| `session.db` | SQLite authority: event_log + blackboard + session_meta tables | **Yes** |
| `events.jsonl` | JSONL mirror of event_log | No (best-effort) |
| `pr_draft.md` | PR draft artifact | Standalone |
| `eval_report.json` | Workflow eval verdict | Standalone |
| `flow_state.json` | Workflow controller state | Standalone |
| `attempt_history.json` | Recovery attempt log | Standalone |

### Workspace artifacts (<workspace>/.fa/)

| Path | Role | Authority? |
|------|------|-----------|
| `blackboard/blackboard.jsonl` | JSONL mirror of session.db.blackboard | No (best-effort) |
| `artifacts/` | Content-addressed tool result offloads | Complements event_log |
| `subagents/<task_id>.json` | Subagent spawn results | Standalone |
| `fts.db` | FTS5 full-text search index | Disposable cache |

### Cross-run artifacts

| Path | Role |
|------|------|
| `~/.fa/global_history.db` | Derived analytics projection (runs table). `fa stats --global-history` |
| `~/.fa/config.yaml` | FeatureFlags + runtime config |
| `~/.fa/models.yaml` | Unified routing config |

### Initialization chain

```
fa run → _cmd_run() → EventLog(path, run_id) → SessionDatabase(session.db)
       → SessionState(log, run_id, workspace) → __post_init__:
           session_db = log.session_db  (shared instance!)
           FeatureFlags loaded from ~/.fa/config.yaml
           Transaction created
           ArtifactStore lazy-init
           Blackboard lazy-init (requires session_db + feature flag)
           TelemetryLogger lazy-init
       → drive_session(state) → set_current_session(state)
       → Tool handlers: get_current_session() → session.blackboard, session.session_db, ...
```

### Authority hierarchy

1. **session.db** — single source of truth for hot-path runtime state
2. **JSONL mirrors** — best-effort, human-readable, for audit/diff
3. **global_history.db** — derived projection, never imported for correctness
4. **File artifacts** — standalone, not replicated in DB
```

**Verification:** `wc -l knowledge/reference.md` should be ~350-400 lines. `grep -c '^| \*\*' knowledge/reference.md` should have all original glossary entries + 9 new ones.

### Step 1.2: Update AGENTS.md references to point to reference.md

Replace all `knowledge/glossary.md` → `knowledge/reference.md` §Terms  
Replace all `knowledge/architecture.md` → `knowledge/reference.md` §Patterns  
Remove `knowledge/overview/FEATURES.md` references → `knowledge/reference.md` §Features  
Update §Query Routing table, §Pre-flight Step 2, §Session close

**Verification:** `grep -rn 'glossary\.md\|architecture\.md\|FEATURES\.md' AGENTS.md` returns 0

---

## Phase 2 — Update core docs with session_db authority

### Step 2.1: Update AGENTS.md

Specific edits:
1. **§Project Overview** — add line about session_db as per-run authority
2. **§Repository Structure** — add `worklogs/` entry, update knowledge/ description
3. **§Pre-flight Step 2** — update grep target to `reference.md` §Terms
4. **§Context-budget discipline** — add note that session.db reduces context need (query vs full scan)
5. **§Query Routing** — add row: "Session state / event history" → `reference.md` §Session Data Layout
6. **§Querying Artifacts** — update: mention session.db as authority explicitly, note JSONL is mirror
7. **§Session close** — add "load doc-maintenance skill" instruction
8. **§Loadable skills** — add doc-maintenance row
9. **Update HANDOFF.md path** → `worklogs/HANDOFF.md`

**Verification:** `grep -c 'session_db\|SessionDatabase\|authority' AGENTS.md` ≥ 5

### Step 2.2: Update project-overview.md (consider rename)

User wants "short and sound name." Candidates: `conventions.md`, `vision.md`, `charter.md`.  
**Decision needed from user on name.** For now, plan edits regardless of filename.

Specific edits:
1. **§6 Key constraints** — update storage: "SQLite per-run session.db is authoritative for hot-path state; filesystem-canon Markdown remains authoritative for durable knowledge. JSONL files are best-effort mirrors."
2. **§1.2.6 Substrate Formality** — note that Blackboard (session.db.blackboard table) now implements I-6.1 through I-6.4
3. **§2 Users** — mention that agent documentation audience now has `reference.md` as single lookup

**Verification:** `grep -c 'session\.db\|SessionDatabase' knowledge/project-overview.md` ≥ 2

### Step 2.3: Update llms.txt (minimal — legacy fallback)

Specific edits:
1. **§MUST READ FIRST** — replace `knowledge/glossary.md` with `knowledge/reference.md`
2. **§FORMAL SUBSTRATE** — add note: "session.db is SQLite authority per run. JSONL files are best-effort mirrors. See reference.md §Session Data Layout for full schema."
3. **§BY-DEMAND INDEX** — note that `knowledge/architecture.md`, `knowledge/glossary.md`, `knowledge/overview/FEATURES.md` are removed (merged into `reference.md`)
4. **Update paths** for moved files (HANDOFF.md → worklogs/, BACKLOG.md → worklogs/, etc.)

**Verification:** `grep -c 'reference\.md' knowledge/llms.txt` ≥ 2

### Step 2.4: Update knowledge/README.md

Specific edits:
1. **Layout tree** — remove architecture.md, glossary.md, FEATURES.md, MAINTENANCE.md entries; add reference.md; add worklogs/ note
2. **What goes where table** — add row for reference.md; update routing
3. **Conventions** — note that MAINTENANCE.md moved to skill
4. **Update paths** for moved files

**Verification:** `grep -c 'reference\.md' knowledge/README.md` ≥ 2; `grep -c 'glossary\.md\|architecture\.md\|MAINTENANCE\.md' knowledge/README.md` = 0

---

## Phase 3 — Create worklogs/ and move files

### Step 3.1: Create worklogs/README.md

```markdown
# Worklogs — Session Work Artifacts

> Purpose: Condense all artifacts related to working in sessions and their outputs.
> This directory is the working surface; knowledge/ is the reference surface.

## Structure

worklogs/
├── README.md              # this file
├── HANDOFF.md             # cross-session bootstrap (read first every session)
├── BACKLOG.md             # active milestones and tracked items
├── pr-notes/              # PR notes (moved from knowledge/pr-notes/)
├── implementation-plans/  # active and recent implementation plans
└── archive/               # finished work, unsorted (prune freely)

## How to use

1. **Every session starts here:** Read HANDOFF.md → BACKLOG.md → active plans.
2. **Every session ends here:** Update HANDOFF.md, load doc-maintenance skill.
3. **Archive rule:** If a plan/note is >30 days old and no active work references it, move to archive/.
4. **Prune rule:** Archive items >90 days old with no cross-references can be deleted.
5. **Cross-references:** When moving files, update all refs per doc-maintenance skill.

## What goes where

| If it is… | Put it in… |
|---|---|
| Cross-session state (gotchas, landmarks, next priorities) | `HANDOFF.md` |
| A tracked milestone or backlog item | `BACKLOG.md` |
| A PR note | `pr-notes/` |
| An active implementation plan | `implementation-plans/` |
| A finished plan, review, or session closure note | `archive/` |
| A research finding or architecture decision | `knowledge/research/` or `knowledge/adr/` (NOT here) |
```

**Verification:** `test -f worklogs/README.md`

### Step 3.2: Move HANDOFF.md → worklogs/HANDOFF.md

```bash
git mv HANDOFF.md worklogs/HANDOFF.md
```

No stub at root. Update ALL references:

```bash
# Find all references
grep -rn 'HANDOFF.md' --include='*.md' --include='*.txt' --include='*.yaml' . | grep -v __pycache__
# Update each: HANDOFF.md → worklogs/HANDOFF.md
```

Key files to update:
- AGENTS.md (~6 refs)
- knowledge/llms.txt (~3 refs)
- knowledge/README.md (~2 refs)
- knowledge/MAINTEN.md → skill (being replaced)
- knowledge/adr/DIGEST.md
- knowledge/skills/*/SKILL.md
- README.md (~3 refs)
- .pre-commit-config.yaml (if any)

**Verification:** `grep -rn '"HANDOFF.md"\|(/HANDOFF.md\|](./HANDOFF.md' . --include='*.md' --include='*.txt' --include='*.yaml' | grep -v __pycache__ | grep -v worklogs/` returns 0

### Step 3.3: Move BACKLOG.md → worklogs/BACKLOG.md

```bash
git mv knowledge/BACKLOG.md worklogs/BACKLOG.md
```

Update refs in: HANDOFF.md, AGENTS.md, llms.txt, knowledge/README.md, skills/, ADRs.

**Verification:** `grep -rn 'knowledge/BACKLOG.md' --include='*.md' --include='*.txt' | grep -v __pycache__` returns 0

### Step 3.4: Move knowledge/pr-notes/ → worklogs/pr-notes/

```bash
git mv knowledge/pr-notes/ worklogs/pr-notes/
```

Update refs in: llms.txt, knowledge/README.md, AGENTS.md (if any), README.md.

**Verification:** `grep -rn 'knowledge/pr-notes' --include='*.md' --include='*.txt' | grep -v __pycache__` returns 0

### Step 3.5: Move implementation plans → worklogs/implementation-plans/

```bash
mkdir -p worklogs/implementation-plans
git mv knowledge/loop-improvement-workplan.md worklogs/implementation-plans/
git mv knowledge/mutation-survivors-workplan.md worklogs/implementation-plans/
# Research notes that are implementation plans:
git mv knowledge/research/authoring-hardening-workplan-v2-2026-07-16.md worklogs/implementation-plans/
git mv knowledge/research/fa-workflow-loop-implementation-plan-2026-06-29.md worklogs/implementation-plans/
git mv knowledge/research/fa-workflow-operator-maintainer-next-actions-memo-2026-06-30.md worklogs/implementation-plans/
git mv knowledge/research/substrate-modernization-plan-2026-07-14.md worklogs/implementation-plans/
git mv knowledge/research/substrate-gap-closure-workplan-round2-2026-07-15.md worklogs/implementation-plans/
git mv knowledge/research/substrate-slice0-slice1-implementation-plan-2026-07-15.md worklogs/implementation-plans/
git mv knowledge/research/substrate-slice2-patch-design-2026-07-15.md worklogs/implementation-plans/
git mv knowledge/research/substrate-slice3-patch-design-2026-07-15.md worklogs/implementation-plans/
git mv knowledge/research/substrate-slice4-patch-design-2026-07-15.md worklogs/implementation-plans/
git mv knowledge/research/adr-13-14-implementation-plan-2026-07-11-v3-reduced.md worklogs/implementation-plans/
git mv knowledge/research/phase1-foundation-detailed-implementation-plan.md worklogs/implementation-plans/
```

Update refs in: HANDOFF.md, llms.txt, BACKLOG.md.

**Verification:** `ls worklogs/implementation-plans/` has ≥10 files

### Step 3.6: Move finished work → worklogs/archive/

```bash
mkdir -p worklogs/archive
# Knowledge root items
git mv knowledge/review-stage-0-0.5-vs-plan.md worklogs/archive/
git mv knowledge/STAGE_0_0.5_VERIFICATION.md worklogs/archive/
git mv knowledge/STAGE_1_VERIFICATION.md worklogs/archive/
git mv knowledge/ci-guardrails-reference.md worklogs/archive/
# Research notes that are finished session artifacts
git mv knowledge/research/task-completion-session-2026-07-16.md worklogs/archive/
git mv knowledge/research/task-declaration-session-2026-07-16.md worklogs/archive/
git mv knowledge/research/state-assessment-2026-07-16.md worklogs/archive/
git mv knowledge/research/tier1-declaration-2026-07-16.md worklogs/archive/
git mv knowledge/research/substrate-decision-freeze-2026-07-15.md worklogs/archive/
git mv knowledge/research/substrate-slice1-closure-pass-and-slice2-init-2026-07-15.md worklogs/archive/
git mv knowledge/research/substrate-slice5-6-7-closure-2026-07-15.md worklogs/archive/
git mv knowledge/research/substrate-slice9-closure-2026-07-15.md worklogs/archive/
git mv knowledge/research/substrate-slice9-patch-design-2026-07-15.md worklogs/archive/
git mv knowledge/research/substrate-state-assessment-2026-07-15-round3.md worklogs/archive/
git mv knowledge/research/phase1-closure-review-wiring.md worklogs/archive/
git mv knowledge/research/phase1-foundation-final-decisions.md worklogs/archive/
git mv knowledge/research/phase1-foundation-review-gaps.md worklogs/archive/
git mv knowledge/research/authoring-hardening-workplan-2026-07-16.md worklogs/archive/
git mv knowledge/research/next-session-context-bundle.md worklogs/archive/
```

**Verification:** `ls worklogs/archive/` has ≥17 files

---

## Phase 4 — Delete merged/pruned files

### Step 4.1: Delete files whose content is now in reference.md

```bash
git rm knowledge/glossary.md
git rm knowledge/architecture.md
git rm knowledge/overview/FEATURES.md
```

All content salvaged into reference.md in Phase 1.

**Verification:** Content comparison — `grep '^| \*\*' knowledge/reference.md | wc -l` should be ≥ original glossary entry count (86) + 9 new entries

### Step 4.2: Remove 02-operations.md from agent routing

File stays on disk but is removed from agent routing surfaces:
- Remove from llms.txt §BY-DEMAND INDEX / §TASK ROUTING
- Remove from knowledge/README.md layout tree
- Keep in knowledge/instructions/ (human operators still need it)
- Update knowledge/instructions/README.md to clarify: "01-install and 02-operations are for human operators, not agent routing"

**Verification:** `grep -c '02-operations' knowledge/llms.txt` = 0; `test -f knowledge/instructions/02-operations.md` passes

### Step 4.3: Delete MAINTENANCE.md (replaced by skill in Phase 5)

```bash
git rm knowledge/MAINTENANCE.md
```

Content moved to knowledge/skills/doc-maintenance/SKILL.md (Phase 5).

**Verification:** `test -f knowledge/MAINTENANCE.md` fails; `test -f knowledge/skills/doc-maintenance/SKILL.md` passes

---

## Phase 5 — MAINTENANCE → skill

### Step 5.1: Create knowledge/skills/doc-maintenance/SKILL.md

```markdown
---
purpose: Session closure and doc hygiene discipline
trigger: At session close, or when moving/pruning/adding any file under knowledge/ or worklogs/
last-reviewed: 2026-07-18
---

# Doc Maintenance Skill

## Trigger

Load this skill at session close, or before any file move/prune/archive operation under `knowledge/` or `worklogs/`.

## §When closing a session

1. Update `worklogs/HANDOFF.md` per its §Session Protocol (overwrite §Current state, rewrite §Next).
2. If any new file was added under `knowledge/` or `worklogs/`, add a row to `knowledge/llms.txt` §BY-DEMAND INDEX.
3. If any ADR was amended, update `knowledge/adr/DIGEST.md` and append to `knowledge/trace/exploration_log.md`.
4. Run `grep -rn '<old-path>' .` for any files moved/renamed/deleted — fix every reference.
5. Verify: `python scripts/check_doc_links.py` passes.

## §When archiving a research note

1. Add `> **Status:** archived 2026-MM-DD` banner at top.
2. Add `superseded_by:` frontmatter if applicable.
3. Update `knowledge/llms.txt` — re-path or remove the row.
4. Cross-check `worklogs/HANDOFF.md` §Current state — replace citation with superseding artifact.
5. Cross-check `knowledge/adr/DIGEST.md` — retarget any Inputs bullet.
6. Cross-check `knowledge/reference.md` §Terms — retarget any See: link.

## §When moving or pruning a doc

**The one hard rule: no dangling links.** In the same PR:

1. `grep -rn '<old-filename>' .` to find every reference.
2. For a move/rename: re-path every reference. Adjust link depth.
3. For a deletion: remove refs or retarget to superseding artifact. Drop llms.txt row.
4. Update `knowledge/llms.txt`, `worklogs/HANDOFF.md` (active links only), `knowledge/reference.md`, and file indexes.
5. Verify: `python scripts/check_doc_links.py` passes and `grep -rn '<old-path>'` returns nothing.

## §When adding a new file under knowledge/ or worklogs/

1. Add a row in `knowledge/llms.txt` §BY-DEMAND INDEX under matching folder section.
2. Row format: `[path/to/file.md]: description.` Description ≤200 chars.
3. For files >1200 LoC add size tag: `[path/to/file.md] (Large)`.
4. If the file has an ADR cross-reference, update DIGEST.md.
5. If the file introduces a new term, add to `knowledge/reference.md` §Terms.

## §When merging an ADR amendment

1. Update `knowledge/adr/DIGEST.md` — extend the Amendments bullet.
2. Append to `knowledge/trace/exploration_log.md` per pr-creation skill rule #9.
3. Cross-check `worklogs/HANDOFF.md` §Current state ADR list.
```

**Verification:** `test -f knowledge/skills/doc-maintenance/SKILL.md` passes

### Step 5.2: Add trigger row to AGENTS.md §Loadable skills

Add row:

| Skill | Trigger and scope |
| :--- | :--- |
| [`doc-maintenance`](./knowledge/skills/doc-maintenance/SKILL.md) | **Trigger:** At session close, or when moving/pruning/adding any file under `knowledge/` or `worklogs/`.<br><br>Ensures link integrity, llms.txt updates, and HANDOFF freshness. Replaces former `knowledge/MAINTENANCE.md` routing file. |

**Verification:** `grep -c 'doc-maintenance' AGENTS.md` ≥ 1

### Step 5.3: Update all MAINTENANCE.md references

19 references found in Phase 0.3. Update each:
- `.pre-commit-config.yaml` → point to skill
- `AGENTS.md` → point to skill
- `worklogs/HANDOFF.md` → point to skill
- `worklogs/BACKLOG.md` → point to skill
- `knowledge/reference.md` → point to skill (replacing glossary entry)
- `knowledge/llms.txt` → point to skill
- `knowledge/anti-patterns/AP-002-*` → point to skill
- `knowledge/anti-patterns/README.md` → point to skill

**Verification:** `grep -rn 'MAINTENANCE\.md' --include='*.md' --include='*.txt' --include='*.yaml' . | grep -v __pycache__` returns 0

---

## Phase 6 — Anti-patterns integration

### Step 6.1: Add AP-005

Create `knowledge/anti-patterns/AP-005-dual-write-authority-violation.md`:

```markdown
---
compiled: 2026-07-18
applies_to: ADR-7 (EventLog), ADR-14 (EventStream), Phase 0.5 Blackboard
---

# AP-005 — Dual-write authority violation

## §Symptom

Tool handler writes to JSONL file but the corresponding `session.db` row is missing or stale. Agent reads from JSONL mirror and gets a different answer than code reading from SQLite authority.

## §Wrong shape

Writing to the JSONL mirror only (or writing to JSONL first, then SQLite), so that the human-readable file and the machine authority diverge on crash or partial failure.

## §Right shape

Always write to SQLite authority first. Only after the authoritative commit succeeds, advance logical state and write the JSONL mirror best-effort. If SQLite write fails, raise RuntimeError — do NOT silently fall through to JSONL-only write.

## §Why the wrong shape dominates

JSONL is the file operators see (`cat events.jsonl`). It "feels" like the primary artifact because it's human-readable. The SQLite DB is invisible. This visibility asymmetry makes JSONL-first writing the intuitive default.

## §Detection

- `session_db.append_event_row()` raises RuntimeError if session_db is None — this is the enforcement point.
- Blackboard.write() writes to session_db first, JSONL second.
- Test: `test_event_log_authority_write_before_jsonl` — verify JSONL is empty when SQLite write fails.

## §Linked-ADR

ADR-7 §7 (Trace), Phase 0.5 Blackboard design

## §Evidence

src/fa/inner_loop/state.py:166-174 (EventLog.append authority-first discipline)
src/fa/blackboard/blackboard.py (Blackboard.write authority-first discipline)
```

### Step 6.2: Update anti-patterns/README.md index

Add AP-005 row to the index table.

**Verification:** `grep -c 'AP-005' knowledge/anti-patterns/README.md` ≥ 1

---

## Phase 7 — Update README.md (rich project presentation)

### Step 7.1: Rewrite README.md as flashy presentation

Merge current README.md + FEATURES.md content into a single rich presentation:
- Keep badges
- Keep mermaid diagram (update to reflect worklogs/ structure)
- Add session_db authority section (brief, visual)
- Update "How to work with this repo" section with new file paths
- Add link to knowledge/reference.md as "single lookup"
- Update folder listing to reflect new structure

**Verification:** `wc -l README.md` ≈ 150-180 lines; `grep -c 'session.db\|SessionDatabase' README.md` ≥ 1

---

## Phase 8 — Cross-reference sweep and verification

### Step 8.1: Full grep sweep for broken references

```bash
# Find any remaining references to moved/deleted files
for old_path in \
  'knowledge/glossary.md' \
  'knowledge/architecture.md' \
  'knowledge/overview/FEATURES.md' \
  'knowledge/MAINTENANCE.md' \
  'knowledge/BACKLOG.md' \
  'HANDOFF.md' \
  'knowledge/pr-notes/' \
  'knowledge/loop-improvement-workplan.md' \
  'knowledge/mutation-survivors-workplan.md' \
  'knowledge/review-stage-0-0.5-vs-plan.md' \
  'knowledge/STAGE_0_0.5_VERIFICATION.md' \
  'knowledge/STAGE_1_VERIFICATION.md' \
  'knowledge/ci-guardrails-reference.md'; do
  count=$(grep -rn "$old_path" --include='*.md' --include='*.txt' --include='*.yaml' . 2>/dev/null | grep -v __pycache__ | grep -v '.pyc' | wc -l)
  echo "$old_path: $count remaining refs"
done
```

Target: 0 remaining refs for all paths.

### Step 8.2: Run doc link checker

```bash
python scripts/check_doc_links.py
```

Target: 0 broken links.

### Step 8.3: Verify agent bootstrap still works

Read the 5 MUST-READ-FIRST files in order and verify they form a coherent bootstrap:
1. AGENTS.md ✓ (updated)
2. knowledge/project-overview.md ✓ (updated)
3. worklogs/HANDOFF.md ✓ (moved)
4. knowledge/adr/DIGEST.md ✓ (unchanged)
5. knowledge/reference.md ✓ (new, replaces glossary)

### Step 8.4: Smoke test

```bash
cd /home/user/First-Agent-dev
# Verify no broken imports in code that references docs
grep -rn 'glossary\|MAINTENANCE\.md\|architecture\.md' src/ tests/ --include='*.py' | grep -v __pycache__
# Should return 0 (code shouldn't reference these files)
```

---

## Open decision: project-overview.md rename

User wants "short and sound name." Options:

| Name | Pros | Cons |
|------|------|------|
| `project-overview.md` | Already known, no rename churn | Long, doesn't convey "vision/convention" |
| `conventions.md` | Short, clear purpose | Misleading — it's more than conventions (has pillars, principles, scope) |
| `vision.md` | Short, aspirational | Vague; could be confused with a roadmap |
| `charter.md` | Short, formal, implies binding principles | Overly formal for a single-user project |

**Recommendation:** Keep `project-overview.md` — the name is descriptive, it's deeply cross-referenced from ~20 files, and renaming adds churn without clear benefit. The "short and sound" quality comes from content, not filename.

---

## Execution order

The phases must execute in this order due to dependencies:

```
Phase 0 (recon) → Phase 1 (reference.md) → Phase 2 (core doc updates)
                                              ↓
                 Phase 3 (worklogs/) ──────── → Phase 4 (deletes)
                                              ↓
                 Phase 5 (skill) ─────────── → Phase 6 (anti-patterns)
                                              ↓
                 Phase 7 (README) ────────── → Phase 8 (verification)
```

Phases 3 and 5 can run in parallel after Phase 2 completes. Phase 7 can start after Phase 4. Phase 8 must be last.

**Estimated total:** ~25 file edits, ~30 file moves, ~50 cross-reference updates. Single PR.
