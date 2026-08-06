# Documentation Refactoring Implementation Plan — v2

> **Created:** 2026-07-18  
> **Supersedes:** doc-refactoring-implementation-plan-2026-07-16.md (v1)  
> **Purpose:** Criterion #8 — docs update for authoring-hardening workplan  
> **Scope:** Restructure agent-facing docs to reflect session_db authority, create `worklogs/`, condense core docs, convert MAINTENANCE to skill  
> **Verifiable:** Every step has a verification command

---

## Decisions Log

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Core doc set | 3 files: AGENTS.md, project-overview.md, reference.md | Agent reads 3 files max for session bootstrap |
| 2 | architecture.md | Prune — salvage insights into reference.md | Agent never references it per user observation |
| 3 | FEATURES.md | Merge into reference.md + feed README.md | Redundant with both glossary and README pitch |
| 4 | glossary.md | Merge into reference.md | Combined with features + architecture salvage = single lookup |
| 5 | llms.txt | Legacy routing fallback — minimal update only | blackboard.query untested; don't oversell |
| 6 | README.md | Rich condensed project presentation | User: "readme should become a rich condensed representation of a project in whole" |
| 7 | worklogs/ | Flat + archive structure | User chose this |
| 8 | HANDOFF.md | Move to worklogs/ (no stub) | User chose no stub |
| 9 | MAINTENANCE.md | Convert to skill (session closure) | User wants agent to load this at session end |
| 10 | Anti-patterns | Keep all 4, add AP-005 | Keep and integrate |
| 11 | ADR-4/7/14 | Defer amendments | Not priority |
| 12 | Codemaps | Defer (codegraph later) | Not priority |
| 13 | Prompts | Defer formalization | Not priority |
| 14 | Trace | Defer pruning | Not priority |
| 15 | session_db authority | Current truth + dual-role note | SQLite = authority, JSONL = human-readability mirror |

---

## Gaps Fixed from v1

| Gap | v1 error | v2 fix |
|-----|----------|--------|
| ADR-11-Blueprint | Planned to move to worklogs/ | Stays in knowledge/research/ — it's a canonical ADR reference, not a session artifact |
| authoring-hardening-workplan-v2 | Planned to move to worklogs/ immediately | Move LAST — it tracks criterion #8 itself; circular if moved mid-PR |
| ci-guardrails-reference.md | Planned to move to archive/ | Stays in knowledge/ — codemaps/ references it 8+ times, codemaps are deferred |
| knowledge/overview/ | Not mentioned | Remove empty directory after FEATURES.md deletion |
| Phase ordering | Phase 2 referenced worklogs/ paths before Phase 3 created them | Restructure: move files FIRST (Phase 2), then update all refs (Phase 3) |
| Internal links in moved files | Not updated | Add explicit step to fix relative links inside moved files |
| mutation-clearing/SKILL.md | Not updated | Add ref update for knowledge/mutation-survivors-workplan.md path change |
| worklogs/IMPLEMENTATION.md | Not present | Add — single pointer to active plan, saves directory scan |

---

## Phase 1 — Create worklogs/ directory structure

**Why first:** Moving files before editing references means all paths exist before we start updating links. This avoids broken intermediate states.

### Step 1.1: Create directory structure

```bash
mkdir -p worklogs/implementation-plans
mkdir -p worklogs/archive
touch worklogs/archive/.gitkeep
```

### Step 1.2: Create worklogs/README.md

```markdown
# Worklogs — Session Work Artifacts

> Purpose: Condense all artifacts related to working in sessions and their outputs.
> This directory is the working surface; knowledge/ is the reference surface.

## Structure

worklogs/
├── README.md              # this file
├── HANDOFF.md             # cross-session bootstrap + active work tracker (read first every session)
├── BACKLOG.md             # active milestones and tracked items
├── pr-notes/              # PR notes (moved from knowledge/pr-notes/)
├── implementation-plans/  # active and recent implementation plans
└── archive/               # finished work, unsorted (prune freely)

## How to use

1. **Every session starts here:** Read HANDOFF.md → BACKLOG.md → active plans (HANDOFF.md §Next points to them).
2. **Every session ends here:** Update HANDOFF.md; load doc-maintenance skill.
3. **Archive rule:** If a plan/note is >30 days old and no active work references it, move to archive/.
4. **Prune rule:** Archive items >90 days old with no cross-references can be deleted.
5. **Cross-references:** When moving files, update all refs per doc-maintenance skill.

## What goes where

| If it is… | Put it in… |
|---|---|
| Cross-session state (gotchas, landmarks, next priorities, active plan pointers) | HANDOFF.md |
| A tracked milestone or backlog item | BACKLOG.md |
| A PR note | pr-notes/ |
| An active implementation plan | implementation-plans/ |
| A finished plan, review, or session closure note | archive/ |
| A research finding or architecture decision | knowledge/research/ or knowledge/adr/ (NOT here) |
| A term definition or feature description | knowledge/reference.md (NOT here) |
```

**Verification:** `test -f worklogs/README.md && test -d worklogs/archive && test -d worklogs/implementation-plans`

### Step 1.3: REMOVED — HANDOFF.md serves as both pointer and tracker

HANDOFF.md already tracks current state and next priorities. Adding IMPLEMENTATION.md would duplicate that role. HANDOFF.md §Next priority list points to active implementation plans; no separate pointer file needed.

