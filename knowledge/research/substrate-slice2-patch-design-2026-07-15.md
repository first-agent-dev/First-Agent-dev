# Slice 2 Patch Design — Runtime Observability on Live Authority

**Date:** 2026-07-15  
**Scope:** Slice 2 only  
**Parent:** `knowledge/research/substrate-slice1-closure-pass-and-slice2-init-2026-07-15.md`

---

## 1. Locked Slice 2 decisions

These are already accepted and binding for implementation.

1. `fs_usage` and `fs_chronicle_search` default to **current run only** when an active session exists.
2. When there is **no active session**, runtime observability tools require an **explicit target**.
3. `fa stats` remains **out of Slice 2**.
4. `fs_usage` must rely on authoritative **`usage` event rows only**.
5. Telemetry remains a separate derived surface for now.

---

## 2. Slice 2 goal

Make runtime observability tools consume the **active authoritative session state** instead of:
- guessed workspace JSONL paths,
- stale home paths,
- mismatched event schemas.

Slice 2 is not a DB migration slice.  
Slice 2 is a **tool wiring + schema correctness** slice.

---

## 3. Current verified defects

### D1 — Builder-time path guessing
Current registration still bakes guessed file paths into tool builders.

Relevant files:
- `src/fa/inner_loop/tools/__init__.py`
- `src/fa/inner_loop/profiles.py`

### D2 — `fs_usage` parses the wrong schema
Current implementation still searches for:
- `prompt_tokens`
- `total_tokens`

But live loop writes:
- `input_tokens`
- `output_tokens`
- `cache_read_input_tokens`
- `cache_creation_input_tokens`

### D3 — Direct JSONL reads instead of authoritative EventLog access
Current implementation opens path-bound JSONL directly instead of using the authority-aware `EventLog.read_all()`.

---

## 4. Technical design

## 4.1 Core principle

Observability tools should resolve their target **at handler execution time**, not at builder registration time.

That means:
- current session context can be honored,
- explicit `run_id` can be honored,
- stale builder-time guesses can be removed.

---

## 4.2 Target resolution rules

### Rule A — Active session default
If current session exists and no explicit target is provided:
- use `session.log`
- scope is current run only

### Rule B — Explicit target by `run_id`
If `run_id` is provided:
- use `~/.fa/session-log/<run_id>/events.jsonl`
- `EventLog.read_all()` becomes the authoritative read path

### Rule C — No session and no explicit target
Return structured failure:
- code: `no_active_session`
- retryable: `False`

### Rule D — No heuristic guessing
Do **not** search:
- `workspace/.fa/events.jsonl`
- `workspace/events.jsonl`
- `~/.fa/events.jsonl`

for runtime observability default behavior.

---

## 4.3 API surface changes

### `fs_chronicle_search`
Current required fields:
- `query`

Add optional field:
- `run_id`

Behavior:
- if active session and no `run_id`: search current run
- if `run_id`: search that run
- otherwise: `no_active_session`

### `fs_usage`
Current schema: empty object

Add optional field:
- `run_id`

Behavior:
- if active session and no `run_id`: summarize current run
- if `run_id`: summarize that run
- otherwise: `no_active_session`

---

## 4.4 Data source policy

### `fs_chronicle_search`
Use:
- `EventLog.read_all()`
- search across serialized event content / event metadata in-memory

### `fs_usage`
Use only:
- `kind == "usage"` rows
- `kind == "tool_call"` rows for tool breakdown

Do **not** depend on:
- telemetry JSONL
- old `prompt_tokens` event shapes
- guessed files outside authority path

---

## 4.5 Exact file edit map

### Primary implementation files
- `src/fa/inner_loop/tools/observability.py`
- `src/fa/inner_loop/tools/__init__.py`
- `src/fa/inner_loop/profiles.py`

### Optional support file
- no new support module is strictly required; resolution helper can live in `observability.py`

### Out of scope files
- `src/fa/stats.py`
- `src/fa/telemetry/telemetry.py`
- `src/fa/inner_loop/session_db.py`

---

## 5. Proposed implementation sequence

### Step 1 — Add authority target resolver in `observability.py`

Helper should:
1. inspect current session via contextvar
2. if explicit `run_id` present, resolve run path
3. if current session exists and no explicit `run_id`, use active session log
4. if neither exists, return structured failure reason

### Step 2 — Rework `build_chronicle_search_tool()`

Changes:
- no longer depend on builder-time guessed path
- use target resolver
- use `EventLog.read_all()`
- return matching entries from current run / explicit run

### Step 3 — Rework `build_usage_tool()`

Changes:
- no longer depend on builder-time guessed path
- use target resolver
- parse authoritative `usage` rows only for token totals
- count `tool_call` rows for breakdown
- compute cache ratio from authoritative usage totals

### Step 4 — Remove path-guessing registration pressure

Update:
- `src/fa/inner_loop/tools/__init__.py`
- `src/fa/inner_loop/profiles.py`

to stop passing guessed event-log paths as if they were authoritative runtime defaults.

---

## 6. Verification plan

### V1 — Active session default proof

1. create active `SessionState`
2. append real rows via `EventLog`
3. dispatch `fs_usage` with no `run_id`
4. assert it reads the current run and returns real usage totals

### V2 — `fs_chronicle_search` active run proof

1. active session with known rows
2. dispatch `fs_chronicle_search` with query only
3. assert current run rows returned

### V3 — No active session failure proof

1. no current session
2. dispatch `fs_usage` without `run_id`
3. assert structured `no_active_session` failure
4. same for `fs_chronicle_search`

### V4 — Explicit run-id proof

1. create run log under `~/.fa/session-log/<run_id>/events.jsonl`
2. no active session
3. dispatch with `run_id`
4. assert correct rows returned

### V5 — No heuristic fallback proof

1. place misleading `workspace/.fa/events.jsonl`
2. no active session and no `run_id`
3. assert failure, not accidental success

---

## 7. New tests to add

Recommended new file:
- `tests/test_observability_runtime_authority.py`

Suggested tests:
1. `test_usage_defaults_to_current_run_authority`
2. `test_chronicle_search_defaults_to_current_run_authority`
3. `test_usage_requires_explicit_target_without_active_session`
4. `test_chronicle_search_requires_explicit_target_without_active_session`
5. `test_usage_explicit_run_id_reads_run_authority`
6. `test_chronicle_search_does_not_guess_workspace_events_path`

---

## 8. Anti-theater rules

The slice is not done if tests only:
- inspect builder arguments,
- inspect guessed path strings,
- or check descriptions without dispatching tools.

At least one test per tool must go through:
- actual registry/tool handler
- actual current session context or explicit run-id path
- actual `EventLog.read_all()` authority path

---

## 9. Done definition

Slice 2 is done when:
1. runtime observability tools default to current run only,
2. no active session requires explicit `run_id`,
3. `fs_usage` reads authoritative `usage` rows correctly,
4. `fs_chronicle_search` reads authority via `EventLog`,
5. path guessing is removed from the runtime observability default path.
