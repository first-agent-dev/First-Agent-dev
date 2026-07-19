# Observability Fix Implementation Plan

> **Created:** 2026-07-18
> **Authority:** Findings from `observability-audit-pr53-2026-07-18.md` (3 passes, 19 findings)
> **Methodology:** `skills/tests-writing/SKILL.md` — C1 composition-root, kill-check, ranked oracles, explicit matrix, type-honest fixtures
> **Scope:** Code fixes + tests for all MUST-fix and SHOULD-fix findings. NICE-to-fix deferred with rationale.
> **Principle:** session.db = authority, JSONL = mirror. Every fix must preserve or improve this conformance.

---

## 0. Guiding Principles (from tests-writing skill)

1. **C1 composition-root tests** — `drive_session` is the root for loop claims; `_cmd_run` / `_cmd_workflow` for CLI claims.
2. **Kill-check** — removing the production call site must fail the test.
3. **Ranked oracles** — event `kind`+fields > `SessionOutcome` > trajectory > `call_count` > FS > free-text.
4. **Explicit matrix** — name the flag matrix in every test docstring (A/B/C).
5. **Type-honest fixtures** — `tool_calls=()`, `_require_log(state)`, real `HookRegistry()`.
6. **Mock boundary** — mock `ProviderChain.request`; keep `drive_session` and real hook/budget wiring.
7. **Sequential phases** — each phase is independently shippable. Tests green → merge → next phase.

---

## 1. Phase Summary

| Phase | Focus | Findings | Files changed | Est. tests |
|-------|-------|----------|---------------|------------|
| **P1** | Dead-code wiring bugs | LOGIC-14, LOGIC-15 | `cli.py` | 4 |
| **P2** | DB authority + data integrity | LOGIC-1, LOGIC-13, LOGIC-8 | `state.py`, `cli.py` | 6 |
| **P3** | Global history overwrite | LOGIC-11 | `global_history.py`, `cli.py` | 4 |
| **P4** | Console visibility (EventType expansion) | LOGIC-5, LOGIC-9, FIX-1..5 | `output.py`, `coder_loop.py`, `cli.py` | 10 |
| **P5** | `fa stats` retrieval gaps | LOGIC-7, FIX-6..9 | `stats.py` | 8 |
| **P6** | Design gaps (telemetry pruning, CompactionManager cleanup) | LOGIC-17, LOGIC-18, LOGIC-19 | `state.py`, `coder_loop.py`, `foundation.py` | 3 |

**Total: ~35 new/modified tests across 6 phases.**

Phases P1–P3 are MUST-fix (data integrity + dead-code). P4–P5 are SHOULD-fix (operator experience). P6 is hygiene.

---

## Phase 1: Wire Dead-Code Hooks (LOGIC-14, LOGIC-15)

### 1.1 LOGIC-14 — LoopGuard `warn_sink` not wired

**Problem:** `LoopGuard.__init__` accepts `warn_sink: WarnSink | None`, but `cli.py` never passes it. The `_emit_warn` method short-circuits when `_warn_sink is None`, so `loop_guard_warn` events are NEVER written to session.db in production.

**Fix location:** `src/fa/cli.py` — both `_cmd_inner_loop_smoke` (line ~763) and `_cmd_run` (line ~1746).

**Fix:**
```python
# Before (both call sites):
hooks.register(
    LoopGuard(
        repeat_warn=limits.loop_guard_repeat_warn,
        circuit_breaker=limits.loop_guard_circuit_breaker,
        window=limits.loop_guard_window,
    )
)

# After:
def _loop_guard_warn_sink(detector: str, message: str) -> None:
    """Emit loop_guard_warn event to EventLog."""
    if log is not None:
        try:
            log.append(
                actor="hook",
                kind="loop_guard_warn",
                content={"detector": detector, "message": message},
            )
        except Exception:  # noqa: BLE001 — observer must never block
            pass

hooks.register(
    LoopGuard(
        repeat_warn=limits.loop_guard_repeat_warn,
        circuit_breaker=limits.loop_guard_circuit_breaker,
        window=limits.loop_guard_window,
        warn_sink=_loop_guard_warn_sink,
    )
)
```

**Important:** The `log` variable must be in scope. In `_cmd_run`, `log` is created at line ~1721 BEFORE `hooks.register`. In `_cmd_inner_loop_smoke`, `log` is created at line ~770. Both satisfy the ordering requirement.

