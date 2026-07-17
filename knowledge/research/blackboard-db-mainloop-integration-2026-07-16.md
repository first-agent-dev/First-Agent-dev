# Blackboard, SQLite Session DB, and Global History DB — Integration with the Main Loop

> Research date: 2026-07-16  
> Scope: Deep technical explanation of how blackboard, SQLite databases, and the main loop are integrated, and how existing artifacts map onto this system.

---

## 1. The Initialization Chain: `fa run` → SessionState → EventLog → SessionDatabase → Blackboard

When a session starts, the system bootstraps through a strict dependency chain. Each layer depends on the previous one, and failures degrade gracefully rather than crashing:

```
fa run
  └─ _cmd_run()                          [cli.py:1576]
       ├─ EventLog(log_path, run_id)     [state.py:95]
       │    └─ SessionDatabase(           [state.py:101]
       │         path.parent / "session.db"
       │       )                          → ~/.fa/session-log/<run_id>/session.db
       │
       ├─ SessionState(                   [state.py:234]
       │     workspace_root, run_id, log, pty_pool
       │   )
       │    └─ __post_init__:
       │         ├─ self.session_db = self.log.session_db   (shared instance!)
       │         ├─ FeatureFlags loaded from ~/.fa/config.yaml
       │         ├─ Transaction created (always)
       │         ├─ ArtifactStore lazy-init (workspace/.fa/artifacts)
       │         ├─ Blackboard lazy-init (requires session_db + feature flag)
       │         └─ TelemetryLogger lazy-init (if enabled)
       │
       └─ drive_session(state, ...)       [coder_loop.py:359]
            └─ set_current_session(state)  [context.py]
                 └─ ContextVar[SessionState | None]
                      └─ Tool handlers call get_current_session()
                           → session.blackboard, session.session_db, etc.
```

**Key insight:** `EventLog` and `Blackboard` share the **same** `SessionDatabase` instance. The `EventLog` creates it during construction, then `SessionState.__post_init__` copies the reference (`self.session_db = self.log.session_db`), and the Blackboard receives it in its constructor. This means event_log, blackboard, and session_meta tables all live in the same per-run SQLite file under a single write lock.

---

## 2. SessionDatabase — The Per-Run Authority

**Location:** `~/.fa/session-log/<run_id>/session.db`  
**Source:** `src/fa/inner_loop/session_db.py`  
**Concurrency model:** `threading.Lock` + short-lived connections + `busy_timeout=15000ms`

### Schema (3 tables)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `event_log` | Authoritative event records | `event_id`, `ts`, `run_id`, `actor`, `kind`, `tool_name`, `tool_call_id`, `parent_event_id`, `content`, `harness_id` |
| `blackboard` | Blackboard entries | `id`, `run_id`, `type`, `content_hash`, `toolchain_digest`, `schema_version`, `parent_id`, `read_set`, `write_set`, `assumptions`, `version_dependencies`, `timestamp`, `payload` |
| `session_meta` | Key-value metadata | `key`, `value`, `updated_at` |

### Write discipline

All writes go through `SessionDatabase` methods which acquire `_write_lock` and use short-lived `sqlite3.Connection` objects. This ensures thread-safety for Phase 2 parallel tool batching without requiring a persistent connection.

---

## 3. EventLog — Dual-Write Authority + JSONL Mirror

**Source:** `src/fa/inner_loop/state.py:83-230`

The `EventLog` follows a **dual-write** pattern with strict ordering:

1. **Authoritative write** to `SessionDatabase.append_event_row()` — if `session_db` is `None`, this **raises `RuntimeError`**. The authority must never be absent for event writes.
2. **Advance logical ID** — only after the authoritative commit succeeds.
3. **Best-effort JSONL mirror** — writes to `events.jsonl`. If this fails, only a warning is logged; the session continues.

For reads (`read_all`):
1. Try `session_db.read_event_rows()` first (authoritative).
2. Fall back to JSONL parsing only if the DB read fails.

```
EventLog.append()
  ├─ session_db.append_event_row(asdict(event))  ← authority, raises on failure
  ├─ _next_id += 1                                ← only after commit
  └─ JSONL mirror write                           ← best-effort, never crashes
```

---

## 4. Blackboard — Typed Append-Only Content-Hashed Store

**Source:** `src/fa/blackboard/blackboard.py`  
**Workspace mirror:** `<workspace>/.fa/blackboard/blackboard.jsonl`

### Construction

```python
Blackboard(
    path=workspace_root / ".fa" / "blackboard",
    session_db=self.session_db,   # SAME instance as EventLog
    run_id=self.run_id,
)
```

