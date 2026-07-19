# PR #53 Edge-Case Audit — Shipped Code vs. Implementation Plan

> **Created:** 2026-07-18  
> **Purpose:** Systematic comparison of the observability-fix implementation plan against the actual shipped code. Identifies gaps where the plan was only partially implemented, introduces new findings not in the original three-pass audit, and surfaces edge cases that arise from the interaction of multiple fixes.
> **Method:** Read every modified source file, trace every code path, compare against the plan document.

---

## 1. Plan vs. Shipped — Verification Matrix

| Plan Item | Status | Notes |
|-----------|--------|-------|
| P1: LOGIC-14 (warn_sink) | ✅ SHIPPED | Both call sites wired correctly |
| P1: LOGIC-15 (observers) | ✅ SHIPPED | Both call sites registered |
| P2: LOGIC-1 (_initial_next_id) | ✅ SHIPPED | DB-first with JSONL fallback |
| P2: LOGIC-13 (session.db discovery) | ✅ SHIPPED | `(d / "session.db").exists()` |
| P2: LOGIC-8 (RuntimeError handling) | ⚠️ PARTIAL | Only catches `event_log_authority_unavailable`; misses `event_log_write_failed` (see NEW-3) |
| P3: LOGIC-11 (global_history overwrite) | ⚠️ PARTIAL | Per-stage skip works; aggregate export has `turns=0` (see NEW-4) |
| P4: LOGIC-5 (context_used_pct) | ✅ SHIPPED | Tracked via `last_budget_ratio` |
| P4: LOGIC-9 (ProviderRequestShapeError) | ✅ SHIPPED | api_retry OutputEvent emitted |
| P4: FIX-1 (context_warn) | ⚠️ PARTIAL | Emitted in non-compaction path; MISSING in compaction-enabled hard-stop paths (see NEW-1) |
| P4: FIX-2 (compaction_start/end) | ✅ SHIPPED | All 4 compaction emission points covered |
| P4: FIX-3 (subagent_start/end) | ❌ NOT WIRED | EventType + handlers added, but `spawn_subagent.py` doesn't emit via `state.output_bus` |
| P4: FIX-4 (cost_alert) | ❌ NOT WIRED | EventType + handler added, but CostGuardian doesn't emit (dormant by design — noted in plan) |
| P4: FIX-5 (loop_warn) | ✅ SHIPPED | Emitted from `_loop_guard_warn_sink` in `_cmd_run` |
| P5: LOGIC-7 (tool_result errors) | ✅ SHIPPED | ToolError dataclass + parsing |
| P5: FIX-6 (compaction in stats) | ⚠️ PARTIAL | Parses `stage{2,3}_{done,error}` but not `compaction_circuit_breaker` or `stage{2,3}_start` (see NEW-5, NEW-6) |
| P5: FIX-7 (subagent in stats) | ✅ SHIPPED | SubagentRecord dataclass + parsing |
| P5: FIX-8/9 (context budget in stats) | ✅ SHIPPED | ContextBudgetEvent dataclass + parsing |
| P6: LOGIC-17 (feature flag cascade) | 🔲 DEFERRED | Per user decision |
| P6: LOGIC-18 (redundant telemetry) | 🔲 DEFERRED | Per user decision |
| P6: LOGIC-19 (dead CompactionManager) | 🔲 DEFERRED | Per user decision |

---

## 2. New Findings — Not in Original Audit

### NEW-1: Compaction-enabled hard-stop paths missing `context_warn` console event
**Severity:** Medium  
**Category:** Asymmetry bug — operator with compaction ON gets LESS console signal than with compaction OFF

**Evidence:** In `coder_loop.py`, the non-compaction `stage3` path emits:
```python
if output is not None:
    output.emit(OutputEvent(type="context_warn", data={"pct": ..., "action": "stage3", ...}))
```

But the compaction-enabled path has TWO hard-stop exits that emit NO `context_warn`:
1. After compaction circuit breaker triggers (line ~880)
2. After compaction completes but budget still exceeds stage3 (line ~920)

