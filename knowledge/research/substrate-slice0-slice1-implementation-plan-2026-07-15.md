# Slice 0 / Slice 1 Implementation Plan — Code-Facing Detail

**Date:** 2026-07-15
**Parent plan:** `knowledge/research/substrate-gap-closure-workplan-round2-2026-07-15.md`
**Purpose:** implementation planning only, no code changes
**Scope:**
- Slice 0 — contract freeze
- Slice 1 — unified per-run DB authority and split-brain removal

---

## 0. Planning assumptions

Locked operator decisions already accepted:

1. **DB authority**
   One unified per-run authoritative DB.
   Workspace/global DBs are derived projections, not hot-path authority.

2. **Resume/PR-draft semantics**
   Previous PR draft / resume text is mutable non-cacheable summary/history.

3. **Subagent scope**
   `fs_spawn_subagent` is narrow-scope, role-bounded, stateless, limited-function, and must not bypass parent shell/tool safety.

This document plans only Slice 0/1. It intentionally does **not** implement Slice 3/4/5 logic here.

---

## 1. What the current code tells us (verified baseline)

### 1.1 Active authority is currently fragmented

Hot-path state currently spans at least three write surfaces:

- `EventLog` JSONL mirror + per-run SQLite DB
  `src/fa/inner_loop/state.py`
- `Blackboard` JSONL mirror + workspace SQLite DB
  `src/fa/blackboard/blackboard.py`
- telemetry JSONL
  `src/fa/telemetry/telemetry.py`

### 1.2 EventLog path

Live CLI uses:
- `src/fa/cli.py::_cmd_run` → `~/.fa/session-log/<run_id>/events.jsonl`
- `EventLog._init_db()` creates `~/.fa/session-log/<run_id>/session.db`

### 1.3 Blackboard path

`SessionState.__post_init__()` currently constructs:
- `Blackboard(self.workspace_root / ".fa" / "blackboard")`

`Blackboard._init_db()` then creates:
- `workspace/.fa/blackboard/session.db`

That is the main authority split.

### 1.4 Primary split-brain defect

Current write order is:
- write JSONL first
- then write SQLite

and read order is:
- prefer SQLite if any rows exist
- otherwise fallback to JSONL

That makes partial SQLite failure produce stale authority reads.

### 1.5 Current runtime consumers that matter for Slice 1

**EventLog authority consumers / wrappers**
- `src/fa/inner_loop/coder_loop.py` via `state.log.read_all()`
- `src/fa/stats.py` via `EventLog.read_all()`
- hook observers using `EventLog.append()`
- audit sink in `src/fa/inner_loop/loop.py`

**Blackboard authority consumers / wrappers**
- `src/fa/inner_loop/tools/write_file.py`
- `src/fa/inner_loop/tools/edit_file.py`
- `src/fa/inner_loop/subagent_runner.py` (`bb.query(type="plan")`)
- `SessionState.__post_init__()` blackboard DI

### 1.6 Things we should NOT solve inside Slice 1

To keep Slice 1 crisp:
- do **not** redesign Stage C here
- do **not** solve global history export here
- do **not** solve shared-workspace multi-run coordination fully here
- do **not** migrate all telemetry storage here unless needed for authority integrity

Slice 1 should solve **hot-path authority** and **split-brain**, not every derived surface.

---

## 2. Slice 0 — Contract freeze plan

## 2.1 Objective

Create a minimal durable contract that later slices can code against without re-litigating semantics.

## 2.2 Deliverables

### Deliverable A — Decision record update

Prefer one of:
- append to the existing round-2 workplan, or
- create a small ADR/decision note under `knowledge/adr/` or `knowledge/research/`

Must explicitly record:
- D8 unified per-run DB authority
- D9 resume text is mutable non-cacheable memory
- D10 narrow-scope subagent contract

### Deliverable B — Drift annotations

At minimum, update or annotate the following misleading surfaces in a follow-up slice if not now:
- any comments implying blackboard workspace DB is hot-path authority
- any comments implying previous PR draft is standing governance
- any comments implying subagent is generic isolated executor

## 2.3 Exact file edit map for Slice 0

### Must-edit
- `knowledge/research/substrate-gap-closure-workplan-round2-2026-07-15.md`
  - ensure D8/D9/D10 are visible and grep-able