**Smoke test adaptation:** `_cmd_inner_loop_smoke` uses `log = EventLog(log_path)` (line 770). The same pattern applies.

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_loop_guard_warn_event_emitted` | `drive_session` | A (budget on, compaction off) | event `kind="loop_guard_warn"` in session.db | Removing `warn_sink=_loop_guard_warn_sink` from cli.py makes this test fail — no `loop_guard_warn` event appears |
| `test_loop_guard_circuit_breaker_still_works_without_sink` | `drive_session` | A | `SessionOutcome.stop_reason` contains "LoopGuard" | Removing circuit-breaker logic itself breaks it |

**LIVE-PATH PROOF:**
```
root: drive_session
test: tests/test_observability_fix_p1.py::test_loop_guard_warn_event_emitted
matrix: A-gates-only
oracle: event:loop_guard_warn
kill-check: removing warn_sink parameter from LoopGuard construction in cli.py makes the test fail
efficiency: N/A
pyramid: A
```

### 1.2 LOGIC-15 — FailureClassifierObserver + AttemptHistoryObserver not registered

**Problem:** Both observers are defined in `src/fa/inner_loop/hooks/recovery_observers.py`, exported from `__init__.py`, but never registered in `cli.py`'s hook chain. `recovery_action` events are NEVER written to session.db.

**Fix location:** `src/fa/cli.py` — both `_cmd_inner_loop_smoke` and `_cmd_run`, AFTER the CostGuardian registration.

**Fix:**
```python
from fa.inner_loop.hooks.recovery_observers import FailureClassifierObserver, AttemptHistoryObserver
from fa.inner_loop.recovery.attempt_history import AttemptHistory

# Register after CostGuardian:
attempt_history = AttemptHistory(workspace / ".fa" / "attempt_history.json")
hooks.register(FailureClassifierObserver(event_log=log))
hooks.register(AttemptHistoryObserver(history=attempt_history))
```

**Dependency check:** `AttemptHistory.__init__` takes a `path: Path` — uses `workspace / ".fa" / "attempt_history.json"`. `FailureClassifierObserver.__init__` takes `event_log: EventLog | None` — pass `log`. Both are in the import chain already (`fa.inner_loop.hooks` exports them).

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_recovery_action_event_on_tool_failure` | `drive_session` | C-defaults | event `kind="recovery_action"` with `category`, `action`, `target` fields | Removing `FailureClassifierObserver` registration makes test fail |
| `test_attempt_history_file_written_on_tool_failure` | `drive_session` | C-defaults | `attempt_history.json` exists and contains the failed tool call | Removing `AttemptHistoryObserver` registration makes test fail |

**LIVE-PATH PROOF:**
```
root: drive_session
test: tests/test_observability_fix_p1.py::test_recovery_action_event_on_tool_failure
matrix: C-defaults
oracle: event:recovery_action + FS:attempt_history.json
kill-check: removing hooks.register(FailureClassifierObserver(...)) makes the test fail
efficiency: N/A
pyramid: A
```

---

## Phase 2: DB Authority Conformance (LOGIC-1, LOGIC-13, LOGIC-8)

### 2.1 LOGIC-1 — `_initial_next_id` counts JSONL lines, not DB rows

**Problem:** `EventLog._initial_next_id` reads the JSONL file to seed `_next_id`. If JSONL writes failed but DB writes succeeded (workflow creates new EventLog per stage on same session.db), the new instance undercounts → duplicate `event_id` values.

**Fix location:** `src/fa/inner_loop/state.py:116-120`

**Fix:**
```python
@staticmethod
def _initial_next_id(path: Path) -> int:
    """Seed _next_id from the authoritative DB, falling back to JSONL."""
    # Try DB first — it's the authority per dual-write discipline.
    db_path = path.parent / "session.db"
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            cur = conn.execute("SELECT COUNT(*) FROM event_log")
            count = int(cur.fetchone()[0])
            return count + 1
        finally:
            conn.close()
    except Exception:
        pass
    # Fallback to JSONL mirror for brand-new sessions without a DB yet.
    if not path.exists():
        return 1
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line) + 1
    except OSError:
        return 1
```