Both go directly to `finish()` without a console warning. The operator sees only the `session_end` with `stop_reason=context_budget_hard_stop` — no context percentage, no indication of whether compaction succeeded or the circuit breaker fired.

**Impact:** An operator debugging a context-budget session death with compaction enabled gets less diagnostic than one with compaction disabled. The asymmetry is confusing.

**Fix:** Add `context_warn` OutputEvent before each `return finish()` in the compaction-enabled hard-stop paths, mirroring the non-compaction path.

---

### NEW-2: Compaction circuit breaker has no console event
**Severity:** Low-Medium  
**Category:** Missing console signal for rare but important event

**Evidence:** The `compaction_circuit_breaker` event is written to EventLog:
```python
state.log.append(actor="runtime", kind="compaction_circuit_breaker", content={"message": ...})
```
But no `OutputEvent` is emitted. The operator sees only `FAIL: context_budget_hard_stop`.

**Fix:** Add a `compaction_end` OutputEvent with `ok=False` and `error="circuit_breaker"` after the `compaction_circuit_breaker` log append, OR add a `context_warn` with `action="circuit_breaker"`.

---

### NEW-3: LOGIC-8 fix incomplete — `event_log_write_failed` RuntimeError not caught
**Severity:** Medium  
**Category:** Logic error in existing fix

**Evidence:** `SessionDatabase.append_event_row()` wraps ALL write failures:
```python
except Exception as exc:
    raise RuntimeError(f"event_log_write_failed: {exc}") from exc
```

The `_cmd_run` handler only checks for `"event_log_authority_unavailable"`:
```python
except RuntimeError as exc:
    if "event_log_authority_unavailable" in str(exc):
        print(f"fa run: failed to write to session database at ...: {exc}", file=sys.stderr)
        return 2
    raise  # Re-raises event_log_write_failed → raw traceback
```

A mid-session DB write failure (disk full, SQLite lock timeout, corruption) produces `RuntimeError("event_log_write_failed: ...")` which is re-raised as a raw traceback — exactly the scenario LOGIC-8 was supposed to prevent.

**Fix:** Extend the condition:
```python
if any(s in str(exc) for s in ("event_log_authority_unavailable", "event_log_write_failed")):
```

---

### NEW-4: Workflow aggregate export has `turns=0` in global_history
**Severity:** Medium  
**Category:** Data accuracy — `fa stats --global-history` shows wrong turns for workflows

**Evidence:** The aggregate export creates:
```python
aggregate_outcome = _SO(
    exit_code=result_code,
    stop_reason="workflow_complete" if result_code == 0 else "workflow_failed",
    turns=0,  # ← hardcoded!
    ...
)
```

`build_export_row` reads `turns` from `outcome.turns` (which is 0), not from telemetry. `_extract_telemetry_from_log` doesn't extract turns either — it only extracts token totals and tool breakdown.

**Impact:** `fa stats --global-history` shows `turns=0` for workflow runs, which is incorrect.

**Fix options:**
- A) Count `usage` events in `_extract_telemetry_from_log` and add `turns` to the telemetry dict
- B) Sum `n_turns` from `session_summary` events in `_extract_telemetry_from_log`
- C) Pass actual turn count from the workflow controller instead of 0

---

### NEW-5: `fa stats` doesn't parse `compaction_circuit_breaker` events
**Severity:** Low  
**Category:** Missing stats coverage

The circuit breaker event is written to session.db but invisible in `fa stats`. An operator whose session died from the circuit breaker won't see it in the compaction section.

**Fix:** Add parsing in `parse_session()` for `kind == "compaction_circuit_breaker"` → append a `CompactionRecord(stage=0, ok=False, error="circuit_breaker")` or a dedicated field.

---

### NEW-6: `fa stats` doesn't parse `compaction_stage{2,3}_start` events
**Severity:** Low  
**Category:** Missing stats coverage — can't detect incomplete compactions

Currently only `done/error` events are parsed. A `start` without a matching `done/error` indicates compaction crashed mid-way, but `fa stats` can't detect this.