### Likely-add
- `knowledge/research/substrate-decision-freeze-2026-07-15.md`
  - if you want a tighter decision artifact than the larger workplan

### Nice-to-have (not mandatory inside Slice 0)
- update stale inline module docstrings later during the code slices instead of here

## 2.4 Verification sequence for Slice 0

1. Grep proof that D8/D9/D10 each exist in one durable file.
2. Grep stale contradictory phrases to build the later cleanup list.
3. Confirm no remaining ambiguity in next-slice design notes.

## 2.5 Done definition

A contributor can answer, from repo docs alone:
- where hot-path authority lives,
- whether resume text is pinned or mutable,
- whether subagent is general shell or bounded helper.

---

## 3. Slice 1 — Unified per-run DB authority

## 3.1 Objective

Replace the current fragmented hot-path authority with a single per-run DB while minimizing call-site churn.

The right tactical move is **not** to rewrite every caller at once.
The right tactical move is to introduce a narrow DB authority layer, then adapt existing facades (`EventLog`, `Blackboard`) onto it.

---

## 3.2 Recommended implementation shape

### Recommendation
Add a new internal module:
- `src/fa/inner_loop/session_db.py`

This becomes the only module responsible for:
- opening the per-run SQLite file
- applying pragmas
- creating authoritative schema
- handling inserts/queries for runtime hot-path state
- sequencing writes consistently

This keeps `state.py` and `blackboard.py` from growing even more chaotic.

### Why a new module is preferable

If we keep bolting more authority logic into `EventLog` and `Blackboard` directly:
- duplicated schema init persists
- duplicated SQLite connection policy persists
- migration logic gets split in two
- future export/meta tables get uglier

A senior implementation would usually centralize this now.

---

## 3.3 Proposed authoritative module API (minimal)

Not final code, but target responsibilities:

### `SessionDatabase`

Constructor:
- `SessionDatabase(db_path: Path)`

Responsibilities:
- `init_schema()`
- `append_event(...) -> event_id / row metadata`
- `read_events() -> tuple[TraceEvent, ...]`
- `write_blackboard(entry: BlackboardEntry) -> None`
- `read_blackboard(id: str) -> BlackboardEntry | None`
- `query_blackboard(type: str | None, key: str | None) -> list[BlackboardEntry]`
- `set_meta(key: str, value: ...)`
- `get_meta(key: str)`

### Connection policy

Prefer:
- open short-lived connections per operation **or** one encapsulated connection with strict lock discipline

Given current code style and reduced migration risk, for Slice 1 I recommend:
- **short-lived connections per operation**, but centralized in `SessionDatabase`
- one Python lock guarding writes in-process
- explicit `busy_timeout`
- WAL + `synchronous=NORMAL`

Reason:
- smallest behavior delta from current code
- avoids immediately introducing shared-connection threading hazards

---

## 3.4 Proposed authoritative schema

Keep schema small for Slice 1.

### Table: `event_log`

Purpose:
- same role as current `EventLog` SQLite table

Columns (minimum):
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `event_id TEXT NOT NULL`
- `ts TEXT NOT NULL`
- `run_id TEXT NOT NULL`
- `actor TEXT NOT NULL`
- `kind TEXT NOT NULL`
- `tool_name TEXT NOT NULL DEFAULT ''`
- `tool_call_id TEXT NOT NULL DEFAULT ''`
- `parent_event_id TEXT NOT NULL DEFAULT ''`
- `content TEXT NOT NULL`
- `harness_id TEXT NOT NULL`

Indexes (minimum):
- `idx_event_log_kind ON event_log(kind)`
- `idx_event_log_run_id_id ON event_log(run_id, id)`
- `idx_event_log_tool_call_id ON event_log(tool_call_id)`

### Table: `blackboard`

Purpose:
- authoritative blackboard state for this run

Columns (minimum):
- `id TEXT PRIMARY KEY`
- `run_id TEXT NOT NULL`
- `type TEXT NOT NULL`
- `content_hash TEXT NOT NULL`
- `toolchain_digest TEXT NOT NULL`
- `schema_version TEXT NOT NULL`
- `parent_id TEXT`
- `read_set TEXT NOT NULL`
- `write_set TEXT NOT NULL`
- `assumptions TEXT NOT NULL`
- `version_dependencies TEXT NOT NULL`
- `timestamp TEXT NOT NULL`
- `payload TEXT NOT NULL`

