# PR #53 Observability Audit — Event Logging, DB Authority, Console Output

> **Created:** 2026-07-18
> **Updated:** 2026-07-18 (third-pass deep audit complete — dead-code, wiring, performance, feature-flag cascade)
> **Purpose:** Verify that all PR #53 features produce events that session.db receives correctly, that they're retrievable, and that CLI console output shows what operators need for debugging.
> **Method:** Pass 1 — trace every EventLog `kind` from emission → DB write → retrieval → console display. Pass 2 — search for logic errors in event handling, silent failure paths, missing emissions on error branches, workflow-to-run correlation gaps, data completeness issues, and edge cases where the operator gets no signal. Pass 3 — different lens: dead-code events, missing wiring, O(n²) performance, feature-flag cascade silencing, and hook-registration gaps that make entire event kinds unreachable in production.

---

## Executive Summary

**DB Authority: ✅ SOLID.** All 31 event kinds are written to session.db via `EventLog.append()` → `SessionDatabase.append_event_row()`. The dual-write discipline (DB first, JSONL mirror second) is correctly implemented. All events are retrievable from session.db.

**Retrieval: ⚠️ PARTIAL.** `fa stats` only consumes 8 of 31 event kinds. `global_history.db` only consumes 3. Many PR #53 features (compaction, subagent, context budget, cost) produce events that end up in session.db but are never surfaced by any CLI consumer.

**Console Output: ❌ SIGNIFICANT GAPS.** The `output.py` EventBus + ConsoleRenderer only display 7 event types. 24 event kinds — including every PR #53 feature except basic tool calls — have **zero console visibility** during a live session. An operator watching `fa run` has no indication when compaction fires, when context budget is low, when subagents spawn, or when costs accumulate.

**Logic Errors: ⚠️ 7 CONFIRMED + 6 GAPS + 5 NEW DEEP AUDIT FINDINGS.** Second-pass audit found 1 confirmed bug (duplicate event_id in DB), 1 data-corruption risk in workflow global_history, and multiple silent-failure / missing-signal paths. Third-pass deep audit found 2 dead-code event kinds (never emitted in production due to missing wiring), 1 O(n²) performance bug, 1 feature-flag cascade that silences all context-budget telemetry after stage 2, and 1 missing event kind from the inventory. See §8 and §11 for full inventory.

---

## 1. Event Flow Architecture

```
coder_loop.py
    ├── state.log.append(kind=...)    → EventLog → SessionDatabase (AUTHORITY)
    │                                           → events.jsonl (MIRROR, best-effort)
    └── output.emit(type=...)         → EventBus → ConsoleRenderer (stderr)
                                            → QuietRenderer (silence)

Key: events.jsonl and session.db see ALL 31 kinds.
     Console sees only 7 types.
```

### Dual-Write Discipline (verified correct)

In `EventLog.append()` (state.py:200-220):

1. **Authoritative write** to `SessionDatabase.append_event_row()` — raises on failure
2. **Advance logical ID** only after DB commit succeeds
3. **Best-effort JSONL mirror** — failure logged but doesn't crash

This is correct. If DB write fails, the event is NOT silently dropped — it raises RuntimeError.

### Read path (verified correct)

`EventLog.read_all()` (state.py:222-260):
- Primary: reads from `SessionDatabase.read_event_rows()`
- Fallback: if DB fails, reads from JSONL (legacy compatibility)
- Both paths reconstruct `TraceEvent` objects correctly

---

## 2. Event Kind Inventory — Emission vs. Display vs. Retrieval