**Fix:** Track starts separately; if a start has no matching end, surface a warning in the compaction section.

---

### NEW-7: `fa stats --global-history` display truncates workflow role string
**Severity:** Trivial  
**Category:** Formatting

`"planner→coder→eval"` overflows the 8-character `role` column:
```python
f"{r.get('role',''):<8s}"
```

**Fix:** Increase column width or truncate with ellipsis.

---

### NEW-8: `import sqlite3` inside `_initial_next_id` instead of top of state.py
**Severity:** Trivial  
**Category:** Style deviation from plan

The implementation plan specified adding `import sqlite3` at the top of `state.py`. The actual code imports it inside the method. Functionally equivalent, but inconsistent.

---

### NEW-9: `state.output_bus` is set after state creation, leaving a window where it's None
**Severity:** Low (design concern, not current bug)  
**Category:** Ordering risk

`state = SessionState(...)` creates state with `output_bus=None`. Then `state.output_bus = output_bus` sets it later. Any code running between these two lines would see `output_bus=None`. Currently no such code exists, but future code could trip on this.

---

### NEW-10: `spawn_subagent.py` doesn't emit `subagent_start`/`subagent_end` OutputEvents via `state.output_bus`
**Severity:** Low (FIX-3 explicitly deferred in plan)  
**Category:** Partially implemented feature

The EventType literals and ConsoleRenderer handlers exist, but `spawn_subagent.py` doesn't call `state.output_bus.emit()`. The `state.output_bus` field is wired and available; the emit calls just need to be added.

---

## 3. Existing Known Gaps (from original audit, not yet addressed)

| ID | Severity | Description |
|----|----------|-------------|
| LOGIC-2 | Medium | Workflow flow_state.json/eval_report.json not in event_log |
| LOGIC-3 | Low | `fa stats` shows only last role in multi-stage workflow |
| LOGIC-10 | Low-Med | `abnormal_stop:*` paths lack actionable console guidance |
| LOGIC-12 | Low | `fa stats --global-history` doesn't show compaction flag |
| LOGIC-16 | Low-Med | `read_all()` O(n²) on every turn |
| FIX-3 | Low | subagent_start/end not wired in spawn_subagent.py |
| FIX-4 | Low | cost_alert not wired (dormant) |

---

## 4. Priority Ranking — New + Existing Gaps

### Must fix (data accuracy + operator blind spots) — ALL IMPLEMENTED
1. **NEW-3** ✅ FIXED — `_cmd_run` now catches both `event_log_authority_unavailable` and `event_log_write_failed` RuntimeErrors with distinct friendly messages
2. **NEW-1** ✅ FIXED — Compaction-enabled hard-stop paths now emit `context_warn(action="stage3")` before `finish()`, eliminating the asymmetry with the non-compaction path
3. **NEW-4** ✅ FIXED — `_extract_telemetry_from_log` counts `usage` events as turns; `build_export_row` uses `max(outcome_turns, telemetry_turns)` so workflow aggregates get correct turns from telemetry

### Should fix (console signal completeness) — PARTIALLY IMPLEMENTED
4. **NEW-2** ✅ FIXED — Circuit breaker now emits `compaction_end(ok=False, error="circuit_breaker: ...")` for console visibility
5. **FIX-3** — Wire subagent_start/end via state.output_bus (~10 lines in spawn_subagent.py) — STILL PENDING
6. **LOGIC-10** — abnormal_stop actionable guidance (~10 lines in coder_loop.py)

### Nice to fix (stats completeness + hygiene)
7. **NEW-5** — `fa stats` missing circuit breaker parsing (~5 lines)
8. **NEW-6** — `fa stats` missing start events for incomplete compaction detection (~10 lines)
9. **LOGIC-12** — `fa stats --global-history` show compaction flag (~3 lines)
10. **NEW-7** — Role column width overflow in global-history display (~2 lines)
11. **NEW-8** — Move `import sqlite3` to top of state.py (~2 lines)
12. **NEW-9** — Set output_bus in SessionState constructor or document the None window