Indexes (minimum):
- `idx_blackboard_run_type_ts ON blackboard(run_id, type, timestamp)`
- `idx_blackboard_type ON blackboard(type)`
- optional later if needed: `idx_blackboard_run_id ON blackboard(run_id)`

### Table: `session_meta`

Purpose:
- store tiny authoritative per-run metadata without inventing ad-hoc event parsing later

Columns:
- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Immediate uses:
- export bookkeeping later
- maybe compaction summary pointer later

Do **not** overdesign this in Slice 1.

---

## 3.5 Mirror policy for JSONL in Slice 1

### Decision
Keep JSONL only as a **best-effort mirror** for now, because:
- existing tooling/tests/stats rely on it,
- removing it in the same slice increases blast radius.

### Required change in semantics
JSONL must stop pretending to be equal authority.

### Required behavior
If authoritative DB write fails:
- append must **not** report clean success
- mirror writes must not become the only silently accepted state
- runtime must either:
  - fail the operation,
  - or enter explicit degraded mode if we intentionally choose that

### Recommendation
For Slice 1, choose:
- **fail closed on authoritative DB write failure**
- JSONL mirror write failure = warning only

That is the simplest honest policy.

---

## 3.6 Exact file edit map for Slice 1

### A. New file

#### `src/fa/inner_loop/session_db.py`

Add new module containing:
- schema initialization
- event/blackboard read/write methods
- central PRAGMA setup
- central write locking discipline

This file is the heart of Slice 1.

---

### B. Major refactor targets

#### `src/fa/inner_loop/state.py`

**Why touched:** currently owns `EventLog` DB logic and `SessionState` blackboard wiring.

**Planned edits:**
1. `EventLog`
   - stop owning schema creation directly
   - delegate SQLite authority operations to `SessionDatabase`
   - optionally keep JSONL mirror logic here only
2. `EventLog.append()`
   - authoritative DB write first or as commit-defining step
   - explicit failure semantics if DB write fails
3. `EventLog.read_all()`
   - authoritative reads from `SessionDatabase`
   - JSONL only fallback if explicitly running in degraded/no-DB mode
4. `SessionState.__post_init__()`
   - create one per-run `SessionDatabase`
   - inject or bind blackboard facade to the same DB
5. `SessionState` fields
   - likely add `session_db: Any | None = None` (typed later)
6. blackboard init path
   - stop constructing authority around `workspace/.fa/blackboard/session.db`

**Symbols likely to change:**
- `EventLog._init_db`
- `EventLog.append`
- `EventLog.read_all`
- `SessionState.__post_init__`

---

#### `src/fa/blackboard/blackboard.py`

**Why touched:** currently creates its own DB + own authority path.

**Planned edits:**
1. make `Blackboard` a facade over `SessionDatabase` or per-run DB path
2. remove workspace-hot-path authority assumptions
3. preserve public API so callers minimally change:
   - `write`
   - `read`
   - `query`
   - `detect_conflict`
4. if JSONL mirror remains, demote it to best-effort only
5. remove private `_init_db` authority bootstrap if central DB owns schema

**Important:**
Minimize caller churn by preserving `BlackboardEntry` and conflict logic shape.

**Symbols likely to change:**
- `Blackboard.__init__`
- `Blackboard._init_db`
- `Blackboard.write`
- `Blackboard.read`
- `Blackboard.query`

---

### C. Hot-path caller adjustments

#### `src/fa/inner_loop/tools/write_file.py`

**Why touched:** uses blackboard conflict detection + blackboard write.

**Planned edits:**
- no API redesign required if `Blackboard` facade stays stable
- but safety checks assuming workspace-root blackboard path will need revision
- any path checks like `.fa/blackboard` equality need to be updated or removed

**Symbols likely to change:**
- `_check_conflict`
- `_write_blackboard_ok`

---

#### `src/fa/inner_loop/tools/edit_file.py`

**Why touched:** same reason as `write_file.py`

**Planned edits:**
- update blackboard-root safety assumptions
- preserve behavior with new per-run authoritative blackboard

**Symbols likely to change:**
- `_get_session_and_blackboard`
- `_write_blackboard_entry`

---

#### `src/fa/inner_loop/subagent_runner.py`

**Why touched:** directly instantiates `Blackboard(self.session_root / ".fa" / "blackboard")`