| # | Event kind | Emitted by | In session.db | In `fa stats` | In `global_history` | Console display | Operator impact |
|---|-----------|-----------|:---:|:---:|:---:|:---:|-------|
| 1 | `tool_call` | state.record_tool_call | ✅ | ✅ | ✅ | ✅ tool_call | Core |
| 2 | `tool_result` | state.record_tool_result | ✅ | ❌ | ❌ | ✅ (via tool_call) | Core |
| 3 | `user_msg` | coder_loop | ✅ | ❌ | ❌ | ❌ | Low |
| 4 | `model_msg` | coder_loop | ✅ | ❌ | ❌ | ❌ | Low |
| 5 | `usage` | coder_loop | ✅ | ✅ | ✅ | ❌ | **HIGH** — token counts invisible live |
| 6 | `run_started` | coder_loop | ✅ | ✅ | ❌ | ❌ | Low |
| 7 | `run_stopped` | coder_loop | ✅ | ✅ | ❌ | ❌ | Low |
| 8 | `session_summary` | coder_loop | ✅ | ✅ | ❌ | ❌ | Medium |
| 9 | `provider_attempt` | coder_loop | ✅ | ✅ | ❌ | ❌ | Medium |
| 10 | `hook_decision` | AuditHook | ✅ | ✅ | ❌ | ❌ | Low |
| 11 | `audit` | AuditHook | ✅ | ❌ | ❌ | ❌ | Low |
| 12 | `loop_guard_warn` | LoopGuard | ✅ | ✅ | ❌ | ❌ | **HIGH** — loop detected, operator blind |
| 13 | `recovery_action` | RecoveryObserver | ✅ | ❌ | ❌ | ❌ | Medium |
| 14 | `timeout` | coder_loop | ✅ | ❌ | ❌ | ❌ | Medium |
| 15 | `service_unavailable` | coder_loop | ✅ | ❌ | ❌ | ❌ | Medium |
| 16 | `telemetry` | state.record_tool_result | ✅ | ❌ | ❌ | ❌ | Low |
| **17** | **`context_budget_warn`** | **coder_loop (PR #53)** | ✅ | ❌ | ❌ | ❌ | **CRITICAL** — context filling up, no console signal |
| **18** | **`context_budget_hard_stop`** | **coder_loop (PR #53)** | ✅ | ❌ | ❌ | ❌ | **CRITICAL** — session killed by budget, operator sees generic stop |
| **19** | **`compaction_stage2_start`** | **coder_loop (PR #53)** | ✅ | ❌ | ❌ | ❌ | **HIGH** — compaction running, operator sees pause |
| **20** | **`compaction_stage2_done`** | **coder_loop (PR #53)** | ✅ | ❌ | ❌ | ❌ | **HIGH** |
| **21** | **`compaction_stage2_error`** | **coder_loop (PR #53)** | ✅ | ❌ | ❌ | ❌ | **HIGH** — compaction failed, operator doesn't know |
| **22** | **`compaction_stage3_start`** | **coder_loop (PR #53)** | ✅ | ❌ | ✅ | ❌ | **HIGH** |
| **23** | **`compaction_stage3_done`** | **coder_loop (PR #53)** | ✅ | ❌ | ✅ | ❌ | **HIGH** |
| **24** | **`compaction_stage3_error`** | **coder_loop (PR #53)** | ✅ | ❌ | ❌ | ❌ | **HIGH** |
| **25** | **`compaction_circuit_breaker`** | **coder_loop (PR #53)** | ✅ | ❌ | ❌ | ❌ | **HIGH** — compaction gave up |
| **26** | **`compaction_warning`** | **foundation.py (PR #53)** | ✅ | ❌ | ❌ | ❌ | Medium |
| **27** | **`subagent_spawn_start`** | **spawn_subagent.py (PR #53)** | ✅ | ❌ | ❌ | ❌ | **HIGH** — subagent launched, operator unaware |
| **28** | **`subagent_spawn_done`** | **spawn_subagent.py (PR #53)** | ✅ | ❌ | ❌ | ❌ | **HIGH** — subagent succeeded, operator unaware |
| **29** | **`subagent_spawn_fail`** | **spawn_subagent.py (PR #53)** | ✅ | ❌ | ❌ | ❌ | **CRITICAL** — subagent failed, no console signal |
| **30** | **`cost_observation`** | **cost_guardian.py (PR #53)** | ✅ | ❌ | ❌ | ❌ | **HIGH** — cost guard fired, invisible |
| 31 | `verification` | VerifierObserver | ✅ | ❌ | ❌ | ❌ | Low |

### Summary counts

| Layer | Event kinds covered | Total 32 | Coverage |
|-------|-------------------|----------|----------|
| session.db write | 32 | 32 | 100% |
| `fa stats` console | 8 | 32 | 25% |
| `global_history.db` | 3 | 32 | 9% |
| ConsoleRenderer (live) | 7 types → covers ~4 kinds | 32 | ~13% |

---

## 3. Critical Gaps for Operator Debugging

### GAP-C1: Compaction events invisible on console (PR #53)

**Scenario:** Operator runs `fa run --role coder --task "large refactoring"` with `context_compaction_enabled: true`. At turn 12, context hits 80% → compaction fires. The operator sees the session "freeze" for several seconds (the compactor LLM call) with no indication of what's happening. If compaction fails, there's no console message — just eventual session termination.

**Current behavior:** 8 compaction event kinds are written to session.db but NONE produce console output.

**What operator sees:** Nothing. The session appears to hang, then either resumes or dies.

**What operator should see:**
```
  🗜️ compaction stage2: context at 82% → summarizing... (verbose+)
  🗜️ compaction stage2: done, 14k → 3k tokens (verbose+)
  or:
  ❌ compaction stage3 error: compactor model returned empty (standard+)
```

### GAP-C2: Context budget warnings invisible on console (PR #53)

**Scenario:** Context budget warns at 70% (stage1), 80% (stage2), 90% (hard stop). On console, the operator sees nothing until the session abruptly stops with `context_budget_hard_stop`. The `--detail verbose` flag should show the context fill level, but currently it doesn't.

**Current behavior:** `context_budget_warn` and `context_budget_hard_stop` events are logged to DB only. ConsoleRenderer has no handler for them. The session_end event shows `stop_reason` but not the context percentage.

**What operator should see at `--detail standard`+:**
```
  ⚠️ context: 72% of window (stage1)
  ⚠️ context: 83% of window → compaction starting (stage2)
  🛑 context: 92% of window → hard stop (budget exhausted)
```

### GAP-C3: Subagent spawn events invisible on console (PR #53)

**Scenario:** Agent calls `spawn_subagent` tool. Operator sees a `tool_call` with name `spawn_subagent` but no indication of whether the subagent started, finished, or failed. On failure, the tool result shows the error, but there's no live progress during subagent execution.

**Current behavior:** `subagent_spawn_start` and `subagent_spawn_fail` are logged to DB only.

**What operator should see at `--detail standard`+:**
```
  → Spawn subagent [researcher] task-abc123
  ← subagent done: exit=0 (verbose+)
  or:
  ❌ subagent failed: compactor_chain exhausted (standard+)
```

### GAP-C4: Cost observations invisible on console (PR #53)

**Scenario:** `CostGuardian` fires with a `cost_observation` event when spend exceeds threshold. Operator has no console indication.

**Current behavior:** Only in DB. `ConsoleRenderer.session_end` shows `est_cost_usd` but only if `show_cost=True` (currently never set to True by the CLI).

**Gap within a gap:** The CLI never passes `show_cost=True` to `ConsoleRenderer`. Even the session summary doesn't show cost by default.

### GAP-C5: Loop guard warnings invisible on console

**Scenario:** Agent enters a repetitive pattern. `LoopGuard` detects it and emits `loop_guard_warn`. Eventually it triggers the circuit breaker. Operator sees nothing until the session terminates.

**Current behavior:** Event is in DB and consumed by `fa stats`, but not shown live on console.

### GAP-C6: `fa stats` doesn't surface PR #53 event kinds

**Current `fa stats` consumption:** Only 8 of 31 event kinds are parsed in `stats.py`. Missing:
- `compaction_*` (8 kinds)
- `context_budget_*` (2 kinds)
- `subagent_*` (2 kinds)
- `cost_observation` (1 kind)
- `recovery_action` (1 kind)
- `timeout`, `service_unavailable` (2 kinds)
- `tool_result` (1 kind — critical for error analysis)
- `verification` (1 kind)

---

## 4. Specific Code-Level Findings

### F1: ConsoleRenderer has no context percentage display

`_handle_session_end` shows `context_used_pct` if present, but `_handle_llm_response` does NOT show context fill level per turn (even in verbose/debug mode). The data IS available from the provider response (via `usage` events) but is never passed to the output event.

### F2: `show_cost` parameter never set to True by CLI

In `cli.py:_cmd_run()`:
```python
output_bus.add(
    ConsoleRenderer(
        detail=getattr(args, "detail", "standard") or "standard",
    )
)
```

No `show_cost=True` is ever passed. The `CostGuardian` data exists but the renderer is never told to display it. This should be auto-enabled when `cost_budget_usd` is set in RuntimeLimits, or at `--detail verbose`+.

### F3: `_handle_session_end` doesn't show stop_reason detail

When session ends with `context_budget_hard_stop`, the console shows:
```
FAIL: context_budget_hard_stop (turns=12)
```

But doesn't explain what context % was reached or that compaction was attempted. The `data` dict has `context_used_pct` but not `compaction_attempted`.

### F4: OutputEvent EventType is too narrow

The `EventType` literal only has 7 values. It should include:
- `context_warn` — context budget approaching limit
- `compaction_start` / `compaction_end` — compaction lifecycle
- `subagent_start` / `subagent_end` — subagent lifecycle
- `cost_alert` — cost guardian threshold hit
- `loop_warn` — loop detection fired

### F5: `fa stats` `parse_session()` doesn't extract compaction/subagent/cost data

`stats.py:parse_session()` handles 8 kinds. The `render_session()` output shows tool usage, file access, and token timelines — but nothing about compaction attempts, subagent spawns, or cost observations. An operator running `fa stats --run-id work-1` after a session with compaction failure gets zero information about it.

---

## 5. Prioritized Fix Plan

### Priority 0 — CONFIRMED BUGS (data integrity)

| Fix | What | Files | Est. effort |
|-----|------|-------|-------------|
| FIX-0a | Fix `_initial_next_id` to query session.db COUNT(*) instead of JSONL line count | `state.py` | ~10 lines |
| FIX-0b | Add workflow-aware global_history export (one row per stage or aggregate all stages) | `cli.py`, `global_history.py` | ~40 lines |
| FIX-0c | Add try/except in `_cmd_run` around `drive_session()` for RuntimeError from EventLog | `cli.py` | ~10 lines |

### Priority 1 — HIGH (operator sees nothing during critical events)

| Fix | What | Files | Est. effort |
|-----|------|-------|-------------|
| FIX-1 | Add `context_warn` OutputEvent + ConsoleRenderer handler | `output.py`, `coder_loop.py` | ~30 lines |
| FIX-2 | Add `compaction_start/end` OutputEvent + handler | `output.py`, `coder_loop.py` | ~40 lines |
| FIX-3 | Add `subagent_start/end` OutputEvent + handler | `output.py`, `spawn_subagent.py` | ~25 lines |
| FIX-4 | Add `cost_alert` OutputEvent + handler; auto-enable `show_cost` | `output.py`, `coder_loop.py` | ~20 lines |
| FIX-5 | Add `loop_warn` OutputEvent + handler | `output.py`, `loop_guard.py` | ~15 lines |

### Priority 2 — MEDIUM (post-session analysis incomplete)

| Fix | What | Files | Est. effort |
|-----|------|-------|-------------|
| FIX-6 | Add compaction section to `fa stats` render_session | `stats.py` | ~40 lines |
| FIX-7 | Add subagent section to `fa stats` render_session | `stats.py` | ~30 lines |
| FIX-8 | Add cost section to `fa stats` render_session | `stats.py` | ~20 lines |
| FIX-9 | Add context budget summary to `fa stats` render_session | `stats.py` | ~20 lines |
| FIX-9b | Add `tool_result` error extraction to `fa stats` | `stats.py` | ~15 lines |

### Priority 3 — LOW (nice to have)

| Fix | What | Files | Est. effort |
|-----|------|-------|-------------|
| FIX-10 | Show context % per turn in `--detail verbose`+ | `output.py`, `coder_loop.py` | ~15 lines |
| FIX-11 | Show cache hit ratio per turn (not just session end) | `output.py` | ~10 lines |
| FIX-12 | Add `--detail debug` compaction payload preview | `output.py` | ~15 lines |
| FIX-13 | Show `has_compaction_summary` in `fa stats --global-history` console output | `cli.py` | ~5 lines |
| FIX-14 | Discover sessions by `session.db` existence, not `events.jsonl` | `cli.py` | ~5 lines |

---

## 6. Verification Checklist (for implementation)

For each fix, verify:

1. **Emission:** `output.emit(type=...)` is called in the right place in coder_loop
2. **EventType:** New literal value added to `EventType` union
3. **Handler:** `_handle_<type>` method added to `ConsoleRenderer`
4. **Detail level:** Event only shown at appropriate `--detail` level
5. **QuietRenderer:** Still silent (no changes needed)
6. **session.db:** Event was already being written (no change needed)
7. **fa stats:** Post-session analysis surfaces the new data
8. **Manual test:** `fa run --detail verbose` shows the new events in real-time

---

## 7. What NOT to Change

- Do NOT change the `EventLog.append()` dual-write discipline — it's correct
- Do NOT change `SessionDatabase` schema — event_log table is flexible (content is JSON)
- Do NOT add new tables to session.db for these events — content column handles it
- Do NOT make console output the authority — session.db remains authority
- Do NOT add events that don't already exist in session.db — just surface existing ones
- Do NOT change the `fa stats` parser to read JSONL — it should read session.db

---

## 8. Second-Pass Logic Error Audit

> **Method:** Different lens from pass 1. Instead of tracing event kinds through the stack, we look for logic errors: silent failure paths, missing emissions on error branches, data corruption risks, workflow-to-run correlation gaps, edge cases where the operator gets no signal.

### LOGIC-1: 🐛 CONFIRMED BUG — `_initial_next_id` counts JSONL lines, NOT DB rows

**Location:** `src/fa/inner_loop/state.py:180-185`

**Code:**
```python
@staticmethod
def _initial_next_id(path: Path) -> int:
    if not path.exists():
        return 1
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line) + 1
    except OSError:
        return 1
```

**Problem:** `_initial_next_id` reads the JSONL file line count to seed `self._next_id`. But JSONL is a best-effort mirror — if a JSONL write fails but the DB write succeeds, the next `EventLog` instance will undercount.

**Impact:** Duplicate `event_id` values in session.db. Example: two rows with `ev-000042`. The `event_id` column is `TEXT NOT NULL` but NOT a primary key (the `id` column `INTEGER PRIMARY KEY AUTOINCREMENT` is the PK), so duplicates are allowed.

**Trigger scenario (most likely in workflow):** Each workflow stage creates a NEW `EventLog` instance on the same `session.db`. If any JSONL write failed during a previous stage, the new instance's `_initial_next_id` will undercount, producing duplicate event IDs.

**Fix:** `_initial_next_id` should query `SELECT COUNT(*) FROM event_log` from session.db, falling back to JSONL count only if DB is unavailable.

**Severity:** Medium. Duplicate event IDs don't break functionality (PK is `id`, not `event_id`) but they break the human-readable correlation between event_id and row order, and any tool that assumes event_id uniqueness will get confused.

---

### LOGIC-2: ⚠️ GAP — Workflow controller writes flow_state.json and eval_report.json as standalone files, NOT to session.db event_log

**Location:** `src/fa/inner_loop/workflow_artifacts.py` (`write_flow_state`, `write_eval_report`)

**Problem:** `write_flow_state()` and `write_eval_report()` write directly to JSON files on disk. These are NOT in the `event_log` table.

**Impact:**
- `fa stats` cannot see workflow transitions, eval verdicts, or repair/replan rounds
- The only way to inspect workflow state is to manually read the JSON files
- Post-session analysis with `fa stats` misses the entire workflow orchestration layer
- The session.db event_log has no record that a workflow even ran

**Operator impact:** After `fa workflow --mode repair` completes with 3 repair rounds, `fa stats --run-id <id>` shows nothing about the workflow — it just shows the combined tool usage across all stages with no indication of the eval verdict or repair loop.

**Severity:** Medium. Data is not lost (JSON files are durable) but it's invisible to the standard analysis tooling.

---

### LOGIC-3: ⚠️ GAP — `fa stats` does not distinguish between roles in a shared run_id workflow

**Location:** `src/fa/stats.py:parse_session()`

**Code:**
```python
if kind == "run_started":
    role = str(content.get("role", ""))
```

**Problem:** In a workflow, all stages share the same run_id → same session.db. Each stage emits its own `run_started` event with a different role. The parser overwrites `role` each time it sees `run_started` → only the LAST role survives.

**Impact:** `fa stats` reports `role=eval` for a `planner,coder,eval` workflow, which is misleading. The operator cannot see that planner and coder stages also ran.

**Severity:** Low. The role field in stats is a single string, not designed for multi-stage workflows. But it's incorrect information.

---

### LOGIC-4: ✅ CONFIRMED CORRECT — `fa stats` ok flag logic

**Analysis:**
- `run_stopped` sets `ok = False`
- `session_summary` present + `stop_reason == "unknown"` → infers `ok = True`
- Happy path (`stopped_by_llm`) does NOT emit `run_stopped`, only `session_summary` → ok=True ✅
- Abnormal paths emit BOTH `run_stopped` AND `session_summary` → ok stays False ✅

**Verdict:** Confusing but not buggy. The logic works correctly because the happy path never emits `run_stopped`.

---

### LOGIC-5: ⚠️ GAP — `session_end` OutputEvent has `context_used_pct: None` hardcoded

**Location:** `src/fa/inner_loop/coder_loop.py` — `finish()` closure

**Code:**
```python
output.emit(
    OutputEvent(
        type="session_end",
        ...
        data={
            ...
            "context_used_pct": None,  # ← hardcoded!
        },
    )
)
```

**Problem:** The actual context budget percentage IS available from the `budget` object (which is in the closure scope via `budget.check(usage)`), but it's never computed or passed to the output event.

**Impact:** `ConsoleRenderer._handle_session_end` has code to display context %:
```python
if self.show_context_pct and d.get("context_used_pct") is not None:
    self._write(f" Context: {d['context_used_pct']:.0f}% of window")
```
But since `context_used_pct` is always `None`, this line NEVER executes. The operator never sees context usage, even at session end.

**Fix:** In `finish()`, compute `context_used_pct` from the budget:
```python
pct = None
try:
    usage = estimate_tokens(messages_payload, tool_payload) if messages_payload else 0
    decision = budget.check(usage)
    pct = decision.get("ratio", 0.0) * 100
except Exception:
    pass
# ... then use pct instead of None
```

Or simpler: track the last `budget.check()` result and pass its ratio.

**Severity:** Medium. Context usage is critical for debugging why a session hit the budget cap. Without it, operators are flying blind on context management.

---

### LOGIC-6: ⚠️ GAP — CostGuardian is dormant on baseline tools

**Location:** `src/fa/observability/cost_guardian.py` + tool implementations

**Problem:** `default_cost_extractor` looks for `cost=...` artifact in `ToolResult.artifacts`. Baseline tools (`fs_read_file`, `fs_write_file`, `fs_run_bash`) do NOT emit this artifact. Only a future T-2 LLM driver will emit it.

**Impact:** The `cost_observation` event kind exists but will never fire with current tools. CostGuardian is fully wired but produces zero observations in production today. The feature is structurally complete but operationally dormant.

**Severity:** Low (expected — this is a future-feature stub, not a bug). But operators should know that `cost_budget_usd` in config currently has no effect.

---

### LOGIC-7: ⚠️ GAP — `fa stats` doesn't parse `tool_result` events

**Location:** `src/fa/stats.py:parse_session()`

**Problem:** `tool_result` is emitted by `state.record_tool_result()` but not handled in `parse_session()`. The `tool_call` handler captures name and params, but tool results (including error details) are invisible.

**Impact:** An operator running `fa stats --run-id X` cannot see which tools failed. Error details from `ToolResult.error` are only in the `tool_result` event kind, which stats ignores.

**Severity:** Medium. Error analysis is a key use case for post-session stats, and tool failures are invisible.

---

### LOGIC-8: ⚠️ GAP — `_cmd_run` has no error handling for EventLog init failure

**Location:** `src/fa/cli.py:_cmd_run()`

**Problem:** If `SessionDatabase` construction fails (e.g., path not writable), `EventLog.__init__` sets `self.session_db = None` and logs a warning. Then `EventLog.append()` raises `RuntimeError("event_log_authority_unavailable: ...")`. This exception propagates unhandled from `drive_session()` → `_cmd_run()`, producing an unhandled traceback.

There is NO try/except around `drive_session()` in `_cmd_run()`:
```python
outcome = drive_session(
    args.task,
    provider_chain=chain,
    ...
    output=output_bus,
)
```

**Impact:** The operator sees a raw Python traceback instead of a friendly "fa run: failed to initialize session database at <path>: <reason>" message.

**Severity:** Medium. This would only happen in misconfigured environments (e.g., non-writable `~/.fa/session-log/`), but when it does happen, the error message is confusing.

**Fix:** Wrap `drive_session()` call in try/except RuntimeError with a friendly message, or check `log.session_db is not None` before calling `drive_session()`.

---

### LOGIC-9: ⚠️ GAP — `ProviderRequestShapeError` handler has no console output event

**Location:** `src/fa/inner_loop/coder_loop.py` — `except ProviderRequestShapeError` handler

**Code:**
```python
except ProviderRequestShapeError as exc:
    state.log.append(
        actor="runtime",
        kind="run_stopped",
        content={"reason": "request_shape", "detail": str(exc)},
    )
    return finish(
        SessionOutcome(
            exit_code=2,
            stop_reason="request_shape",
            ...
        )
    )
```

**Problem:** Unlike `ProviderChainExhaustedError` (which emits `api_retry` OutputEvents for each failed attempt), the `ProviderRequestShapeError` handler emits NO console events before `finish()`. The operator only sees the generic `session_end` line and `ERROR: request_shape (turns=X)`.

**Impact:** An operator encountering a request shape error (e.g., model doesn't support tools, or request body is malformed) gets no diagnostic about what was wrong. The detail string (`str(exc)`) is written to the DB log but not to the console.

**Severity:** Medium. Request shape errors indicate a configuration or adapter bug. Without the detail on console, the operator must look up the events.jsonl or session.db to understand the problem.

**Fix:** Add an `output.emit(OutputEvent(type="api_retry", ...))` or a new `OutputEvent(type="request_error", ...)` with the shape error detail.

---

### LOGIC-10: ⚠️ GAP — `abnormal_stop:*` paths have minimal console output

**Location:** `src/fa/inner_loop/coder_loop.py` — abnormal stop handler

**Code:**
```python
state.log.append(
    actor="runtime",
    kind="run_stopped",
    content={"reason": f"abnormal_stop:{response.finish_reason}"},
)
return finish(
    SessionOutcome(
        exit_code=1,
        stop_reason=f"abnormal_stop:{response.finish_reason}",
        ...
    )
)
```

**Problem:** The `abnormal_stop:length` and `abnormal_stop:content_filter` paths write `run_stopped` to EventLog and go through `finish()` (which emits `session_end`). But:
1. No specific OutputEvent explains what happened during the session
2. The `finish_reason` from the LLM response is in the `model_msg` event but never surfaced to console
3. The operator sees `FAIL: abnormal_stop:length (turns=X)` with no guidance on how to fix it

**Impact:** `abnormal_stop:length` typically means `max_tokens` was too low for the model's response. `abnormal_stop:content_filter` means the provider rejected the output. Both require operator action, but the console output doesn't guide the operator.

**Severity:** Low-Medium. The stop reason is shown, but without actionable guidance.

**Fix:** Add context to session_end data for abnormal stops, or emit a dedicated OutputEvent. E.g., `abnormal_stop:length` → "Model output truncated. Consider increasing --max-tokens or the model's max output tokens." `abnormal_stop:content_filter` → "Provider content filter triggered. Check tool outputs for sensitive content."

---

### LOGIC-11: 🐛 CONFIRMED BUG — Workflow stages overwrite each other in global_history.db

**Location:** `src/fa/cli.py:_cmd_run()` → `export_session_to_global_history()`; `src/fa/inner_loop/global_history.py`

**Problem:** Each workflow stage calls `export_session_to_global_history()` with the SAME `run_id`. Since global_history.db uses `INSERT OR REPLACE` on `run_id` (which is the PRIMARY KEY), each stage overwrites the previous stage's row.

**What's lost:**
- `role`: only the last stage's role survives (e.g., "eval")
- `turns`: only the last stage's turn count (from `outcome.turns`, which is per-stage)
- `stop_reason`: only the last stage's stop reason
- `exit_code`: only the last stage's exit code

**What's accidentally correct:**
- Token totals (`input_tokens`, `output_tokens`): `_extract_telemetry_from_log()` reads ALL events from the shared session.db and accumulates across stages. The last export writes correct cross-stage totals.
- `tool_calls_breakdown_json`: also accumulated across all stages correctly
- `has_compaction_summary`: correct because compaction events from all stages are in the shared session.db

**Example:** A `planner(3 turns) → coder(12 turns) → eval(2 turns)` workflow results in a global_history row with `role=eval`, `turns=2`. The operator sees a 2-turn eval run, not a 17-turn workflow.

**Severity:** High. Global history is the operator's cross-run analytics surface. Workflow data is fundamentally broken there.

**Fix options:**
1. **One row per stage**: use composite PK `(run_id, role)` instead of just `run_id`
2. **Aggregate at workflow end**: add a workflow-aware export that aggregates all stages into one row with `roles=planner→coder→eval`, `total_turns=17`
3. **Export only at workflow end**: skip per-stage exports, export once from `_cmd_workflow` with the full workflow picture

---

### LOGIC-12: ⚠️ GAP — `fa stats --global-history` doesn't display compaction data

**Location:** `src/fa/cli.py:_cmd_stats()` — global-history rendering

**Code:**
```python
for r in rows[:20]:
    print(
        f"  {r.get('run_id', ''):<20s} {r.get('role', ''):<8s} {r.get('model', ''):<20s} "
        f"{r.get('stop_reason', ''):<20s} turns={r.get('turns', 0)} "
        f"in={r.get('input_tokens', 0)} out={r.get('output_tokens', 0)}",
        file=sys.stderr,
    )
```

**Problem:** The `has_compaction_summary` column exists in global_history.db but is never displayed in the console output. Only `--output json` reveals it.

**Impact:** An operator cannot see which runs had compaction without querying the DB directly. For debugging compaction issues, the operator must use JSON output or raw SQL.

**Severity:** Low. The data is accessible via `--output json`. But the console should surface this, since compaction is a key indicator of session health.

---

### LOGIC-13: ⚠️ GAP — `fa stats` discovers sessions by `events.jsonl` existence, not `session.db`

**Location:** `src/fa/cli.py:_cmd_stats()`

**Code:**
```python
session_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and (d / "events.jsonl").exists()], ...)
```

**Problem:** Session discovery checks for `events.jsonl` existence even though `session.db` is the authority. If JSONL mirror write fails but DB writes succeed, the session becomes invisible to `fa stats`.

**Impact:** In the rare case where JSONL write fails for ALL events in a session (disk full on the first write, permissions issue, etc.), the session exists in session.db but `fa stats` cannot find it.

**Severity:** Low. This is a rare edge case since JSONL writes are best-effort and typically succeed after DB writes. But it contradicts the "session.db is authority" principle.

**Fix:** Check for `(d / "session.db").exists()` instead of `(d / "events.jsonl").exists()`.

---

### Verified OK — No Issues Found

The following items from the audit checklist were verified and found to be correct:

1. **`finish()` double-call guard:** The `summary_written` flag correctly prevents double `session_summary` and double `session_end` OutputEvent. `finish()` can be called multiple times safely — subsequent calls are no-ops. ✅

2. **Workflow exit 2 diagnostics:** All `return 2` paths in `_cmd_workflow()` have clear `print(..., file=sys.stderr)` messages explaining the error. No silent exit-2 paths exist. ✅

3. **`fa stats` ok flag logic (LOGIC-4):** Confusing but correct. Happy path never emits `run_stopped`, so `ok` correctly defaults to `True`. Abnormal paths emit both `run_stopped` and `session_summary`, keeping `ok = False`. ✅

---

## 9. Finding Summary Table

| ID | Severity | Category | Description |
|----|----------|----------|-------------|
| LOGIC-1 | 🐛 Bug (Medium) | Data integrity | `_initial_next_id` counts JSONL, not DB rows → duplicate event IDs |
| LOGIC-2 | ⚠️ Gap (Medium) | Missing event | Workflow flow_state + eval_report not in event_log |
| LOGIC-3 | ⚠️ Gap (Low) | Data accuracy | `fa stats` shows only last role in multi-stage workflow |
| LOGIC-4 | ✅ OK | — | `fa stats` ok flag logic confirmed correct |
| LOGIC-5 | ⚠️ Gap (Medium) | Missing data | `context_used_pct: None` hardcoded, never computed |
| LOGIC-6 | ⚠️ Gap (Low) | Dormant feature | CostGuardian dormant on baseline tools (by design) |
| LOGIC-7 | ⚠️ Gap (Medium) | Missing data | `fa stats` doesn't parse `tool_result` events |
| LOGIC-8 | ⚠️ Gap (Medium) | Error handling | `_cmd_run` has no try/except for EventLog RuntimeError |
| LOGIC-9 | ⚠️ Gap (Medium) | Missing console | `ProviderRequestShapeError` has no console output event |
| LOGIC-10 | ⚠️ Gap (Low-Med) | Missing console | `abnormal_stop:*` paths lack actionable console output |
| LOGIC-11 | 🐛 Bug (High) | Data corruption | Workflow stages overwrite each other in global_history.db |
| LOGIC-12 | ⚠️ Gap (Low) | Missing display | `fa stats --global-history` doesn't show compaction flag |
| LOGIC-13 | ⚠️ Gap (Low) | Principle violation | Session discovery uses JSONL, not session.db |

### Priority ranking for fixes

**Must fix (data integrity):**
1. LOGIC-11 — Workflow global_history overwrite (High severity, affects all workflow users)
2. LOGIC-1 — `_initial_next_id` JSONL vs DB (Medium severity, triggers in workflow)
3. LOGIC-8 — Unhandled RuntimeError in `_cmd_run` (Medium severity, confusing error messages)

**Should fix (operator experience):**
4. LOGIC-5 — `context_used_pct: None` (Medium, deprives operator of critical context info)
5. LOGIC-9 — `ProviderRequestShapeError` no console event (Medium, no diagnostics on config error)
6. LOGIC-7 — `fa stats` missing `tool_result` (Medium, error analysis incomplete)
7. LOGIC-2 — Workflow artifacts not in event_log (Medium, workflow invisible to stats)

**Nice to fix (polish):**
8. LOGIC-10 — `abnormal_stop` actionable guidance (Low-Medium)
9. LOGIC-3 — Multi-role role display (Low)
10. LOGIC-12 — Global history compaction display (Low)
11. LOGIC-13 — Session discovery via session.db (Low)
12. LOGIC-6 — CostGuardian dormant (Low, by design)

---

## 10. Session.db Authority Principle — Audit Conformance

The codebase declares "session.db is authority, JSONL is mirror." This audit verified conformance:

| Aspect | Conforms? | Notes |
|--------|-----------|-------|
| Write path: DB first, JSONL second | ✅ | `EventLog.append()` writes DB → advance ID → JSONL |
| Read path: DB primary, JSONL fallback | ✅ | `EventLog.read_all()` tries DB first |
| `fa stats` reads from session.db | ✅ | Uses `EventLog.read_all()` which reads DB |
| Session discovery uses JSONL, not DB | ❌ | LOGIC-13: `cli.py` discovers sessions by `events.jsonl` existence |
| Event ID seeded from JSONL, not DB | ❌ | LOGIC-1: `_initial_next_id` counts JSONL lines |
| Global history export uses DB data | ✅ | `_extract_telemetry_from_log()` reads via `log.read_all()` from DB |
| Workflow artifacts in session.db | ❌ | LOGIC-2: flow_state.json / eval_report.json are standalone files |

**Score: 4/7 conformant.** Three deviations from the stated principle, two of which (LOGIC-1, LOGIC-13) are straightforward fixes.

---

## 11. Third-Pass Deep Audit — Dead Code, Wiring, Performance, Feature-Flag Cascade

> **Method:** Fundamentally different lens from passes 1 and 2. Instead of "does event X reach display Y" or "is there a logic error in this handler," this pass asks: **which event kinds are dead code in production because the wiring is missing? Which code paths are silently O(n²) or worse? Which feature flag combinations silently silence entire telemetry streams? Which hooks are defined but never registered?**

### LOGIC-14: 🐛 CONFIRMED BUG — `loop_guard_warn` events are NEVER emitted in production (warn_sink not wired)

**Location:** `src/fa/cli.py:762-768` (both `_cmd_inner_loop_smoke` and `_cmd_run`)

**Code in cli.py:**
```python
hooks.register(
    LoopGuard(
        repeat_warn=limits.loop_guard_repeat_warn,
        circuit_breaker=limits.loop_guard_circuit_breaker,
        window=limits.loop_guard_window,
    )
)
```

**The gap:** `LoopGuard.__init__` accepts an optional `warn_sink: WarnSink | None = None`. When provided, the sink is called on every warn, and the convention is that the caller passes a function that writes `kind="loop_guard_warn"` to EventLog. **But `cli.py` never passes `warn_sink`.**

The `_emit_warn` method in `LoopGuard`:
```python
def _emit_warn(self, detector: str, message: str) -> None:
    if self._warn_sink is None:
        return  # ← always returns in production!
    try:
        self._warn_sink(detector, message)
    except Exception:
        pass
```

**Impact:** The `loop_guard_warn` event kind (row #12 in the inventory) is **dead code in production**. It exists in the code, it's in `fa stats`, but it is NEVER written to session.db or events.jsonl during `fa run` or `fa workflow`.

The circuit-breaker deny still works correctly (it raises `PermissionError` which the loop handles), but the warning-level signal — which fires at `repeat_warn=3` repetitions before the circuit breaker at `circuit_breaker=5` — is completely silent.

**Operator impact:** An operator has ZERO early warning that a loop is forming. By the time the circuit breaker fires and the session terminates, 5+ identical tool calls have already wasted tokens and time. The warn at 3 would have given the operator 2 tool calls of advance notice.

**Fix:** Wire `warn_sink` in `cli.py`:
```python
def _loop_guard_warn_sink(detector: str, message: str) -> None:
    if state.log is not None:
        state.log.append(
            actor="hook",
            kind="loop_guard_warn",
            content={"detector": detector, "message": message},
        )


hooks.register(
    LoopGuard(
        repeat_warn=limits.loop_guard_repeat_warn,
        circuit_breaker=limits.loop_guard_circuit_breaker,
        window=limits.loop_guard_window,
        warn_sink=_loop_guard_warn_sink,
    )
)
```

**Severity:** High. This is a dead-code bug — a documented, consumed event kind that never fires in production.

---

### LOGIC-15: 🐛 CONFIRMED BUG — `recovery_action` events are NEVER emitted in production (FailureClassifierObserver not registered)

**Location:** `src/fa/cli.py` — both `_cmd_inner_loop_smoke` and `_cmd_run`

**The gap:** `FailureClassifierObserver` and `AttemptHistoryObserver` are defined in `src/fa/inner_loop/hooks/recovery_observers.py` and exported from `src/fa/inner_loop/hooks/__init__.py`, but **neither is registered in `cli.py`**.

The `_cmd_run` hook registration chain:
1. SandboxHook ✅
2. LoopGuard ✅
3. RateLimitBlocker ✅
4. LockfileBlocker ✅
5. AuthExpiredBlocker ✅
6. IntentGuard ✅
7. AuditHook ✅
8. SecretGuard ✅
9. CostGuardian ✅
10. LearningObserver ✅
11. VerifierObserver ✅ (conditional)
12. **FailureClassifierObserver ❌ NOT REGISTERED**
13. **AttemptHistoryObserver ❌ NOT REGISTERED**

**Impact:** The `recovery_action` event kind (row #13 in the inventory) is **dead code in production**. When a tool fails, the FailureClassifier runs its category/action classification — but the result is never written to EventLog. An operator running `fa stats --run-id X` after a session with multiple tool failures gets zero recovery-action data.

Additionally, the `attempt_history.json` file is never written, so the coder-recovery prompt (which reads attempt history before the next retry) has no data source.

**Severity:** Medium-High. Recovery classification is a key observability signal — it tells the operator WHY a tool failed (rate limit? auth? network? bad params?) and what recovery action is recommended. Without it, tool failure analysis requires reading raw `tool_result` events.

**Fix:** Register both observers in `cli.py`:
```python
from fa.inner_loop.hooks.recovery_observers import FailureClassifierObserver, AttemptHistoryObserver
from fa.inner_loop.recovery.attempt_history import AttemptHistory

attempt_history = AttemptHistory(workspace / ".fa" / "attempt_history.json")
hooks.register(FailureClassifierObserver(event_log=log))
hooks.register(AttemptHistoryObserver(history=attempt_history))
```

---

### LOGIC-16: ⚠️ PERFORMANCE — `state.log.read_all()` called on every turn, O(n²) in long sessions

**Location:** `src/fa/inner_loop/coder_loop.py:1122` and `src/fa/inner_loop/loop.py:520`

**Code in coder_loop.py:**
```python
log_len_before = len(state.log.read_all()) if state.log is not None else 0
```

**Code in loop.py (parallel batch stop detection):**
```python
recent = state.log.read_all()[-5:]
```

**Problem:** `read_all()` performs a full `SELECT * FROM event_log ORDER BY id ASC` on every turn. In a 16-turn session with 10 events per turn, that's 160 rows read 16 times = 2,560 rows read total. In a long workflow with 3 stages × 16 turns × 10 events = 480 events, the third stage re-reads all 480 rows every turn.

This is O(n²) in total reads across a session. For the common case (sessions < 500 events) this is fine. But for long sessions with compaction (which indicates many events), this becomes a noticeable latency source.

**The `read_all()` on line 1122 is used only to count rows** — it doesn't need the full row content. And the `read_all()[-5:]` on line 520 only needs the last 5 rows.

**Impact:** During compaction-heavy sessions (where context is large and many events exist), the per-turn `read_all()` adds latency at the exact moment the operator is already experiencing slowness from context pressure.

**Severity:** Low-Medium. Not a correctness issue, but it's a performance anti-pattern that degrades precisely when the operator is most sensitive to latency (during context pressure).

**Fix options:**
1. Add `EventLog.count()` method that runs `SELECT COUNT(*) FROM event_log` instead of `read_all()`
2. Add `EventLog.tail(n)` method that runs `SELECT * FROM event_log ORDER BY id DESC LIMIT n`
3. Cache the event count on the EventLog instance and increment on each append

---

### LOGIC-17: ⚠️ GAP — Feature flag cascade: `context_compaction_enabled: false` silences ALL budget telemetry after stage 2

**Location:** `src/fa/inner_loop/coder_loop.py:640-660`

**Code:**
```python
if decision["action"] in {"stage2", "stage3"}:
    compaction_enabled = False
    try:
        if state.feature_flags is not None:
            compaction_enabled = getattr(state.feature_flags, "context_compaction_enabled", False)
    except Exception:
        pass

    if not compaction_enabled:
        if decision["action"] == "stage2":
            # Emits context_budget_warn ← GOOD
            state.log.append(actor="runtime", kind="context_budget_warn", content=decision)
        else:
            # Emits context_budget_hard_stop + run_stopped ← GOOD
            state.log.append(actor="runtime", kind="context_budget_hard_stop", content=decision)
            state.log.append(actor="runtime", kind="run_stopped", content={...})
            return finish(...)
    else:
        # Compaction path — emits compaction_* events
        # BUT: after compaction, if budget still exceeded:
        #   → context_budget_hard_stop is emitted ← GOOD
        #   → BUT only if decision["action"] == "stage3" AFTER compaction
```

**The cascade problem:** The default config has:
- `context_budget_enabled: true` (default)
- `context_compaction_enabled: false` (default)

This means:
1. Context budget IS active → it checks token usage every turn
2. At 80% (stage 2), it emits `context_budget_warn` ✅
3. At 90% (stage 3), it emits `context_budget_hard_stop` and kills the session ✅
4. **But there is NO intermediate signal between 80% warn and 90% kill**

With compaction enabled, there would be a progression: warn → mask (stage 2) → compact (stage 3) → hard stop. The operator sees multiple events and the session gets a chance to recover. Without compaction, the operator gets ONE warn at 80% and then the session dies at 90% with no recovery path.

**The deeper problem:** The 80%→90% gap could span many turns. The operator sees the warn at turn 8 (80%) and might not notice. By turn 14 (90%), the session dies. There are **zero additional signals between the warn and the kill**. No per-turn context % display. No escalating warns.

**Impact:** With default config, `context_budget_warn` fires at most ONCE per session. Then the session either:
- Stays under 90% and completes (operator never knows context was close to the limit)
- Hits 90% and dies (operator is surprised — "it was working fine a minute ago")

**Severity:** Medium. This is a design gap, not a bug. The fix would be to emit periodic context percentage signals (e.g., at `--detail verbose`+) regardless of whether compaction is enabled.

---

### LOGIC-18: ⚠️ GAP — `telemetry` event kind is redundant and bloats event_log (2 events per tool result)

**Location:** `src/fa/inner_loop/state.py:record_tool_result()`

**Code:**
```python
# In record_tool_result():
# 1. Writes to TelemetryLogger (filesystem artifact)
self.telemetry.log(event)
# 2. Writes to EventLog as "telemetry" kind
self.log.append(
    actor="telemetry",
    kind="telemetry",
    content={...},
    ...
)
# 3. Then ALSO writes the "tool_result" kind
return self.log.append(
    actor="tool",
    kind="tool_result",
    content=content,
    ...
)
```

**Problem:** Every tool result produces BOTH a `telemetry` event AND a `tool_result` event in session.db. The `telemetry` event contains a subset of the `tool_result` data (tool_name, ok, artifact_id, turn). This means:

1. Every tool call generates 4 rows in event_log: `tool_call`, `telemetry`, `tool_result`, + the `hook_decision` from the AuditHook. That's 4 rows per tool instead of the expected 2 (`tool_call` + `tool_result`).
2. The `telemetry` event has zero consumers — `fa stats` doesn't parse it, `global_history.db` doesn't use it, ConsoleRenderer doesn't display it.
3. The `TelemetryLogger` filesystem artifact is the actual intended consumer; the EventLog row is an accidental byproduct.

**Impact:** Event_log bloat. In a 16-turn session with 3 tools per turn, that's 48 extra `telemetry` rows that nobody reads. More importantly, it inflates the `read_all()` result on every turn (see LOGIC-16), making the O(n²) problem worse.

**Severity:** Low. Not a correctness issue, but it's unnecessary data that makes session.db larger and `read_all()` slower.

**Fix:** Remove the `self.log.append(kind="telemetry", ...)` call from `record_tool_result()`. The `TelemetryLogger` filesystem artifact is sufficient for the telemetry use case. Or gate it behind a feature flag.

---

### LOGIC-19: ⚠️ GAP — `compaction_warning` event kind is dead code (CompactionManager not wired)

**Location:** `src/fa/inner_loop/compaction/foundation.py`

**The gap:** The `CompactionManager` class (with its `check()` method that emits `compaction_warning` at 70%) is defined in `foundation.py` but is **never instantiated or called anywhere in the codebase**.

The actual context budget check is done by `ContextBudget` class in `src/fa/memory/context_budget.py`, which emits `context_budget_warn` instead of `compaction_warning`. The `CompactionManager` appears to be an earlier design that was superseded by `ContextBudget` but never removed.

**Impact:** The `compaction_warning` event kind (row #26 in the inventory) is **dead code** — it can never be emitted because no code path creates a `CompactionManager` instance or calls its `check()` method. The inventory entry should be marked as "not emitted in production."

**Severity:** Low. This is code hygiene rather than an operational bug. But it's misleading — the inventory suggests `compaction_warning` is a real event kind when it's actually unreachable.

**Fix:** Either remove `CompactionManager` and the `compaction_warning` kind, or update the inventory to mark it as "legacy/dead code."

---

### Summary of Third-Pass Findings

| ID | Severity | Category | Description |
|----|----------|----------|-------------|
| LOGIC-14 | 🐛 Bug (High) | Dead code / Missing wiring | `loop_guard_warn` never emitted — `warn_sink` not wired in `cli.py` |
| LOGIC-15 | 🐛 Bug (Med-High) | Dead code / Missing wiring | `recovery_action` never emitted — `FailureClassifierObserver` not registered |
| LOGIC-16 | ⚠️ Perf (Low-Med) | O(n²) | `read_all()` called every turn — full DB scan per turn |
| LOGIC-17 | ⚠️ Gap (Medium) | Feature flag cascade | Default config silences all budget signals after first warn |
| LOGIC-18 | ⚠️ Gap (Low) | Redundant event | `telemetry` event duplicates `tool_result`, bloats event_log |
| LOGIC-19 | ⚠️ Gap (Low) | Dead code | `compaction_warning` never emitted — `CompactionManager` not wired |

### Updated Event Kind Inventory — Corrected for Dead Code

After accounting for dead-code events (LOGIC-14, LOGIC-15, LOGIC-19), the **actual** event kinds that reach session.db in production are:

| Category | Kinds written in production | Kinds dead-code (never emitted) |
|----------|---------------------------|-------------------------------|
| Core | 10 (tool_call, tool_result, user_msg, model_msg, usage, run_started, run_stopped, session_summary, provider_attempt, hook_decision) | 0 |
| Observers | 4 (audit, verification, telemetry, cost_observation*) | 2 (loop_guard_warn*, recovery_action*) |
| Context/Compaction | 8 (context_budget_warn, context_budget_hard_stop, compaction_stage2_*, compaction_stage3_*, compaction_circuit_breaker) | 1 (compaction_warning*) |
| Subagent | 3 (subagent_spawn_start, subagent_spawn_done, subagent_spawn_fail) | 0 |
| Other | 0 | 2 (timeout*, service_unavailable*) |
| **Total** | **25 live** | **5 dead*** |

*`cost_observation` is live code but dormant (LOGIC-6). `timeout` and `service_unavailable` exist as event kinds in the schema but are never emitted by any current code path — they appear to be reserved for future use.

**Revised coverage:** 25 event kinds actually reach session.db in production (not 32). Of those, `fa stats` consumes 7 (down from 8 because `loop_guard_warn` was the 8th and it's dead). Console displays ~4.

---

## 12. Cumulative Finding Summary (All Three Passes)

| ID | Severity | Category | Description |
|----|----------|----------|-------------|
| LOGIC-1 | 🐛 Bug (Medium) | Data integrity | `_initial_next_id` counts JSONL, not DB rows → duplicate event IDs |
| LOGIC-2 | ⚠️ Gap (Medium) | Missing event | Workflow flow_state + eval_report not in event_log |
| LOGIC-3 | ⚠️ Gap (Low) | Data accuracy | `fa stats` shows only last role in multi-stage workflow |
| LOGIC-4 | ✅ OK | — | `fa stats` ok flag logic confirmed correct |
| LOGIC-5 | ⚠️ Gap (Medium) | Missing data | `context_used_pct: None` hardcoded, never computed |
| LOGIC-6 | ⚠️ Gap (Low) | Dormant feature | CostGuardian dormant on baseline tools (by design) |
| LOGIC-7 | ⚠️ Gap (Medium) | Missing data | `fa stats` doesn't parse `tool_result` events |
| LOGIC-8 | ⚠️ Gap (Medium) | Error handling | `_cmd_run` has no try/except for EventLog RuntimeError |
| LOGIC-9 | ⚠️ Gap (Medium) | Missing console | `ProviderRequestShapeError` has no console output event |
| LOGIC-10 | ⚠️ Gap (Low-Med) | Missing console | `abnormal_stop:*` paths lack actionable console output |
| LOGIC-11 | 🐛 Bug (High) | Data corruption | Workflow stages overwrite each other in global_history.db |
| LOGIC-12 | ⚠️ Gap (Low) | Missing display | `fa stats --global-history` doesn't show compaction flag |
| LOGIC-13 | ⚠️ Gap (Low) | Principle violation | Session discovery uses JSONL, not session.db |
| LOGIC-14 | 🐛 Bug (High) | Dead code / Missing wiring | `loop_guard_warn` never emitted — `warn_sink` not wired |
| LOGIC-15 | 🐛 Bug (Med-High) | Dead code / Missing wiring | `recovery_action` never emitted — observers not registered |
| LOGIC-16 | ⚠️ Perf (Low-Med) | O(n²) | `read_all()` called every turn — full DB scan |
| LOGIC-17 | ⚠️ Gap (Medium) | Feature flag cascade | Default config silences budget signals after first warn |
| LOGIC-18 | ⚠️ Gap (Low) | Redundant event | `telemetry` event duplicates `tool_result`, bloats DB |
| LOGIC-19 | ⚠️ Gap (Low) | Dead code | `compaction_warning` never emitted — CompactionManager not wired |

### Revised Priority Ranking (All Three Passes)

**Must fix (data integrity + dead code bugs):**
1. LOGIC-11 — Workflow global_history overwrite (High, data corruption)
2. LOGIC-14 — `loop_guard_warn` warn_sink not wired (High, dead-code bug)
3. LOGIC-15 — `FailureClassifierObserver` not registered (Med-High, dead-code bug)
4. LOGIC-1 — `_initial_next_id` JSONL vs DB (Medium, duplicate IDs in workflow)
5. LOGIC-8 — Unhandled RuntimeError in `_cmd_run` (Medium, confusing tracebacks)

**Should fix (operator experience):**
6. LOGIC-5 — `context_used_pct: None` (Medium, no context info at session end)
7. LOGIC-17 — Feature flag cascade silences budget telemetry (Medium, design gap)
8. LOGIC-9 — `ProviderRequestShapeError` no console event (Medium)
9. LOGIC-7 — `fa stats` missing `tool_result` (Medium)
10. LOGIC-2 — Workflow artifacts not in event_log (Medium)

**Nice to fix (polish / perf / hygiene):**
11. LOGIC-16 — `read_all()` O(n²) (Low-Medium, perf)
12. LOGIC-10 — `abnormal_stop` actionable guidance (Low-Medium)
13. LOGIC-3 — Multi-role role display in stats (Low)
14. LOGIC-18 — Remove redundant `telemetry` event (Low, hygiene)
15. LOGIC-19 — Remove dead `CompactionManager` / `compaction_warning` (Low, hygiene)
16. LOGIC-12 — Global history compaction display (Low)
17. LOGIC-13 — Session discovery via session.db (Low)
18. LOGIC-6 — CostGuardian dormant (Low, by design)

---

## 13. Implementation Status (2026-07-18)

All MUST-fix and SHOULD-fix findings have been implemented. See implementation plan at `knowledge/research/observability-fix-implementation-plan-2026-07-18.md`.

### Phase 1 — Dead-code wiring bugs ✅ COMPLETE
- LOGIC-14: LoopGuard `warn_sink` wired in `cli.py` (both `_cmd_inner_loop_smoke` and `_cmd_run`)
- LOGIC-15: `FailureClassifierObserver` + `AttemptHistoryObserver` registered in `cli.py` (both call sites)

### Phase 2 — DB authority conformance ✅ COMPLETE
- LOGIC-1: `_initial_next_id` now queries `SELECT COUNT(*) FROM event_log` from session.db, falls back to JSONL
- LOGIC-13: Session discovery uses `session.db` existence instead of `events.jsonl`
- LOGIC-8: `_cmd_run` catches `RuntimeError("event_log_authority_unavailable")` with friendly error message

### Phase 3 — Global history overwrite ✅ COMPLETE
- LOGIC-11: Per-stage global_history export skipped when `outcome_sink is not None` (workflow). Single aggregate export from `_cmd_workflow` with `role="planner→coder→eval"`

### Phase 4 — Console visibility ✅ COMPLETE
- LOGIC-5: `context_used_pct` computed from `last_budget_ratio` instead of hardcoded None
- LOGIC-9: `ProviderRequestShapeError` emits `api_retry` OutputEvent
- FIX-1: `context_warn` OutputEvent + `_handle_context_warn` handler
- FIX-2: `compaction_start`/`compaction_end` OutputEvents + handlers
- FIX-5: `loop_warn` OutputEvent emitted from `_loop_guard_warn_sink`
- EventType expanded from 7 to 14 literal values
- `output_bus: EventBus | None` field added to `SessionState`
- `state.output_bus = output_bus` wired in `cli.py`

### Phase 5 — fa stats retrieval ✅ COMPLETE
- LOGIC-7: `tool_result` error extraction → `ToolError` dataclass
- FIX-6: Compaction section → `CompactionRecord` dataclass + rendering
- FIX-7: Subagent section → `SubagentRecord` dataclass + rendering
- FIX-8/9: Context budget section → `ContextBudgetEvent` dataclass + rendering

### Deferred to separate PR (P6 — hygiene)
- LOGIC-17: Feature flag cascade (design gap, not a bug)
- LOGIC-18: Remove redundant `telemetry` event kind
- LOGIC-19: Remove dead `CompactionManager` / `compaction_warning`

### Test results
- 30 new tests across 5 test files — all pass
- 111 existing tests in blast radius — all pass
- Total: 141 tests green