---

## Phase 2 — Move files to worklogs/

All `git mv` operations. No reference updates yet — those come in Phase 3.

### Step 2.1: Move HANDOFF.md

```bash
git mv HANDOFF.md worklogs/HANDOFF.md
```

**Internal links to fix later:** All relative paths inside HANDOFF.md (e.g., `./knowledge/` → `../knowledge/`, `./src/` → `../src/`, `./scripts/` → `../scripts/`)

**Verification:** `test -f worklogs/HANDOFF.md && ! test -f HANDOFF.md`

### Step 2.2: Move BACKLOG.md

```bash
git mv knowledge/BACKLOG.md worklogs/BACKLOG.md
```

**Internal links to fix later:** All `./` relative paths in BACKLOG.md change depth by one level.

**Verification:** `test -f worklogs/BACKLOG.md && ! test -f knowledge/BACKLOG.md`

### Step 2.3: Move pr-notes/

```bash
git mv knowledge/pr-notes/ worklogs/pr-notes/
```

**Cross-ref audit:** Almost zero external refs (only AGENTS.md line 18 mentions `/pr-notes/`). Internal refs within pr-notes are relative and will still work within the moved directory.

**Verification:** `test -d worklogs/pr-notes/ && ! test -d knowledge/pr-notes/`

### Step 2.4: Move implementation plans

```bash
# From knowledge/ root
git mv knowledge/loop-improvement-workplan.md worklogs/implementation-plans/
git mv knowledge/mutation-survivors-workplan.md worklogs/implementation-plans/

# From knowledge/research/ — these are implementation plans, not reference research
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

**Cross-ref audit:** HANDOFF.md (3 refs), BACKLOG.md (1 ref), next-session-context-bundle.md (2 refs), PR_NOTE_workflow_slices_A_to_H.md (2 refs), mutation-clearing/SKILL.md (2 refs), exploration_log.md (2 refs). All updated in Phase 3.

**Verification:** `ls worklogs/implementation-plans/ | wc -l` = 12

### Step 2.5: Move finished work to archive/

```bash
# From knowledge/ root
git mv knowledge/review-stage-0-0.5-vs-plan.md worklogs/archive/
git mv knowledge/STAGE_0_0.5_VERIFICATION.md worklogs/archive/
git mv knowledge/STAGE_1_VERIFICATION.md worklogs/archive/

# From knowledge/research/ — finished session artifacts
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

**NOT moved (stays in knowledge/research/):**
- `ADR-11-Authoring-Guardrails-Blueprint.md` — canonical ADR reference, not a session artifact. Referenced from ADR-11 (5×), DIGEST, exploration_log.
- `authoring-hardening-workplan-v2-2026-07-16.md` — tracks criterion #8 itself. Circular to move mid-PR. Move in follow-up session.
- All cross-reference notes, inspiration notes, ADR research, architecture research, deployment research — these are reference material.

**Cross-ref audit:** Archive files have minimal external refs (mainly internal cross-references to each other). No active agent routing points at these.

**Verification:** `ls worklogs/archive/ | grep -v .gitkeep | wc -l` = 18

### Step 2.6: Fix relative links inside moved files

After moving, all relative paths inside the moved files change depth. For files moved from repo root → worklogs/:
- `./knowledge/` → `../knowledge/`
- `./src/` → `../src/`
- `./scripts/` → `../scripts/`

For files moved from knowledge/research/ → worklogs/implementation-plans/:
- `../` → `../../` (two levels up to repo root)
- `../research/` → `../../research/`

For files moved from knowledge/ → worklogs/:
- `./` references → `../knowledge/` (one level deeper)

**Approach:** For each moved file, run `grep -n '](\.\.' <file>` to find relative links, then fix. This is mechanical but must be done per-file.

**Verification per file:** `python scripts/check_doc_links.py` passes for each moved file.

---

## Phase 3 — Update all cross-references for moves

Single pass through all files that reference moved paths.

### Step 3.1: HANDOFF.md references

Files referencing `HANDOFF.md` at root (grep found ~40 refs):