The Blackboard **cannot exist** without a `SessionDatabase`. If `session_db is None`, `_ensure_blackboard` logs a warning and sets `self.blackboard = None`.

### BlackboardEntry structure

```python
@dataclass
class BlackboardEntry:
    id: str                          # unique entry identifier
    type: str                        # entry type (e.g., "file_edit", "file_write")
    content_hash: str                # SHA-256 hash of payload content
    toolchain_digest: str            # hash of the tool chain that produced this
    schema_version: str              # schema versioning for migration safety
    parent_id: str | None            # links to parent entry (provenance chain)
    read_set: list[str]              # paths/resources read before this write
    write_set: list[str]             # paths/resources written by this entry
    assumptions: list[str]           # stated assumptions at write time
    version_dependencies: dict       # version constraints
    timestamp: str                   # ISO-8601 UTC
    payload: Any                     # the actual entry data
```

### Write path (same dual-write as EventLog)

```
Blackboard.write(entry)
  ├─ session_db.write_blackboard_row(asdict(entry))  ← authority
  └─ JSONL mirror to blackboard.jsonl                ← best-effort
```

### Read/query path

```
Blackboard.read(entry_id)
  ├─ session_db.read_blackboard_row(id)  ← authority, try first
  └─ JSONL fallback                      ← only if DB read fails

Blackboard.query(filters)
  ├─ session_db.query_blackboard_rows(filters)  ← authority
  └─ JSONL fallback                              ← only if DB fails
```

### Conflict detection

`Blackboard.detect_conflict()` checks:
- **Read/write overlaps**: If entry B's `read_set` intersects with entry A's `write_set`, and A was written after B started, there's a conflict.
- **Assumption violations**: If an entry's stated `assumptions` are contradicted by a later entry's `write_set`.

This enables the system to detect when concurrent tool calls have stomped on each other's reads.

---

## 5. Transaction — Read/Write Set Accumulation

**Source:** `src/fa/inner_loop/transaction.py`

The `Transaction` object is always initialized (unlike Blackboard, which is conditional). It accumulates:

- `read_set`: paths/resources that have been read during the session
- `write_set`: paths/resources that have been written during the session

The Blackboard uses these sets when constructing `BlackboardEntry` instances. Tool handlers call `session.transaction.add_read(path)` and `session.transaction.add_write(path)` to track their resource accesses, which then feed into the Blackboard's conflict detection.

---

## 6. Where Blackboard Writes Happen During a Run

| Tool Handler | Source | What it writes |
|-------------|--------|----------------|
| `edit_file` | `src/fa/inner_loop/tools/edit_file.py:139` | `BlackboardEntry` with `type="file_edit"`, `write_set=[edited_path]` |
| `write_file` | `src/fa/inner_loop/tools/write_file.py:148` | `BlackboardEntry` with `type="file_write"`, `write_set=[written_path]` |

Both tool handlers:
1. Get the current session via `get_current_session()`
2. Access `session.blackboard`
3. Construct a `BlackboardEntry` with the relevant `read_set`, `write_set`, and `payload`
4. Call `blackboard.write(entry)` which writes to both SQLite authority and JSONL mirror

---

## 7. GlobalHistoryStore — Derived Cross-Run Analytics Projection

**Source:** `src/fa/inner_loop/global_history.py`  
**Location:** `~/.fa/global_history.db` (separate database!)  
**Key principle:** This is a **derived projection**, NOT hot-path authority.

### Schema (1 table)

```sql
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT, updated_at TEXT,
    role TEXT, model TEXT, family TEXT,
    exit_code INTEGER, stop_reason TEXT,
    turns INTEGER,
    input_tokens INTEGER, output_tokens INTEGER,
    cache_read_input_tokens INTEGER, cache_creation_input_tokens INTEGER,
    cache_hit_ratio REAL,
    tool_calls_total INTEGER, tool_calls_breakdown_json TEXT,
    has_compaction_summary INTEGER,
    workspace_root TEXT,
    duration_ms INTEGER
);
```

### When it's populated

At session end, inside `_cmd_run()` (cli.py:1838-1855):

```python
try:
    from fa.inner_loop.global_history import export_session_to_global_history
    export_session_to_global_history(
        run_id=run_id,
        session_log_dir=session_log_dir,
        ...
    )
except Exception as exc:
    # best-effort, never crashes main
    logging.getLogger(__name__).warning("global_history export failed for %s: %s", run_id, exc)
```

### Active consumer

`fa stats --global-history` (cli.py:2099-2105) reads from `~/.fa/global_history.db` to display cross-run analytics. This is the only active consumer.

### Design constraints