**Import needed:** Add `import sqlite3` at top of `state.py` (not currently imported).

**Edge cases:**
- Brand-new session (no session.db yet) → `sqlite3.connect` may fail or return 0 rows → falls back to JSONL check → returns 1 ✅
- Corrupted DB → falls back to JSONL → may undercount but this is best-effort ✅
- DB exists but `event_log` table doesn't → `sqlite3.OperationalError` → caught → fallback ✅

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_initial_next_id_reads_db_not_jsonl` | C0 unit on `EventLog._initial_next_id` | N/A | Returns count+1 from DB when DB has rows | Reverting to JSONL-only logic returns wrong count |
| `test_initial_next_id_fallback_no_db` | C0 unit | N/A | Returns 1 for brand-new path | N/A |
| `test_no_duplicate_event_ids_in_workflow` | C1 `drive_session` via simulated workflow | A | All `event_id` values unique in session.db | Reverting fix produces duplicate IDs |
| `test_event_ids_sequential_after_jsonl_failure` | C1 | A | event_ids monotonically increase even after JSONL write failure | Reverting fix produces gap/duplicate |

**LIVE-PATH PROOF:**
```
root: drive_session (via two-stage simulated workflow reusing same session.db)
test: tests/test_observability_fix_p2.py::test_no_duplicate_event_ids_in_workflow
matrix: A-gates-only
oracle: event_id uniqueness in session.db
kill-check: reverting _initial_next_id to JSONL-only makes duplicate event_ids appear
efficiency: N/A
pyramid: A
```

### 2.2 LOGIC-13 — Session discovery uses JSONL, not session.db

**Problem:** `_cmd_stats` discovers sessions by `(d / "events.jsonl").exists()`. If JSONL write fails but DB write succeeds, the session becomes invisible.

**Fix location:** `src/fa/cli.py:_cmd_stats()` — session discovery loop.

**Fix:**
```python
# Before:
session_dirs = sorted(
    [d for d in runs_dir.iterdir() if d.is_dir() and (d / "events.jsonl").exists()],
    ...
)

# After:
session_dirs = sorted(
    [d for d in runs_dir.iterdir() if d.is_dir() and (d / "session.db").exists()],
    ...
)
```

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_stats_discovers_session_by_db_not_jsonl` | C2 CLI `fa stats` | C | Session with session.db but no events.jsonl is found | Reverting to JSONL check makes session invisible |

### 2.3 LOGIC-8 — `_cmd_run` has no try/except for EventLog RuntimeError

**Problem:** If `SessionDatabase` construction fails, `EventLog.append()` raises `RuntimeError("event_log_authority_unavailable")`. This propagates unhandled from `drive_session()`, producing a raw Python traceback.

**Fix location:** `src/fa/cli.py:_cmd_run()` — around the `drive_session()` call.