| File | Old path | New path |
|------|----------|----------|
| AGENTS.md | `./HANDOFF.md` | `./worklogs/HANDOFF.md` |
| README.md | `./HANDOFF.md` | `./worklogs/HANDOFF.md` |
| knowledge/llms.txt | `HANDOFF.md` | `worklogs/HANDOFF.md` |
| knowledge/README.md | `../HANDOFF.md` | `../worklogs/HANDOFF.md` |
| knowledge/MAINTENANCE.md | (being deleted) | (skip) |
| knowledge/adr/DIGEST.md | `../../HANDOFF.md` | `../../worklogs/HANDOFF.md` |
| knowledge/adr/ADR-*.md | varies | adjust depth |
| knowledge/skills/*/SKILL.md | `../../HANDOFF.md` | `../../worklogs/HANDOFF.md` |
| knowledge/trace/exploration_log.md | `../../HANDOFF.md` | `../../worklogs/HANDOFF.md` |
| knowledge/anti-patterns/*.md | `../../HANDOFF.md` | `../../worklogs/HANDOFF.md` |
| .pre-commit-config.yaml | (if any) | update |

**Verification:** `grep -rn '"HANDOFF.md"\|/HANDOFF.md\|](./HANDOFF.md\|](../HANDOFF.md\|](../../HANDOFF.md' --include='*.md' --include='*.txt' --include='*.yaml' . | grep -v __pycache__ | grep -v worklogs/` returns 0

### Step 3.2: BACKLOG.md references

| File | Old path | New path |
|------|----------|----------|
| HANDOFF.md (now worklogs/) | `./knowledge/BACKLOG.md` | `./BACKLOG.md` (same dir) |
| knowledge/llms.txt | `knowledge/BACKLOG.md` | `worklogs/BACKLOG.md` |
| knowledge/README.md | `./BACKLOG.md` | `../worklogs/BACKLOG.md` |

**Verification:** `grep -rn 'knowledge/BACKLOG.md\|/BACKLOG.md' --include='*.md' --include='*.txt' . | grep -v __pycache__ | grep -v worklogs/` returns 0

### Step 3.3: Implementation plan references

| File | Old | New |
|------|-----|-----|
| HANDOFF.md | `knowledge/loop-improvement-workplan.md` | `implementation-plans/loop-improvement-workplan.md` |
| HANDOFF.md | `knowledge/mutation-survivors-workplan.md` | `implementation-plans/mutation-survivors-workplan.md` |
| HANDOFF.md | `knowledge/research/fa-workflow-loop-implementation-plan-2026-06-29.md` | `implementation-plans/fa-workflow-loop-implementation-plan-2026-06-29.md` |
| knowledge/skills/mutation-clearing/SKILL.md | `knowledge/mutation-survivors-workplan.md` | `worklogs/implementation-plans/mutation-survivors-workplan.md` |
| knowledge/trace/exploration_log.md | `knowledge/research/adr-13-14-implementation-plan-*` | `worklogs/implementation-plans/adr-13-14-implementation-plan-*` |

**Verification:** `grep -rn 'knowledge/research/fa-workflow-loop\|knowledge/research/substrate-slice\|knowledge/research/substrate-gap\|knowledge/research/substrate-modernization\|knowledge/research/adr-13-14-implementation\|knowledge/loop-improvement-workplan\|knowledge/mutation-survivors-workplan' --include='*.md' --include='*.txt' . | grep -v __pycache__ | grep -v worklogs/ | grep -v doc-refactoring` returns 0

### Step 3.4: pr-notes/ references

Only AGENTS.md line 18 mentions `/pr-notes/`. Update to `/worklogs/pr-notes/`.

**Verification:** `grep -rn 'knowledge/pr-notes\|/pr-notes/' --include='*.md' --include='*.txt' . | grep -v __pycache__ | grep -v worklogs/pr-notes/ | grep -v doc-refactoring` returns 0

### Step 3.5: Full sweep

```bash
# Run after all individual updates
for old_path in \
  'knowledge/BACKLOG.md' \
  'knowledge/loop-improvement-workplan.md' \
  'knowledge/mutation-survivors-workplan.md' \
  'knowledge/pr-notes/' \
  'knowledge/research/substrate-slice' \
  'knowledge/research/substrate-gap-closure' \
  'knowledge/research/substrate-modernization' \
  'knowledge/research/adr-13-14-implementation' \
  'knowledge/research/fa-workflow-loop' \
  'knowledge/research/fa-workflow-operator' \
  'knowledge/research/phase1-foundation-detailed' \
  'knowledge/STAGE_0_0.5_VERIFICATION' \
  'knowledge/STAGE_1_VERIFICATION' \
  'knowledge/review-stage-0-0.5'; do
  count=$(grep -rn "$old_path" --include='*.md' --include='*.txt' --include='*.yaml' . 2>/dev/null | grep -v __pycache__ | grep -v worklogs/ | grep -v doc-refactoring | wc -l)
  echo "$old_path: $count remaining refs"
done
```

Target: 0 for all paths.

---

## Phase 4 — Create reference.md (merged glossary + features + architecture salvage + session_db)

This is the keystone edit. One file replaces three that will be deleted in Phase 6.

### Step 4.0: Update 02-operations.md session data info first

The operations manual currently describes `events.jsonl` as the primary event log without mentioning session.db authority. Update it FIRST, then reference that canonical info from reference.md.

Specific edits to `knowledge/instructions/02-operations.md`:

1. **§1 Что это и как устроено** — in the "Главные файлы" table, add `session.db` entry:
   - `~/.fa/session-log/<run_id>/session.db` — "Авторитетная SQLite-база сессии (event_log + blackboard + session_meta). events.jsonl — зеркало для чтения, session.db — источник истины."

2. **§7 Запуск задач агента** — after the `fa run` example, add note:
   - "Данные сессии пишутся сначала в `session.db` (SQLite), затем в `events.jsonl` (зеркало). Если файлы расходятся — session.db авторитетен."

3. **§10 Диагностика** — in the log viewing section, add:
   - "Для программного чтения используйте `session.db` (авторитетный источник). `events.jsonl` — для быстрого `cat`/`grep`, но не авторитетен."

**Verification:** `grep -c 'session\.db\|session_db' knowledge/instructions/02-operations.md` ≥ 2

### Step 4.1: Content inventory

Source files and what to take:

| Source | Lines | Take | Skip |
|--------|-------|------|------|
| glossary.md | 86 | All 40+ term entries | — |
| FEATURES.md | 114 | §1-§7 feature descriptions (condensed) | Russian marketing prose; keep technical content only |
| architecture.md | 273 | П1-П4 patterns, memory taxonomy table, stable/volatile table | §Трёхслойная модель (implicit in ADR-7), §Чему учит Agent (generic), §Правило 80% (generic) |
| NEW (session_db) | ~120 | Session data layout, initialization chain, authority hierarchy, new terms | — |

**Target:** ~400-450 lines total. Below the 1000-line "summary/overview" threshold per pr-creation skill.

### Step 4.2: Write knowledge/reference.md

```markdown
# Reference — Terms, Features, and Session Architecture

> Single lookup file for agents. Replaces glossary.md, FEATURES.md, and architecture.md.
> For routing rules, see AGENTS.md §Query Routing. For vision/axes/principles, see project-overview.md.

---

## §Quick Ref — Most Common Queries

| Query | Answer |
|-------|--------|
| Where is session state? | `~/.fa/session-log/<run_id>/session.db` (SQLite authority). JSONL mirrors are best-effort. |
| How to read events programmatically? | `session.session_db.read_event_rows()` — never parse JSONL directly for correctness. |
| How to find artifacts? | `blackboard.query(type="skill")` or `fs_instant_grep(query="auth", limit=10)`. See AGENTS.md §Querying Artifacts. |
| How to see cross-run stats? | `fa stats --global-history` reads `~/.fa/global_history.db`. |
| Is JSONL authoritative? | No. If JSONL and session.db disagree, session.db wins. JSONL is human-readability surface. |

---

## § Terms

[All existing glossary.md entries, preserving table format and cross-references.]

### New terms — session_db authority model

| Term | Description |
|------|-------------|
| **SessionDatabase** | Per-run authoritative SQLite database at `~/.fa/session-log/<run_id>/session.db`. Three tables: `event_log` (authoritative events), `blackboard` (content-hashed entries with read_set/write_set), `session_meta` (key-value). Thread-safe via `threading.Lock` + short-lived connections + WAL. Created by `EventLog.__init__`; shared with `Blackboard` and `SessionState`. Source: `src/fa/inner_loop/session_db.py`. |
| **Blackboard** | Typed append-only content-hashed store. Entries: `id`, `type`, `content_hash`, `read_set`, `write_set`, `assumptions`, `version_dependencies`. Authority: `session.db.blackboard` table. Mirror: `workspace/.fa/blackboard/blackboard.jsonl` (best-effort). Cannot exist without `SessionDatabase`. Gated by `FeatureFlags.blackboard_enabled`. Conflict detection via `detect_conflict()`. Source: `src/fa/blackboard/blackboard.py`. |
| **Transaction** | Accumulates `read_set`/`write_set` during a session. Always initialized (unlike Blackboard, which is conditional). Feeds into Blackboard entries for conflict detection. Source: `src/fa/inner_loop/transaction.py`. |
| **ArtifactStore** | Content-addressed store at `<workspace>/.fa/artifacts/`. Stores elided tool result payloads as `tool-result-<sha256[:16]>.json`. Keeps `event_log` lean. Source: `src/fa/inner_loop/artifacts.py`. |
| **GlobalHistoryStore** | Derived analytics projection at `~/.fa/global_history.db`. Single `runs` table (tokens, cost, duration, tool breakdown). Populated at session end, best-effort, never crashes main. Active consumer: `fa stats --global-history`. NOT imported by hot-path code for correctness. Source: `src/fa/inner_loop/global_history.py`. |
| **Dual-write authority** | Write discipline: (1) write to SQLite authority first (raises on failure), (2) advance state only after commit, (3) write JSONL mirror best-effort. Both `EventLog` and `Blackboard` follow this pattern. SQLite = machine authority; JSONL = human-readability surface. |
| **ContextVar DI** | Dependency injection via `contextvars.ContextVar`. `set_current_session(state)` in `drive_session()`; tool handlers call `get_current_session()` → access `session.blackboard`, `session.session_db`. Decouples tools from session lifecycle. Source: `src/fa/inner_loop/context.py`. |
| **FeatureFlags** | Runtime toggles from `~/.fa/config.yaml`. 13 fields, all with production consumers. Gate Blackboard and Telemetry init. Defaults safe (`blackboard_enabled=True`). Source: `src/fa/feature_flags.py`. |
| **EventLog** | Append-only event writer. Creates `SessionDatabase` at init. `append()` → `session_db.append_event_row()` (authority) + `events.jsonl` (mirror). `read_all()` → DB first, JSONL fallback. Source: `src/fa/inner_loop/state.py`. |

---

## § Features

### Session Database Authority

Every `fa run` creates a per-run SQLite database (`session.db`) that is the single source of truth for hot-path runtime state. Three tables hold the complete session history, blackboard entries, and metadata. JSONL files exist as human-readable mirrors — if they disagree with session.db, session.db wins.

### Blackboard Conflict Detection

When `edit_file` or `write_file` writes, the Blackboard checks for conflicts: if entry B's `read_set` overlaps with a prior entry A's `write_set`, and A was written after B started reading, `detect_conflict()` returns a structured failure. This prevents the "parent HEAD switched" bug (Claude #55708).

### Cross-Run Analytics

`fa stats --global-history` reads `~/.fa/global_history.db` — a derived projection populated at session end. Not hot-path authority; purely analytics.

### Egress-Injection Proxy (ADR-12)

API keys live only in a separate `fa-egress-proxy` container. Agent reaches providers through the proxy (HTTP + non-key token); proxy injects the real key. Agent can *use* keys but never *read* them.

### Trusted Computing Base (ADR-11)

Two-tier authoring TCB: frozen stdlib-only Level-0 kernel + allowlisted Level-1 rules. LLM as Untrusted Compiler threat model. Test-decay lock prevents `pytest.skip` / `assert True` gaming.

### Bash Intent Analysis

`fs_run_bash` is parsed through `bashlex` AST. IntentGuard classifies: `READ_ONLY`, `INDEX_WRITE`, `REPO_WRITE`, `DANGEROUS`. REPO_WRITE blocked without authorized PR draft.

### Token-Efficient Retrieval

Mechanical Wiki: filesystem-canon Markdown + SQLite FTS5 BM25. No vector DB, no embeddings in v0.1. Tools have `max_context_bytes` with automatic head/tail elision.

---

## § Patterns

### Feedback Loop (П1)

Action → Observation → Reflection → Next Action. The core agent pattern. Tests after edits, linter, typechecker = the feedback loop made deterministic. First reliable agent pattern; everything else builds on it.

### Planning Before Execution (П2)

1. Parse requirements. 2. Explore codebase. 3. Plan (files, risks, tests). 4. Execute step-by-step. 5. Deliver.

### Escalation (П3)

`task_is_clear → execute() / task_is_ambiguous → ask() / task_exceeds_capability → report()` — three modes, never guess.

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
| Stable (architecture, ADRs) | knowledge/adr/, knowledge/ | Synthesize once, rarely changes |
| Semi-stable (research) | knowledge/research/ | Update on significant findings |
| Volatile (session logs) | ~/.fa/session-log/ | Synthesize on demand only |

---

## § Session Data Layout

> For the operator-facing description of session data, see `knowledge/instructions/02-operations.md`.

### Per-run artifacts (~/.fa/session-log/<run_id>/)

| File | Role | Authority |
|------|------|-----------|
| `session.db` | SQLite: event_log + blackboard + session_meta | **Yes** |
| `events.jsonl` | JSONL mirror of event_log | No (best-effort) |
| `pr_draft.md` | PR draft artifact | Standalone |
| `eval_report.json` | Workflow eval verdict | Standalone |
| `flow_state.json` | Workflow controller state | Standalone |
| `attempt_history.json` | Recovery attempt log | Standalone |

### Workspace artifacts (<workspace>/.fa/)

| Path | Role | Authority |
|------|------|-----------|
| `blackboard/blackboard.jsonl` | JSONL mirror of session.db.blackboard | No (best-effort) |
| `artifacts/` | Content-addressed tool result offloads | Complements event_log |
| `subagents/<task_id>.json` | Subagent spawn results | Standalone |
| `fts.db` | FTS5 full-text search index | Disposable cache |

### Cross-run artifacts

| Path | Role |
|------|------|
| `~/.fa/global_history.db` | Derived analytics. `fa stats --global-history` |
| `~/.fa/config.yaml` | FeatureFlags + runtime config |
| `~/.fa/models.yaml` | Unified routing config |

### Initialization chain

```
fa run → _cmd_run() → EventLog(path, run_id) → SessionDatabase(session.db)
       → SessionState(log, run_id, workspace) → __post_init__:
           session_db = log.session_db (shared instance)
           FeatureFlags from ~/.fa/config.yaml
           Transaction (always)
           ArtifactStore (lazy)
           Blackboard (lazy, requires session_db + flag)
           TelemetryLogger (lazy)
       → drive_session(state) → set_current_session(state)
       → Tools: get_current_session() → session.blackboard, session.session_db, ...
```

### Authority hierarchy

1. **session.db** — single source of truth for hot-path state
2. **JSONL mirrors** — best-effort, human-readable, for audit/diff
3. **global_history.db** — derived projection, never imported for correctness
4. **File artifacts** — standalone, not replicated in DB
```

**Verification:**
- `wc -l knowledge/reference.md` ≈ 400-450
- `grep -c '^| \*\*' knowledge/reference.md` ≥ 49 (40 original + 9 new terms)
- All 9 new terms present: `SessionDatabase`, `Blackboard`, `Transaction`, `ArtifactStore`, `GlobalHistoryStore`, `Dual-write authority`, `ContextVar DI`, `FeatureFlags`, `EventLog`

---

## Phase 5 — Update core docs with session_db authority + new paths

### Step 5.1: Update AGENTS.md

Specific edits:

1. **§Project Overview** — add: "Session state is managed by per-run SQLite authority (session.db). See knowledge/reference.md §Session Data Layout."
2. **§Repository Structure** — update entries:
   - Remove `knowledge/llms.txt — one-fetch file index` (keep but note legacy)
   - Add `worklogs/ — session work artifacts (HANDOFF, BACKLOG, plans, pr-notes)`
   - Change `knowledge/` description to note reference.md
   - Change HANDOFF.md → worklogs/HANDOFF.md
3. **§Pre-flight Step 2** — change grep target from `knowledge/glossary.md` to `knowledge/reference.md`
4. **§Context-budget discipline** — add: "session.db reduces context need: query `session.session_db` instead of scanning JSONL files."
5. **§Query Routing** — add row: "Session state / event history / data layout" → `knowledge/reference.md §Session Data Layout`
6. **§Querying Artifacts** — update: explicitly state "session.db is SQLite authority; JSONL files are best-effort mirrors. If they disagree, session.db wins."
7. **§Session close** — add: "Load doc-maintenance skill before committing." + update HANDOFF.md path
8. **§Loadable skills** — add doc-maintenance row
9. **§Working in This Repo** — update all `HANDOFF.md` references to `worklogs/HANDOFF.md`

**Verification:** `grep -c 'session\.db\|SessionDatabase\|authority' AGENTS.md` ≥ 4; `grep -c 'worklogs/' AGENTS.md` ≥ 2

### Step 5.2: Update project-overview.md

Specific edits:

1. **§6 Key constraints → Storage** — change: "Filesystem-canonical (Markdown + YAML frontmatter). Per-run hot-path authority in SQLite (`session.db`); disposable FTS5 index. JSONL mirrors are best-effort, not authoritative."
2. **§1.2.6 Substrate Formality** — add note: "Blackboard (session.db.blackboard table) now implements I-6.1 through I-6.4 with content hashing, read_set/write_set, and detect_conflict()."

**Verification:** `grep -c 'session\.db\|SessionDatabase' knowledge/project-overview.md` ≥ 2

### Step 5.3: Update llms.txt (minimal)

Specific edits:

1. **§MUST READ FIRST** — update to reflect new paths:
   - Item 5: `knowledge/reference.md — canonical definitions, features, session architecture` (replaces glossary.md)
   - Item 3: `worklogs/HANDOFF.md` (replaces root HANDOFF.md)
   - Verify list is still 5 items, coherent, in reading order
2. **§FORMAL SUBSTRATE** — add note: "session.db is SQLite authority per run (3 tables: event_log, blackboard, session_meta). JSONL files are best-effort mirrors. Full schema: knowledge/reference.md §Session Data Layout."
3. **§TASK ROUTING** — update HANDOFF.md path; update "Move/prune a doc?" to reference doc-maintenance skill
4. **§BY-DEMAND INDEX** — add note: "knowledge/architecture.md, knowledge/glossary.md, knowledge/overview/FEATURES.md removed (merged into knowledge/reference.md)."

**Verification:** `grep -c 'reference\.md' knowledge/llms.txt` ≥ 2

### Step 5.4: Update knowledge/README.md

Specific edits:

1. **Layout tree** — remove: architecture.md, glossary.md, FEATURES.md, MAINTENANCE.md entries. Add: reference.md. Add worklogs/ note.
2. **What goes where table** — add rows:
   - "A term, feature, or session architecture detail" → `knowledge/reference.md`
   - "Cross-session state or active work" → `worklogs/`
3. **Routing table** — update: "What is our architecture for X?" → `knowledge/reference.md §Patterns` (was architecture.md). "Terms" → `knowledge/reference.md §Terms` (was glossary.md).
4. **Conventions** — remove MAINTENANCE.md reference, point to doc-maintenance skill

**Verification:** `grep -c 'reference\.md' knowledge/README.md` ≥ 3; `grep -c 'glossary\.md\|architecture\.md\|MAINTENANCE\.md' knowledge/README.md` = 0

### Step 5.5: Update README.md

Rewrite as rich condensed project representation. Structure:

```markdown
# First-Agent

[Badges — keep existing]

> One-liner pitch

## Architecture at a Glance

[Mermaid diagram — update to show worklogs/ + session.db authority]

## Key Features

[Condensed from FEATURES.md + new session_db features]
- Session Database Authority (SQLite per-run, JSONL mirrors)
- Blackboard Conflict Detection
- Egress-Injection Proxy
- Trusted Computing Base
- Bash Intent Analysis
- Token-Efficient Retrieval

## Quick Start

[For humans: link to knowledge/instructions/]
[For agents: link to AGENTS.md]

## Repository Map

[Updated file listing reflecting new structure]
- AGENTS.md — agent session rules
- knowledge/project-overview.md — vision, principles, scope
- knowledge/reference.md — terms, features, session architecture
- worklogs/HANDOFF.md — current session state
- knowledge/adr/ — architecture decisions
- knowledge/research/ — research notes
- knowledge/skills/ — agent-loadable disciplines
```

**Verification:** `grep -c 'session\.db\|reference\.md\|worklogs/' README.md` ≥ 3

---

## Phase 6 — Delete merged/pruned files

### Step 6.1: Delete files whose content is now in reference.md

```bash
git rm knowledge/glossary.md
git rm knowledge/architecture.md
git rm knowledge/overview/FEATURES.md
```

### Step 6.2: Remove empty knowledge/overview/ directory

```bash
rmdir knowledge/overview/
```

**Verification:** `test -d knowledge/overview/` fails

### Step 6.3: Delete MAINTENANCE.md (replaced by skill in Phase 7)

```bash
git rm knowledge/MAINTENANCE.md
```

**Verification:** All three source files deleted, reference.md contains their merged content.

### Step 6.4: Remove 02-operations.md from agent routing

File stays on disk for human operators. Remove from agent routing surfaces only:
- Remove from llms.txt (agent routing index)
- Remove from knowledge/README.md layout tree (agent memory map)
- Keep in knowledge/instructions/ for human use
- Update knowledge/instructions/README.md: clarify "01-install and 02-operations are for human operators, not agent session routing"

**Verification:** `grep -c '02-operations' knowledge/llms.txt` = 0; `test -f knowledge/instructions/02-operations.md` passes

### Step 6.5: Final sweep for deleted file references

```bash
for deleted in \
  'knowledge/glossary.md' \
  'knowledge/architecture.md' \
  'knowledge/overview/FEATURES.md' \
  'knowledge/MAINTENANCE.md'; do
  count=$(grep -rn "$deleted" --include='*.md' --include='*.txt' --include='*.yaml' . 2>/dev/null | grep -v __pycache__ | grep -v doc-refactoring | wc -l)
  echo "$deleted: $count remaining refs"
done
```

Target: 0 for all paths.

---

## Phase 7 — Create doc-maintenance skill

### Step 7.1: Create knowledge/skills/doc-maintenance/SKILL.md

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
3. If any new term was introduced, add to `knowledge/reference.md` §Terms.
4. If any ADR was amended, update `knowledge/adr/DIGEST.md` and append to `knowledge/trace/exploration_log.md`.
5. Run `grep -rn '<old-path>' .` for any files moved/renamed/deleted — fix every reference.
6. Verify: `python scripts/check_doc_links.py` passes.

## §When archiving a research note

1. Add `> **Status:** archived 2026-MM-DD` banner at top.
2. Add `superseded_by:` frontmatter if applicable.
3. Update `knowledge/llms.txt` — re-path or remove the row.
4. Cross-check `worklogs/HANDOFF.md` §Current state.
5. Cross-check `knowledge/adr/DIGEST.md`.
6. Cross-check `knowledge/reference.md` §Terms.

## §When moving or pruning a doc

**The one hard rule: no dangling links.** In the same PR:

1. `grep -rn '<old-filename>' .` to find every reference.
2. For a move/rename: re-path every reference. Adjust link depth.
3. For a deletion: remove refs or retarget to superseding artifact. Drop llms.txt row.
4. Update `knowledge/llms.txt`, `worklogs/HANDOFF.md` (active links only), `knowledge/reference.md`, and file indexes.
5. Verify: `python scripts/check_doc_links.py` passes and `grep -rn '<old-path>'` returns nothing unexpected.

## §When adding a new file under knowledge/ or worklogs/

1. Add a row in `knowledge/llms.txt` §BY-DEMAND INDEX under matching folder section.
2. Row format: `[path/to/file.md]: description.` Description ≤200 chars.
3. For files >1200 LoC add size tag: `[path/to/file.md] (Large)`.
4. If the file introduces a new term, add to `knowledge/reference.md` §Terms.
5. If the file has an ADR cross-reference, update DIGEST.md.

## §When merging an ADR amendment

1. Update `knowledge/adr/DIGEST.md` — extend the Amendments bullet.
2. Append to `knowledge/trace/exploration_log.md` per pr-creation skill rule #9.
3. Cross-check `worklogs/HANDOFF.md` §Current state ADR list.
```

**Verification:** `test -f knowledge/skills/doc-maintenance/SKILL.md`

### Step 7.2: Add trigger row to AGENTS.md §Loadable skills

Add row to the skill table:

```markdown
| [`doc-maintenance`](./knowledge/skills/doc-maintenance/SKILL.md) | **Trigger:** At session close, or when moving/pruning/adding any file under `knowledge/` or `worklogs/`.<br><br>Ensures link integrity, llms.txt updates, and HANDOFF freshness. Replaces former `knowledge/MAINTENANCE.md` routing file. |
```

**Verification:** `grep -c 'doc-maintenance' AGENTS.md` ≥ 1

### Step 7.3: Update all MAINTENANCE.md references (19 found in audit)

| File | Update |
|------|--------|
| `.pre-commit-config.yaml:34` | Point to skill |
| `AGENTS.md:260` | Point to skill |
| `worklogs/HANDOFF.md` (was root) | Point to skill |
| `worklogs/BACKLOG.md` | Point to skill |
| `knowledge/reference.md` (new) | Reference skill in glossary-style entry |
| `knowledge/llms.txt` | Point to skill |
| `knowledge/anti-patterns/AP-002-*` (4 refs) | Point to skill |
| `knowledge/anti-patterns/README.md` (3 refs) | Point to skill |

**Verification:** `grep -rn 'MAINTENANCE\.md' --include='*.md' --include='*.txt' --include='*.yaml' . | grep -v __pycache__ | grep -v doc-refactoring` returns 0

---

## Phase 8 — Anti-patterns integration

### Step 8.1: Create AP-005

File: `knowledge/anti-patterns/AP-005-dual-write-authority-violation.md`

```markdown
---
compiled: 2026-07-18
applies_to: ADR-7 (EventLog), Phase 0.5 Blackboard, session_db authority
---

# AP-005 — Dual-write authority violation

## §Symptom

Tool handler writes to JSONL file but the corresponding `session.db` row is missing or stale. Agent reads from JSONL mirror and gets a different answer than code reading from SQLite authority.

## §Wrong shape

Writing to the JSONL mirror only (or writing to JSONL first, then SQLite), so that the human-readable file and the machine authority diverge on crash or partial failure.

## §Right shape

Always write to SQLite authority first. Only after the authoritative commit succeeds, advance logical state and write the JSONL mirror best-effort. If SQLite write fails, raise `RuntimeError` — do NOT silently fall through to JSONL-only write.

## §Why the wrong shape dominates

JSONL is the file operators see (`cat events.jsonl`). It "feels" like the primary artifact because it's human-readable. The SQLite DB is invisible. This visibility asymmetry makes JSONL-first writing the intuitive default.

## §Detection

1. `session_db.append_event_row()` raises `RuntimeError` if `session_db` is `None` — enforcement point in `src/fa/inner_loop/state.py`.
2. `Blackboard.write()` writes to `session_db` first, JSONL second — pattern in `src/fa/blackboard/blackboard.py`.
3. Test: verify JSONL is empty when SQLite write fails (composition-root test pattern).

## §Linked-ADR

ADR-7 §7 (Trace), Phase 0.5 Blackboard design

## §Evidence

- `src/fa/inner_loop/state.py` — `EventLog.append()` authority-first discipline
- `src/fa/blackboard/blackboard.py` — `Blackboard.write()` authority-first discipline
```

### Step 8.2: Update anti-patterns/README.md index

Add row:

```markdown
| AP-005 | Dual-write authority violation | [session_db authority](../reference.md#session-data-layout) | accepted |
```

**Verification:** `grep -c 'AP-005' knowledge/anti-patterns/README.md` ≥ 1

---

## Phase 9 — Verification

### Step 9.1: Broken reference sweep

```bash
echo "=== Deleted file refs ==="
for f in knowledge/glossary.md knowledge/architecture.md knowledge/overview/FEATURES.md knowledge/MAINTENANCE.md; do
  echo "$f: $(grep -rn "$f" --include='*.md' --include='*.txt' --include='*.yaml' . 2>/dev/null | grep -v __pycache__ | grep -v doc-refactoring | wc -l) remaining"
done

echo "=== Moved file refs ==="
for f in HANDOFF.md knowledge/BACKLOG.md knowledge/pr-notes/ knowledge/loop-improvement-workplan.md knowledge/mutation-survivors-workplan.md; do
  echo "$f: $(grep -rn "$f" --include='*.md' --include='*.txt' --include='*.yaml' . 2>/dev/null | grep -v __pycache__ | grep -v worklogs/ | grep -v doc-refactoring | wc -l) remaining"
done
```

Target: 0 for all paths.

### Step 9.2: Doc link checker

```bash
python scripts/check_doc_links.py
```

Target: 0 broken links.

### Step 9.3: Agent bootstrap coherence test

Read the 5 MUST-READ-FIRST files in order, verify they form a coherent bootstrap:

1. `AGENTS.md` — updated with worklogs/ paths, reference.md, session_db ✓
2. `knowledge/project-overview.md` — updated with session_db ✓
3. `worklogs/HANDOFF.md` — moved, internal links fixed ✓
4. `knowledge/adr/DIGEST.md` — unchanged ✓
5. `knowledge/reference.md` — new, replaces glossary ✓

### Step 9.4: Smoke test — no code references broken

```bash
grep -rn 'glossary\|MAINTENANCE\.md' src/ tests/ --include='*.py' | grep -v __pycache__
# Target: 0 (code shouldn't reference these doc files)
```

---

## Execution order (dependency DAG)

```
Phase 1 (create worklogs/) ─────┐
                                 ├→ Phase 2 (move files) ─→ Phase 3 (update refs)
Phase 4 (create reference.md) ──┘         │
                                           ├→ Phase 5 (update core docs)
                                           │
                                 Phase 7 (skill) ──┤
                                                    ├→ Phase 6 (deletes)
                                                    │
                                 Phase 8 (AP-005) ──┘
                                                    │
                                                    └→ Phase 9 (verification)
```

Phases 1 and 4 can run in parallel. Phase 7 can run in parallel with Phase 2. Phase 6 must wait for Phases 4 and 7. Phase 9 is last.

---

## Items intentionally deferred to follow-up sessions

| Item | Reason |
|------|--------|
| ADR-4/7/14 amendments | Not priority per user |
| Codemaps update (codegraph) | Not priority per user |
| Prompts formalization | Not priority per user |
| Trace pruning | Not priority per user |
| Move `authoring-hardening-workplan-v2` to worklogs/ | Circular — it tracks this PR's criterion #8. Move after this PR lands. |
| Move `ADR-11-Authoring-Guardrails-Blueprint.md` | Not a session artifact — canonical ADR reference with 6+ external refs |
| Move `ci-guardrails-reference.md` | Referenced 8+ times from codemaps/; codemaps are deferred |
| `fa generate-llms-txt` tool | Auto-generate BY-DEMAND INDEX from blackboard — future work |

---

## Risk register

| Risk | Mitigation |
|------|------------|
| Moved files have broken internal links | Phase 2.6 explicitly fixes relative links; Phase 9.2 runs link checker |
| Missing cross-ref update causes 404 | Phase 9.1 does comprehensive grep sweep for all old paths |
| reference.md too large (>1000 lines) | Content budget: ~450 lines. If exceeded, split §Features into separate file. |
| AGENTS.md skill table grows too large | Current: 4 skills. After: 5 skills. Well within attention budget. |
| JSONL-first writers introduced in future | AP-005 documents the correct pattern; code raises RuntimeError on authority absence |