- **No hot-path module imports this for correctness** — it's purely analytics.
- Uses `INSERT OR REPLACE` for idempotency.
- Same concurrency model as `SessionDatabase`: `threading.Lock` + WAL + short-lived connections.

---

## 8. ArtifactStore — Content-Addressed Tool Result Offloads

**Source:** `src/fa/inner_loop/artifacts.py`  
**Location:** `<workspace>/.fa/artifacts/`

When tool results are too large to keep in the event stream, they're offloaded to the artifact store:

```
tool-result-<sha256[:16]>.json
```

This keeps the `event_log` table lean while preserving full outputs for post-hoc analysis. The `ArtifactStore` is lazy-initialized in `SessionState.__post_init__` and accessed through `session.artifact_store`.

---

## 9. The Full Data Flow Diagram

```
                          ┌─────────────────────────────────────────────────┐
                          │              fa run (_cmd_run)                  │
                          └───────────────┬─────────────────────────────────┘
                                          │
                              creates EventLog + SessionState
                                          │
              ┌───────────────────────────┼───────────────────────────────┐
              │                           │                               │
    ┌─────────▼─────────┐     ┌───────────▼───────────┐     ┌────────────▼──────────┐
    │   EventLog        │     │   SessionState        │     │   GlobalHistoryStore  │
    │                   │     │                       │     │                       │
    │  append() ────────┼─┐   │  session_db ◄─────────┼─┐   │  @ session end only   │
    │  read_all()       │ │   │  blackboard           │ │   │  export_session_to_   │
    │                   │ │   │  transaction           │ │   │  global_history()     │
    └───────────────────┘ │   │  artifact_store        │ │   │                       │
                          │   │  telemetry             │ │   │  ~/.fa/               │
                          │   │  feature_flags         │ │   │  global_history.db    │
                          │   │  pty_pool              │ │   └───────────────────────┘
                          │   └───────────────────────┘ │
                          │                             │
              ┌───────────▼─────────────────────────────▼──────────┐
              │          SessionDatabase (per-run authority)       │
              │                                                   │
              │   ~/.fa/session-log/<run_id>/session.db           │
              │                                                   │
              │   ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
              │   │ event_log   │ │ blackboard   │ │session_meta│ │
              │   │ (authority) │ │ (authority)  │ │ (key-value)│ │
              │   └─────────────┘ └─────────────┘ └────────────┘ │
              └───────────────────────┬───────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────────┐
                    │                 │                     │
          ┌─────────▼──────┐ ┌───────▼────────┐  ┌────────▼─────────┐
          │ events.jsonl   │ │ blackboard/    │  │ pr_draft.md      │
          │ (JSONL mirror) │ │ blackboard.    │  │ eval_report.json │
          │                │ │ jsonl          │  │ flow_state.json  │
          │ best-effort    │ │ (JSONL mirror) │  │ attempt_history  │
          └────────────────┘ │ best-effort    │  │ .json            │
                             └────────────────┘  └──────────────────┘
```

---

## 10. How Existing Artifacts Map onto This System

### Per-run artifacts (under `~/.fa/session-log/<run_id>/`)

| Artifact | File | Relationship to DB | Notes |
|----------|------|-------------------|-------|
| Event stream (authority) | `session.db` → `event_log` table | **Primary authority** | All tool calls, LLM interactions, system events |
| Event stream (mirror) | `events.jsonl` | Secondary mirror | Best-effort JSONL; useful for `cat`/`grep`/`diff` but not authoritative |
| Blackboard state (authority) | `session.db` → `blackboard` table | **Primary authority** | Content-hashed entries with read/write sets |
| Blackboard state (mirror) | `blackboard.jsonl` (under workspace) | Secondary mirror | Same best-effort pattern as events.jsonl |
| PR draft | `pr_draft.md` | Standalone file artifact | Written by PR creation tool |
| Eval report | `eval_report.json` | Standalone file artifact | Workflow eval verdict |
| Flow state | `flow_state.json` | Standalone file artifact | Workflow controller state |
| Attempt history | `attempt_history.json` | Standalone file artifact | Recovery attempt log |

### Workspace artifacts (under `<workspace>/.fa/`)

| Artifact | Path | Relationship to DB | Notes |
|----------|------|-------------------|-------|
| Blackboard JSONL mirror | `.fa/blackboard/blackboard.jsonl` | Mirror of `session.db.blackboard` | Same dual-write pattern |
| Artifact store | `.fa/artifacts/tool-result-<sha>.json` | Complements event_log | Offloads elided tool results |
| Subagent envelopes | `.fa/subagents/<task_id>.json` | Standalone | Subagent spawn results |
| FTS index | `.fa/fts.db` | Independent SQLite | FTS5 full-text search over workspace |

### Cross-run artifacts

