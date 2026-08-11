# PR #53 Observability — Post-Implementation Verification Audit

> **Created:** 2026-07-19
> **Purpose:** Independent verification of the P1–P5 + edge-case implementation against the original audit findings, implementation plan, and edge-case audit. Traces every code path, identifies new gaps not in the original three-pass audit, and produces a final status matrix.
> **Method:** Read every modified source file, trace every code path, compare against plan + edge-case documents. Run all 38 observability tests. Check for logic errors introduced by the fixes themselves.

---

## 1. Test Suite Status

All 38 observability tests pass:

| Suite | Count | Status |
|-------|-------|--------|
| test_observability_fix_p1.py | 4 | ✅ ALL PASS |
| test_observability_fix_p2.py | 6 | ✅ ALL PASS |
| test_observability_fix_p3.py | 4 | ✅ ALL PASS |
| test_observability_fix_p4.py | 7 | ✅ ALL PASS |
| test_observability_fix_p5.py | 9 | ✅ ALL PASS |
| test_observability_edge_cases.py | 8 | ✅ ALL PASS |
| **Total** | **38** | **✅ ALL PASS** |

---

## 2. Plan vs. Shipped — Final Verification Matrix

| Plan Item | Status | Verification |
|-----------|--------|--------------|
| P1: LOGIC-14 (warn_sink) | ✅ SHIPPED | Both call sites (`_cmd_run`, `_cmd_inner_loop_smoke`) wired. C1 test passes. |
| P1: LOGIC-15 (observers) | ✅ SHIPPED | Both `FailureClassifierObserver` and `AttemptHistoryObserver` registered in both entry points. C1 test passes. |
| P2: LOGIC-1 (_initial_next_id) | ✅ SHIPPED | DB-first with JSONL fallback. C0 + C1 tests pass. `import sqlite3` inside method (NEW-8 — style only). |
| P2: LOGIC-13 (session.db discovery) | ✅ SHIPPED | `(d / "session.db").exists()` replaces JSONL check. C2 test passes. |
| P2: LOGIC-8 (RuntimeError handling) | ✅ SHIPPED | Both `event_log_authority_unavailable` AND `event_log_write_failed` caught with distinct messages. |
| P3: LOGIC-11 (global_history overwrite) | ✅ SHIPPED | Per-stage export skipped via `outcome_sink is None` guard. Workflow exports single aggregate row. |
| P4: LOGIC-5 (context_used_pct) | ✅ SHIPPED | `last_budget_ratio` tracked; `round(last_budget_ratio * 100, 1)` in finish(). |
| P4: LOGIC-9 (ProviderRequestShapeError) | ✅ SHIPPED | `api_retry` OutputEvent emitted with `reason="request_shape_error: ..."`. |
| P4: FIX-1 (context_warn) | ✅ SHIPPED + NEW-1 FIX | Emitted in all paths: warn, stage2 (no compaction), stage3 (no compaction), compaction stage3-still-exceeds (NEW-1). |
| P4: FIX-2 (compaction_start/end) | ✅ SHIPPED + NEW-2 FIX | All 4 compaction emission points covered + circuit breaker (NEW-2). |
| P4: FIX-3 (subagent_start/end) | ❌ NOT WIRED | EventType + handlers exist in output.py. `spawn_subagent.py` doesn't emit via `state.output_bus`. `state.output_bus` IS available. |
| P4: FIX-4 (cost_alert) | ❌ NOT WIRED (dormant by design) | EventType + handler exist. CostGuardian doesn't emit. Deferred per plan. |
| P4: FIX-5 (loop_warn) | ✅ SHIPPED | `_loop_guard_warn_sink` closure emits to both EventLog and output_bus. |
| P5: LOGIC-7 (tool_result errors) | ✅ SHIPPED | `ToolError` dataclass + parsing in `parse_session()`. |
| P5: FIX-6 (compaction in stats) | ⚠️ PARTIAL | Parses `stage{2,3}_{done,error}` but not `compaction_circuit_breaker` (NEW-5) or `stage{2,3}_start` (NEW-6). |
| P5: FIX-7 (subagent in stats) | ✅ SHIPPED | `SubagentRecord` dataclass + parsing. |
| P5: FIX-8/9 (context budget in stats) | ✅ SHIPPED | `ContextBudgetEvent` dataclass + parsing + rendering. |
| P6: LOGIC-17 | 🔲 DEFERRED | Per user decision. |
| P6: LOGIC-18 | 🔲 DEFERRED | Per user decision. |
| P6: LOGIC-19 | 🔲 DEFERRED | Per user decision. |