**Fix:**
```python
try:
    outcome = drive_session(
        args.task,
        provider_chain=chain,
        ...
        output=output_bus,
    )
except RuntimeError as exc:
    if "event_log_authority_unavailable" in str(exc):
        print(
            f"fa run: failed to write to session database at {log.path.parent / 'session.db'}: {exc}",
            file=sys.stderr,
        )
        return 2
    raise  # Re-raise unexpected RuntimeErrors
```

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_cmd_run_friendly_error_on_db_unavailable` | C1 via `_cmd_run` | C | exit_code=2, stderr contains "failed to write to session database" | Removing try/except produces raw traceback |

**LIVE-PATH PROOF:**
```
root: cli:_cmd_run
test: tests/test_observability_fix_p2.py::test_cmd_run_friendly_error_on_db_unavailable
matrix: C-defaults
oracle: outcome:exit_code==2 + stderr substring
kill-check: removing try/except around drive_session makes test fail (raw traceback, no friendly message)
efficiency: N/A
pyramid: A
```

---

## Phase 3: Global History Overwrite (LOGIC-11)

### 3.1 LOGIC-11 — Workflow stages overwrite each other in global_history.db

**Problem:** Each workflow stage calls `export_session_to_global_history()` with the SAME `run_id`. `INSERT OR REPLACE` on `run_id` PK causes each stage to overwrite the previous row. Only the last stage's role, turns, stop_reason, and exit_code survive.

**Design decision needed:** There are three options:
1. **Composite PK `(run_id, role)`** — one row per stage
2. **Aggregate at workflow end** — export once with `roles=planner→coder→eval`, `total_turns=17`
3. **Skip per-stage exports, export only from `_cmd_workflow`** — single export with full workflow picture

**Recommended: Option 2** — aggregate at workflow end. Rationale:
- `fa stats --global-history` is a cross-run analytics surface. One row per run is the expected granularity.
- Composite PK (option 1) changes the query API (every consumer must aggregate).
- Skip per-stage (option 3) requires re-plumbing the export call from `_cmd_run` to `_cmd_workflow`.

**Implementation for option 2:**

1. **In `_cmd_run`**: Skip global_history export when called from `_cmd_workflow` (detect via `outcome_sink` parameter — it's non-None only when called from `_run_stage` which is workflow).

   ```python
   # Only export to global_history if NOT part of a workflow
   # (workflow exports once with aggregate data at the end)
   if outcome_sink is None:
       try:
           export_session_to_global_history(...)
       except Exception as exc:
           ...
   ```

2. **In `_cmd_workflow`**: After all stages complete, export a single aggregated row.

   ```python
   # After workflow completes:
   try:
       from fa.inner_loop.global_history import export_session_to_global_history
       
       # Build aggregate row from all stages
       # Read ALL events from the shared session.db for telemetry
       log = EventLog(...)
       export_session_to_global_history(
           run_id=run_id,
           outcome=SessionOutcome(
               exit_code=final_exit_code,
               stop_reason=final_stop_reason,
               turns=total_turns_across_stages,
               final_text="",
               tool_results=(),
           ),
           log=log,
           role="→".join(roles),  # e.g. "planner→coder→eval"
           model=...,  # from last stage's chain_config
           family=...,
           workspace_root=workspace,
           duration_ms=total_duration_ms,
       )
   except Exception as exc:
       ...
   ```

3. **In `global_history.py`**: No schema change needed. The `role` column already supports arbitrary strings.

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_workflow_global_history_single_aggregate_row` | C2 `fa workflow` | C | global_history.db has exactly 1 row for the run_id with `role="planner→coder→eval"` and aggregate turns | Reverting to per-stage export overwrites and loses data |
| `test_non_workflow_still_exports` | C2 `fa run` | C | global_history.db has 1 row after `fa run` | Skipping export when `outcome_sink is None` is wrong direction |
| `test_workflow_aggregate_turns_correct` | C2 `fa workflow` | C | `turns` column = sum of all stage turns | Reverting shows only last stage's turns |
| `test_workflow_aggregate_tokens_correct` | C2 `fa workflow` | C | Token totals are cross-stage cumulative | Already correct in current code due to `_extract_telemetry_from_log` reading shared session.db |

**DECISION: Option 2 — Aggregate at workflow end.** Confirmed by user 2026-07-18.

---

## Phase 4: Console Visibility — EventType Expansion (LOGIC-5, LOGIC-9, FIX-1..5)

This is the largest phase. It adds new `EventType` literal values and corresponding handlers in `ConsoleRenderer`, plus `output.emit()` calls in `coder_loop.py`.

### 4.0 EventType expansion

**Current:** `EventType = Literal["session_start", "turn_start", "llm_response", "tool_call", "hook_deny", "api_retry", "session_end"]`

**New:**
```python
EventType = Literal[
    "session_start",
    "turn_start",
    "llm_response",
    "tool_call",
    "hook_deny",
    "api_retry",
    "session_end",
    "context_warn",       # NEW — context budget approaching limit
    "compaction_start",   # NEW — compaction stage starting
    "compaction_end",     # NEW — compaction stage completed/failed
    "subagent_start",     # NEW — subagent spawned
    "subagent_end",       # NEW — subagent done/failed
    "cost_alert",         # NEW — cost guardian threshold hit
    "loop_warn",          # NEW — loop guard warning
]
```

### 4.1 LOGIC-5 — `context_used_pct: None` hardcoded

**Fix location:** `src/fa/inner_loop/coder_loop.py` — `finish()` closure (line ~525).

**Fix:** Track the last budget check ratio and pass it to the output event.

```python
# Add tracking variable before the loop:
last_budget_ratio: float = 0.0

# Inside the budget check block (after each budget.check call):
decision = budget.check(usage)
last_budget_ratio = decision.get("ratio", 0.0)

# In finish(), replace "context_used_pct": None with:
"context_used_pct": round(last_budget_ratio * 100, 1),
```