| Artifact | Path | Relationship to DB | Notes |
|----------|------|-------------------|-------|
| Global history | `~/.fa/global_history.db` → `runs` table | **Derived projection** from all session.db files | Populated at session end, best-effort |
| Config | `~/.fa/config.yaml` | Controls FeatureFlags | Loaded by `SessionState.__post_init__` |
| Models | `~/.fa/models.yaml` | Read-only routing config | Mounted into containers |

### Knowledge/documentation artifacts (under `knowledge/`)

| Artifact | Purpose | Mapping |
|----------|---------|---------|
| `llms.txt` | BY-DEMAND INDEX for agent context loading | **Deprecated in favor of blackboard.query()** — the blackboard now provides structured, content-hashed, queryable access to session state that llms.txt tried to serve as a flat index for |
| `HANDOFF.md` | Cross-session worklog | **Could be superseded by blackboard entries** with `type="handoff"` — the blackboard provides richer semantics (read_set, write_set, assumptions) that handoff notes currently lack |
| `MAINTENANCE.md` | Doc maintenance rules | Standalone convention — no DB integration needed |
| `AGENTS.md` | Session loadout | Read by the prompt composer, no DB integration |
| `trace/exploration_log.md` | Exploration trace | Could map to blackboard entries with `type="exploration"` |
| `trace/codebase_map.json` | Codebase map | Could map to blackboard entries with `type="codebase_map"` |
| `trace/exploration_tree.yaml` | Exploration tree | Marked "superseded" — candidate for pruning |
| Research notes | 60+ files under `knowledge/research/` | Standalone research artifacts, no DB integration |
| ADR files | 16 ADRs + DIGEST.md | Architectural decisions, reference-only |
| Skills | 5 SKILL.md files | Convention-based, no DB integration |
| Templates | 3 template files | Reference config, no DB integration |

---

## 11. The ContextVar Dependency Injection Pattern

Tool handlers never receive `SessionState` as a parameter. Instead, they use:

```python
# src/fa/inner_loop/context.py
_current_session: ContextVar[SessionState | None] = ContextVar("current_session", default=None)

def set_current_session(session: SessionState) -> Token[...]:
    return _current_session.set(session)

def get_current_session() -> SessionState | None:
    return _current_session.get()
```

In `drive_session()` (coder_loop.py:359):
```python
token = set_current_session(state)
try:
    ...  # run the loop
finally:
    reset_current_session(token)
```

Tool handlers then access:
```python
session = get_current_session()
blackboard = session.blackboard       # may be None if disabled
session_db = session.session_db       # may be None if degraded
transaction = session.transaction     # always initialized
artifact_store = session.artifact_store
```

This pattern ensures that even though tools are called from many different code paths, they all access the same per-session state without tight coupling to the session lifecycle.

---

## 12. Feature Flag Gating

The Blackboard and Telemetry subsystems are gated by `FeatureFlags`:

| Flag | Default | Effect |
|------|---------|--------|
| `blackboard_enabled` | `True` | Enables Blackboard initialization and write operations |
| `telemetry_enabled` | `True` | Enables TelemetryLogger initialization |

FeatureFlags are loaded from `~/.fa/config.yaml` in `SessionState.__post_init__`. If loading fails, defaults are used. If even the defaults fail, `feature_flags` is `None` and subsystems degrade gracefully.

The recently-declared phantom flag `blackboard_filtered_history_include_plans` was added to the `FeatureFlags` dataclass to resolve a `getattr` call that was accessing an undeclared attribute.

---

## 13. Summary: Authority Hierarchy

```
┌──────────────────────────────────────────────────────────────┐
│                    AUTHORITY HIERARCHY                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Per-run SessionDatabase (session.db)                     │
│     ├── event_log table    ← EventLog authority              │
│     ├── blackboard table   ← Blackboard authority            │
│     └── session_meta table ← Metadata authority              │
│                                                              │
│  2. JSONL mirrors (events.jsonl, blackboard.jsonl)           │
│     └── Best-effort, non-authoritative, for audit/diff       │
│                                                              │
│  3. Global History DB (global_history.db)                    │
│     └── Derived projection, populated at session end         │
│                                                              │
│  4. File artifacts (pr_draft.md, eval_report.json, etc.)     │
│     └── Standalone, not replicated in DB                     │
│                                                              │
│  5. Workspace artifacts (.fa/artifacts/, .fa/subagents/)     │
│     └── Content-addressed or task-addressed supplements      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

The design principle is clear: **SQLite is the single source of truth for hot-path runtime state**. JSONL files exist as human-readable mirrors for ad-hoc inspection. The global history DB is a derived analytics projection that should never be imported by hot-path code for correctness.