---

## 3. New Findings from This Verification Pass

### FINDING-V1: `import os` inside `_cmd_run` shadows module-level `os` — **CRITICAL PRODUCTION BUG**

**Severity:** CRITICAL
**Category:** Variable shadowing causes UnboundLocalError at runtime

**Evidence:**
- `_cmd_run.__code__.co_varnames` includes `'os'` — Python compiles `import os` at line 1895 as a local variable assignment for the entire function scope.
- Line 1667: `os.environ["NO_COLOR"] = "1"` — guarded by `if no_color`, so not hit in tests.
- Line 1761: `run_id = args.run_id or f"run-{os.getpid()}"` — **UNGUARDED**, hit whenever `--run-id` is not provided.
- Line 1897: `os.environ.get("FA_PTY_POOL_MAX_SIZE", "2")` — the `import os` at line 1895 makes this work, but breaks all earlier `os` references.

**Impact:** Any user running `fa run --task "hello"` WITHOUT `--run-id` gets `UnboundLocalError: cannot access local variable 'os' where it is not associated with a value`. The `--no-color` flag also crashes.

**Fix:** Remove the inner `import os` at line 1895. The module-level `import os` at line 13 is already available.

**Verification:**
```python
# Before fix: os is local
'_cmd_run'.__code__.co_varnames includes 'os'
# After fix: os is not local — uses module-level import
```

### FINDING-V2: `_cmd_inner_loop_smoke` warn_sink doesn't emit loop_warn OutputEvent

**Severity:** Low (asymmetry, not data loss)
**Category:** Same as noted in previous session's summary — confirmed still open

**Evidence:** The `_smoke_loop_guard_warn_sink` in `_cmd_inner_loop_smoke` only writes to EventLog, not to output_bus. The `_loop_guard_warn_sink` in `_cmd_run` writes to both. This asymmetry means the smoke entry point has less console visibility than `fa run`.

**Impact:** Minor — smoke is a diagnostic entry point, not production. But the asymmetry is misleading for developers reading both code paths.

---

## 4. Previously Identified Gaps — Confirmed Still Open

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| LOGIC-2 | Medium | Workflow flow_state.json/eval_report.json not in event_log | OPEN |
| LOGIC-3 | Low | `fa stats` shows only last role in multi-stage workflow | OPEN |
| LOGIC-10 | Low-Med | `abnormal_stop:*` paths lack actionable console guidance | OPEN |
| LOGIC-12 | Low | `fa stats --global-history` doesn't show compaction flag | OPEN |
| LOGIC-16 | Low-Med | `read_all()` O(n²) on every turn | OPEN |
| FIX-3 | Low | subagent_start/end not wired in spawn_subagent.py | OPEN |
| FIX-4 | Low | cost_alert not wired (dormant by design) | OPEN |
| NEW-5 | Low | `fa stats` doesn't parse `compaction_circuit_breaker` | OPEN |
| NEW-6 | Low | `fa stats` doesn't parse `compaction_stage{2,3}_start` | OPEN |
| NEW-7 | Trivial | Role column width overflow in global-history display | OPEN |
| NEW-8 | Trivial | `import sqlite3` inside `_initial_next_id` instead of top of state.py | OPEN |
| NEW-9 | Low | `state.output_bus` set after state creation — None window | OPEN |
| NEW-10 | Low | `spawn_subagent.py` doesn't emit subagent_start/end via state.output_bus | OPEN (= FIX-3) |

---

## 5. Session.db Authority Conformance: 6/7

Same as previous session. LOGIC-2 still deviates — workflow artifacts are standalone files not in event_log.

---

## 6. Event Kinds — Production Status

| Kind | Status | Notes |
|------|--------|-------|
| `loop_guard_warn` | ✅ LIVE | Wired via warn_sink in P1 |
| `recovery_action` | ✅ LIVE | Wired via FailureClassifierObserver in P1 |
| `compaction_warning` | ❌ DEAD | Only in dead CompactionManager (LOGIC-19) |
| `timeout` | ❌ DEAD | Never emitted in production |
| `service_unavailable` | ❌ DEAD | Never emitted in production |
| `cost_observation` | 💤 DORMANT | CostGuardian wired but no cost artifacts yet |
| `telemetry` | ⚠️ REDUNDANT | Written alongside `tool_result` — zero consumers (LOGIC-18) |

---

## 7. Critical Fix Required: FINDING-V1

The `import os` shadowing bug (FINDING-V1) is a **blocking production issue** that must be fixed before any merge. All other findings are lower priority and can be addressed incrementally.