### 4.2 LOGIC-9 — ProviderRequestShapeError no console event

**Fix location:** `src/fa/inner_loop/coder_loop.py` — `except ProviderRequestShapeError` handler (line ~1023).

**Fix:** Add an `output.emit()` call before `finish()`:
```python
except ProviderRequestShapeError as exc:
    state.log.append(
        actor="runtime",
        kind="run_stopped",
        content={"reason": "request_shape", "detail": str(exc)},
    )
    if output is not None:
        output.emit(
            OutputEvent(
                type="api_retry",  # reuse existing type — it's a provider error
                turn=turn,
                max_turns=max_turns,
                data={
                    "provider": "unknown",
                    "status": 0,
                    "retry_after_s": 0,
                    "reason": f"request_shape_error: {exc}",
                },
            )
        )
    return finish(...)
```

### 4.3 FIX-1 — context_warn OutputEvent

**Where to emit:** `coder_loop.py` — in the `context_budget_warn` event emission block (lines ~638, ~655).

```python
# After state.log.append(kind="context_budget_warn"):
if output is not None:
    output.emit(
        OutputEvent(
            type="context_warn",
            turn=turn,
            max_turns=max_turns,
            data={
                "pct": round(decision.get("ratio", 0) * 100),
                "action": decision.get("action", ""),
                "message": decision.get("message", ""),
            },
        )
    )
```

**ConsoleRenderer handler:**
```python
def _handle_context_warn(self, e: OutputEvent) -> None:
    d = e.data
    pct = d.get("pct", 0)
    action = d.get("action", "")
    if action in ("stage2", "stage3"):
        self._write(f"  {self._c('33', '⚠️')} context: {pct}% of window ({action})")
    else:
        if self.detail in ("verbose", "debug"):
            self._write(f"  {self._c('33', '⚠️')} context: {pct}% of window")
```

### 4.4 FIX-2 — compaction_start/end OutputEvent

**Where to emit:** `coder_loop.py` — at each `compaction_stage{2,3}_{start,done,error}` emission point.

```python
# After state.log.append(kind="compaction_stage2_start"):
if output is not None:
    output.emit(OutputEvent(
        type="compaction_start",
        turn=turn, max_turns=max_turns,
        data={"stage": 2, "tokens_before": usage},
    ))

# After state.log.append(kind="compaction_stage2_done"):
if output is not None:
    output.emit(OutputEvent(
        type="compaction_end",
        turn=turn, max_turns=max_turns,
        data={"stage": 2, "tokens_before": usage, "tokens_after": post_mask_usage, "ok": True},
    ))

# Similarly for stage3 and error cases.
```

**ConsoleRenderer handler:**
```python
def _handle_compaction_start(self, e: OutputEvent) -> None:
    d = e.data
    stage = d.get("stage", "?")
    self._write(f"  {self._c('36', '🗜️')} compaction stage{stage}: context at {d.get('tokens_before', 0)} tokens")

def _handle_compaction_end(self, e: OutputEvent) -> None:
    d = e.data
    stage = d.get("stage", "?")
    ok = d.get("ok", True)
    if ok:
        before = d.get("tokens_before", 0)
        after = d.get("tokens_after", 0)
        self._write(f"  {self._c('36', '🗜️')} compaction stage{stage}: done, {before} → {after} tokens")
    else:
        self._write(f"  {self._c('31', '❌')} compaction stage{stage} error: {d.get('error', 'unknown')}")
```

### 4.5 FIX-3 — subagent_start/end OutputEvent

**Where to emit:** `src/fa/inner_loop/tools/spawn_subagent.py` — at `subagent_spawn_{start,done,fail}` emission points.

This requires `spawn_subagent.py` to receive the `output` EventBus. Currently it doesn't have access. Two options:
- **Option A:** Pass `output` through `SessionState` (add `output_bus: EventBus | None = None` field).
- **Option B:** Emit via `state.log.append` only (already done) and add console rendering by polling the event log.

**Recommended: Option A** — it's the cleanest pattern and follows the existing `output.emit()` discipline.