**Planned edits:**
- for Slice 1, eliminate direct authority-path construction here
- use current session’s injected blackboard if available
- if no current session exists, decide whether to:
  - skip blackboard plan inclusion, or
  - create a non-authoritative read path explicitly marked as such

**Symbols likely to change:**
- `_build_filtered_history`

**Note:**
This is partly Slice 5 territory, but this call site must be cleaned in Slice 1 to avoid recreating workspace DB authority.

---

#### `src/fa/inner_loop/tools/observability.py`

**Why touched:** still JSONL/path based; not fully solved in Slice 1, but at least avoid reinforcing stale authority assumptions.

**Planned edits (minimal in Slice 1):**
- probably none yet, unless needed to avoid broken imports/interfaces
- full runtime observability rewiring belongs to Slice 2

---

#### `src/fa/stats.py`

**Why touched:** consumes `EventLog.read_all()`

**Planned edits:**
- likely minimal or zero if `EventLog.read_all()` remains compatible
- ensure stats still work if JSONL mirror is best-effort and DB is authority

---

### D. Probably no Slice-1 edits required

Unless implementation reveals coupling:
- `src/fa/inner_loop/coder_loop.py`
- `src/fa/providers/*`
- `src/fa/memory/*`
- `src/fa/runtime/*`

Those should benefit from `EventLog` compatibility instead of direct changes.

---

## 3.7 Concrete implementation sequence for Slice 1

### Step 1 — Introduce central DB module

Add `session_db.py` with:
- path handling
- PRAGMAs
- schema creation
- event append/read
- blackboard write/read/query

**Checkpoint A**
- module exists
- schema can initialize in a temp run dir
- zero call-site integration yet

### Step 2 — Move EventLog authority onto SessionDatabase

Update `EventLog` so:
- SQLite schema init is delegated
- authoritative append/read use central module
- JSONL remains mirror-only

**Checkpoint B**
- existing `EventLog` tests still mostly pass or fail only where semantics intentionally changed
- split-brain repro test can now be written against `EventLog`

### Step 3 — Rewire SessionState blackboard to same per-run DB

Update `SessionState.__post_init__()`:
- create the per-run DB once
- create blackboard facade bound to that DB

**Checkpoint C**
- `state.log` and `state.blackboard` point into same per-run authority

### Step 4 — Adapt Blackboard facade

Update `Blackboard` to:
- stop owning workspace authority DB
- use central DB-backed operations
- keep external API stable

**Checkpoint D**
- `write_file` and `edit_file` still operate through same public API

### Step 5 — Remove/repair workspace-path safety assumptions

Update:
- `write_file.py`
- `edit_file.py`
- any code assuming `.fa/blackboard` path identity

**Checkpoint E**
- conflict detection/write paths operate against session-injected blackboard cleanly

### Step 6 — Remove direct workspace-blackboard construction in subagent path

Update `subagent_runner.py`:
- do not instantiate workspace authority DB directly

**Checkpoint F**
- no hot-path code constructs `workspace/.fa/blackboard/session.db` as authority anymore

### Step 7 — Decide and implement DB failure semantics

Recommended:
- authoritative DB write failure = fail operation / explicit degraded mode
- mirror write failure = warning only

**Checkpoint G**
- partial DB failure no longer yields stale authority success

---

## 3.8 Verification sequence for Slice 1

Verification must be run in this order.

### V1 — Schema/bootstrap verification

1. initialize fresh per-run DB
2. assert tables exist:
   - `event_log`
   - `blackboard`
   - `session_meta`
3. assert indexes exist

### V2 — EventLog authority verification

1. append two events normally
2. read back through `EventLog.read_all()`
3. verify both rows present in correct order

### V3 — Split-brain regression proof

Recreate the exact audit repro class:

1. write first event successfully
2. force authoritative DB write failure on second append
3. assert operation does **not** silently succeed while reader sees stale DB state
4. verify chosen failure behavior explicitly

This is the most important proof in Slice 1.

### V4 — Blackboard authority verification

1. write one blackboard entry
2. query/read it back
3. verify it comes from per-run authority DB

### V5 — Blackboard split-brain regression proof

1. write one entry successfully
2. force authoritative DB write failure on second write
3. assert no stale-authority success path remains

### V6 — Tool-path compatibility verification