**Implementation:**
1. Add `output_bus: EventBus | None = None` to `SessionState`.
2. In `cli.py:_cmd_run`, set `state.output_bus = output_bus` after creating state.
3. In `spawn_subagent.py`, after each `state.log.append(kind="subagent_spawn_...")`, also call:
   ```python
   if state.output_bus is not None:
       state.output_bus.emit(OutputEvent(
           type="subagent_start",  # or "subagent_end"
           ...
       ))
   ```

**DECISION: Option A — output_bus on SessionState.** Confirmed by user 2026-07-18.

### 4.6 FIX-4 — cost_alert OutputEvent

**Where to emit:** `src/fa/observability/cost_guardian.py` — when `cost_observation` event is emitted.

Same pattern as subagent: need `output_bus` access. With Option A above, `CostGuardian` receives `event_log` but not `output_bus`. Options:
- **Option A-extended:** Also pass `output_bus` to `CostGuardian`.
- **Option B:** Since CostGuardian is dormant (LOGIC-6), this is low-priority. Defer to when T-2 LLM driver lands.

**Recommendation:** Defer FIX-4 to P6. CostGuardian is dormant; adding `output_bus` plumbing for a feature that produces zero events in production is low ROI.

### 4.7 FIX-5 — loop_warn OutputEvent

**Where to emit:** `cli.py` — inside `_loop_guard_warn_sink` (added in Phase 1).

After appending to EventLog, also emit to the output bus. But `warn_sink` is a closure, not a method on a class. It needs access to `output_bus`.

**Fix:** Define `_loop_guard_warn_sink` after `output_bus` is created, capturing it in the closure:

```python
# In _cmd_run, AFTER output_bus creation:
def _loop_guard_warn_sink(detector: str, message: str) -> None:
    if log is not None:
        try:
            log.append(actor="hook", kind="loop_guard_warn", content={"detector": detector, "message": message})
        except Exception:
            pass
    if output_bus is not None:
        try:
            output_bus.emit(OutputEvent(
                type="loop_warn",
                data={"detector": detector, "message": message},
            ))
        except Exception:
            pass

hooks.register(LoopGuard(..., warn_sink=_loop_guard_warn_sink))
```

**ConsoleRenderer handler:**
```python
def _handle_loop_warn(self, e: OutputEvent) -> None:
    d = e.data
    self._write(f"  {self._c('33', '🔄')} loop detected: {d.get('detector', '?')} — {d.get('message', '')}")
```

### Phase 4 Test Plan Summary

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_context_used_pct_in_session_end` | C1 `drive_session` | A | `session_end` event data has `context_used_pct > 0` | Reverting `None` assignment makes pct always None |
| `test_context_warn_console_event` | C1 `drive_session` | A | `OutputEvent(type="context_warn")` emitted | Removing emit call makes test fail |
| `test_compaction_console_events` | C1 `drive_session` | B (compaction on) | `OutputEvent(type="compaction_start"/"compaction_end")` emitted | Removing emit calls makes test fail |
| `test_request_shape_console_event` | C1 `drive_session` | A | `OutputEvent(type="api_retry")` emitted with shape error | Removing emit makes test fail |
| `test_loop_warn_console_event` | C1 `drive_session` | A | `OutputEvent(type="loop_warn")` emitted | Removing warn_sink wiring makes test fail |
| `test_context_warn_detail_standard_shows` | C1 | A | stderr contains "⚠️ context:" at `--detail standard` | N/A (render test) |
| `test_compaction_detail_minimal_hidden` | C1 | B | stderr does NOT contain "🗜️" at `--detail minimal` | N/A |
| `test_loop_warn_detail_standard_shows` | C1 | A | stderr contains "🔄" at `--detail standard` | N/A |
| `test_context_used_pct_shows_in_session_end` | C1 | A | stderr contains "Context: XX% of window" | Reverting None assignment hides it |
| `test_abnormal_stop_length_guidance` | C1 | A | stderr contains actionable guidance for `abnormal_stop:length` | N/A |

---

## Phase 5: `fa stats` Retrieval Gaps (LOGIC-7, FIX-6..9)

### 5.1 LOGIC-7 — `fa stats` doesn't parse `tool_result` events

**Fix location:** `src/fa/stats.py:parse_session()`

**Fix:** Add `tool_result` handling to extract error details:
```python
elif kind == "tool_result":
    tool_name = event.tool_name
    ok = bool(content.get("ok", True))
    if not ok:
        error = content.get("error")
        if isinstance(error, dict):
            tool_errors.append(ToolError(
                tool=tool_name,
                code=str(error.get("code", "")),
                message=str(error.get("message", "")),
            ))
```

Add `ToolError` dataclass and `tool_errors: list[ToolError]` field to `SessionAnalytics`.

### 5.2 FIX-6 — Compaction section in `fa stats`

Add `CompactionRecord` dataclass and parse `compaction_stage{2,3}_{start,done,error}` events.

### 5.3 FIX-7 — Subagent section in `fa stats`

Parse `subagent_spawn_{start,done,fail}` events.

### 5.4 FIX-8 — Context budget section in `fa stats`

Parse `context_budget_warn` and `context_budget_hard_stop` events.

### 5.5 FIX-9 — Context budget summary in `fa stats`

Render compaction, subagent, context budget, and tool error sections in `render_session()`.

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_stats_parses_tool_result_errors` | C0 `parse_session` | N/A | `SessionAnalytics.tool_errors` non-empty for failed tools | Removing handler returns empty list |
| `test_stats_parses_compaction_events` | C0 `parse_session` | N/A | `SessionAnalytics.compaction_records` non-empty | Removing handler returns empty list |
| `test_stats_parses_subagent_events` | C0 `parse_session` | N/A | `SessionAnalytics.subagent_records` non-empty | Removing handler returns empty list |
| `test_stats_parses_context_budget_events` | C0 `parse_session` | N/A | `SessionAnalytics.context_budget_events` non-empty | Removing handler returns empty list |
| `test_stats_renders_compaction_section` | C0 `render_session` | N/A | stderr contains "Compaction:" | Removing render section hides it |
| `test_stats_renders_subagent_section` | C0 `render_session` | N/A | stderr contains "Subagent:" | Removing render section hides it |
| `test_stats_renders_tool_errors_section` | C0 `render_session` | N/A | stderr contains "Tool errors:" | Removing render section hides it |
| `test_stats_renders_context_budget_section` | C0 `render_session` | N/A | stderr contains "Context budget:" | Removing render section hides it |

---

## Phase 6: Design Gaps + Hygiene (LOGIC-17, LOGIC-18, LOGIC-19)

### 6.1 LOGIC-17 — Feature flag cascade silences budget telemetry after first warn

**Problem:** Default config has `context_budget_enabled: true` + `context_compaction_enabled: false`. Operator gets ONE warn at ~80%, then session dies at ~90% with zero intermediate signals.

**Fix:** In `coder_loop.py`, emit periodic context percentage signals at `--detail verbose+` regardless of compaction being enabled. This is a design enhancement, not a bug.

```python
# After budget.check() in the per-turn loop:
if budget_enabled:
    usage = estimate_tokens(messages_payload, tool_payload)
    decision = budget.check(usage)
    last_budget_ratio = decision.get("ratio", 0.0)
    
    # Always emit per-turn context percentage at verbose+ (even without warn)
    if output is not None and self.detail in ("verbose", "debug"):
        if decision["action"] == "ok" and last_budget_ratio > 0.5:
            output.emit(OutputEvent(
                type="context_warn",
                turn=turn, max_turns=max_turns,
                data={"pct": round(last_budget_ratio * 100), "action": "ok", "message": ""},
            ))
```

Wait — `detail` is not available in `coder_loop.py`. It's a `ConsoleRenderer` attribute. The correct approach is to always emit the event, and let the renderer decide whether to display it:

```python
# In coder_loop.py, after budget.check() every turn:
if budget_enabled and output is not None:
    output.emit(OutputEvent(
        type="context_warn",
        turn=turn, max_turns=max_turns,
        data={"pct": round(last_budget_ratio * 100), "action": decision["action"], "message": decision.get("message", "")},
    ))
```

Then in `_handle_context_warn`, show `action=="ok"` only at `--detail verbose+`.

**Test plan:** Covered by Phase 4's context_warn tests.

### 6.2 LOGIC-18 — Remove redundant `telemetry` event kind

**Fix location:** `src/fa/inner_loop/state.py:record_tool_result()` — remove the `self.log.append(kind="telemetry", ...)` call.