Run at least:
- `write_file` path that checks conflicts and writes blackboard record
- `edit_file` path that writes blackboard record

Verify no workspace-blackboard-path assumptions break these tools.

### V7 — Stats compatibility verification

Run `parse_session()` / `fa stats` equivalent on a run-local log and confirm:
- existing consumer still works through `EventLog.read_all()`

### V8 — Negative search verification

After Slice 1, run grep to prove no remaining hot-path authority constructors like:
- `workspace/.fa/blackboard/session.db`
- direct blackboard SQLite init outside the central authority module

---

## 3.9 Tests to add or update

### New tests to add

#### `tests/test_session_db_authority.py` (recommended new file)

Add:
1. `test_session_db_initializes_schema`
2. `test_event_log_authority_read_roundtrip`
3. `test_event_log_no_split_brain_on_db_write_failure`
4. `test_blackboard_authority_read_roundtrip`
5. `test_blackboard_no_split_brain_on_db_write_failure`

This keeps the authority defects isolated and explicit.

### Existing tests likely to update

#### `tests/test_blackboard_conflict.py`
- adapt if it assumes workspace-local DB path

#### `tests/test_inner_loop_tools.py`
- ensure `write_file` / `edit_file` remain blackboard-compatible

#### `tests/test_stats.py`
- ensure stats still consume `EventLog.read_all()` correctly under DB authority

#### `tests/test_cli.py`
- if any tests assert specific filesystem layout assumptions for blackboard, update them

### Nice-to-have test

#### `tests/test_observability_authority_smoke.py`
May be deferred to Slice 2, but if cheap, add a regression skeleton proving runtime observability should not guess stale workspace paths.

---

## 3.10 Anti-theater rules for Slice 1

Do **not** accept the slice as done if:
- tests mock away `sqlite3.connect`
- tests only assert append returned an object
- tests inspect only JSONL mirror content
- tests do not reproduce the partial-failure class discovered in audit
- code still allows stale SQLite reads to eclipse newer mirror rows silently

---

## 3.11 Open design choice inside Slice 1

### Question
Should JSONL mirrors remain in the same run directory or be reduced/disabled during the transition?

### Recommendation
Keep them for now in the same paths to minimize blast radius:
- `~/.fa/session-log/<run_id>/events.jsonl`
- blackboard mirror only if still needed for diffability

But document them as:
- mirrors only,
- not authority,
- potentially removable in later cleanup.

---

## 3.12 Risks to watch while implementing Slice 1

1. **Call-site churn explosion**
   Mitigation: keep `EventLog` and `Blackboard` public APIs stable.

2. **Accidental cross-run coordination regression**
   Mitigation: explicitly state that cross-run workspace coordination is not promised by Slice 1 and will be revisited under subagent/shared-workspace hardening.

3. **Stats/CLI breakage because JSONL assumptions leak everywhere**
   Mitigation: keep mirrors during transition; keep `EventLog.read_all()` stable.

4. **Scope creep into telemetry migration**
   Mitigation: telemetry stays derived for Slice 1 unless it blocks authority cleanup.

---

## 4. Recommended execution checklist

### Slice 0
- [ ] write/confirm D8/D9/D10 decision record
- [ ] grep contradictory phrases to cleanup ledger
- [ ] freeze implementation assumptions for Slice 1

### Slice 1 prep
- [ ] enumerate every current authority write path
- [ ] enumerate every current authority read path
- [ ] design final per-run schema
- [ ] choose JSONL mirror failure policy

### Slice 1 code sequence
- [ ] add `session_db.py`
- [ ] rewire `EventLog`
- [ ] inject session DB through `SessionState`
- [ ] rewire `Blackboard`
- [ ] adapt `write_file.py`
- [ ] adapt `edit_file.py`
- [ ] remove direct workspace blackboard construction from subagent path
- [ ] add split-brain regression tests
- [ ] rerun focused suites

---

## 5. Exit condition before moving to Slice 2

Do not proceed to Slice 2 unless all of the following are true:

1. hot-path event + blackboard authority is per-run and unified
2. partial authoritative DB failure no longer yields fake success + stale reads
3. existing tool callers still work through compatible facades
4. no hot-path code still creates workspace blackboard authority DBs directly
5. tests prove the exact split-brain class is gone

Only then is the substrate stable enough to rewire the observability query plane cleanly.