**Impact:** Every tool result currently writes both `telemetry` AND `tool_result` to session.db. Removing `telemetry` cuts event_log rows per tool call from 4 to 3 (tool_call + hook_decision + tool_result). Zero consumers read `telemetry` events — `fa stats` doesn't parse them, `global_history` doesn't use them.

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_no_telemetry_event_in_event_log` | C1 `drive_session` | C | No event with `kind="telemetry"` in session.db | Reverting fix re-introduces telemetry rows |

### 6.3 LOGIC-19 — Remove dead `CompactionManager` / `compaction_warning`

**Fix location:** `src/fa/inner_loop/compaction/foundation.py` — remove `CompactionManager` class.

**Pre-check:** Verify nothing imports from `foundation.py`:
```bash
grep -r "from fa.inner_loop.compaction.foundation" src/ tests/
grep -r "CompactionManager" src/ tests/
```

**Test plan:**

| Test | Root | Matrix | Oracle | Kill-check |
|------|------|--------|--------|------------|
| `test_no_compaction_warning_event_possible` | C0 import check | N/A | `foundation.py` does not exist or `CompactionManager` is removed | N/A |

---

**DECISIONS CONFIRMED (2026-07-18):**
- D1: Option B — Aggregate at workflow end for LOGIC-11
- D2: Option A — Add output_bus to SessionState, wire subagent AND cost
- D3: Keep proposed phase ordering (P1→P5)
- D4: LOGIC-10 included in P4 (abnormal_stop actionable guidance, ~10 lines)
- D5: Stop at P5, defer P6 to separate PR

---

## File Change Summary

| File | Phases | Changes |
|------|--------|---------|
| `src/fa/cli.py` | P1, P2, P3, P4 | Wire warn_sink, wire observers, skip per-stage export, add workflow export, try/except RuntimeError, session.db discovery |
| `src/fa/inner_loop/state.py` | P2, P6 | `_initial_next_id` DB-first, remove `telemetry` event |
| `src/fa/inner_loop/coder_loop.py` | P4, P6 | Compute `context_used_pct`, emit context_warn/compaction/loop_warn OutputEvents, per-turn context % signal |
| `src/fa/output.py` | P4 | Add 7 new EventType literals, add 7 handlers to ConsoleRenderer |
| `src/fa/inner_loop/global_history.py` | P3 | No change needed for option 2 (aggregate at workflow end) |
| `src/fa/stats.py` | P5 | Add tool_result, compaction, subagent, context_budget parsing + rendering |
| `src/fa/inner_loop/tools/spawn_subagent.py` | P4 | Emit subagent_start/end OutputEvents via state.output_bus |
| `src/fa/inner_loop/compaction/foundation.py` | P6 | Remove dead CompactionManager |
| `tests/test_observability_fix_p1.py` | P1 | 4 tests — loop_guard_warn + recovery_action wiring |
| `tests/test_observability_fix_p2.py` | P2 | 6 tests — _initial_next_id, session discovery, RuntimeError handling |
| `tests/test_observability_fix_p3.py` | P3 | 4 tests — global history overwrite |
| `tests/test_observability_fix_p4.py` | P4 | 10 tests — console visibility |
| `tests/test_observability_fix_p5.py` | P5 | 8 tests — fa stats parsing |

---

## Verification Protocol

After each phase:

1. **Run full test suite:** `just check` — all existing + new tests must pass.
2. **Kill-check audit:** For each new test, verify that removing the production call site fails the test.
3. **Type-check:** `pyright` / `mypy` must be clean on all changed files.
4. **Manual smoke test:** `fa run --detail verbose --task "echo hello"` must show new console output.
5. **DB integrity:** After `fa run`, inspect `session.db` with `sqlite3` — confirm:
   - All `event_id` values are unique
   - New event kinds (`loop_guard_warn`, `recovery_action`) appear when triggered
   - `context_used_pct` in `session_end` event is non-None
6. **Global history:** After `fa workflow`, inspect `global_history.db` — confirm single aggregate row.

---

## What NOT to Change

(per audit §7, reinforced)

- `EventLog.append()` dual-write discipline — it's correct
- `SessionDatabase` schema — event_log table is flexible (content is JSON)
- Console as authority — session.db remains authority
- Add new DB tables — not needed
- `fa stats` to read JSONL — it reads session.db via `EventLog.read_all()`
