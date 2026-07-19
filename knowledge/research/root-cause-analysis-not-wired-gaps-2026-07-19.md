# Root Cause Analysis — "Not Wired / Partial Implementation" Slippage

> **Created:** 2026-07-19
> **Question:** Why did detailed implementation plans + tests-writing skill + three-pass audits fail to prevent partial/wired implementations from being marked "shipped"?

---

## The Pattern

Every failure follows the same structure:

```
PRODUCER (emit call in loop/tools)  ←→  CONSUMER (handler in ConsoleRenderer)
        ↑                                          ↑
   Agent skips or                             Agent reliably ships
   partially implements                       this side
```

**6 out of 6 failures** are the agent shipping the CONSUMER but not the PRODUCER:

| Finding | Consumer shipped? | Producer shipped? | Test covers producer? |
|---------|:-:|:-:|:-:|
| LOGIC-8 (partial) | ✅ caught first RuntimeError | ❌ missed second variant | ❌ test only checked first |
| LOGIC-11 (partial) | ✅ per-stage skip works | ❌ aggregate turns=0 | ❌ no workflow export test |
| FIX-1 (partial) | ✅ context_warn in non-compaction | ❌ missing in compaction path | ❌ no matrix B test |
| FIX-3 (not wired) | ✅ handler exists | ❌ no emit in spawn_subagent | ❌ no test at all |
| FIX-4 (not wired) | ✅ handler exists | ❌ no emit in CostGuardian | ❌ no test (deferred) |
| FIX-6 (partial) | ✅ parses done/error | ❌ misses circuit_breaker, starts | ❌ tests only covered done/error |

## The Three Root Causes

### RC-1: Kill-Check Misapplied — Tests Verify Consumption, Not Production

The tests-writing skill says:

> "removing the production call site must fail the test"

But in practice, the "production call site" was interpreted as **the handler registration**, not **the emit call in the loop**. This is a critical misreading.

For FIX-3 (subagent), the test plan said:
> "removing `FailureClassifierObserver` registration makes test fail"

This is a CONSUMER kill-check. The real kill-check should have been:
> "removing `output_bus.emit(OutputEvent(type='subagent_start'))` from spawn_subagent.py makes the test fail"

Since that emit call was never written, there was nothing to remove, and the test passed vacuously.

**The structural gap:** The kill-check principle as written assumes the call site EXISTS and tests whether it's correctly wired. It has no mechanism to detect a call site that was NEVER WRITTEN.

### RC-2: Matrix Coverage Incomplete — Tests Covered Path A, Not Path B

The implementation plan defined explicit flag matrices:
- **A:** budget on, compaction off
- **B:** budget on, compaction on (full cascade)
- **C:** defaults

But the P4 tests only exercised matrix A. The compaction-enabled paths (matrix B) were never tested. This is why FIX-1's gap (context_warn missing in compaction hard-stop) survived — no test ever ran the compaction-on path to stage3.

The skill says "name the matrix in every test docstring" but doesn't enforce that ALL matrices are covered. It's a declaration convention, not a coverage gate.

### RC-3: No Structural Completeness Check — Plan Items Marked Done Without Producer Verification

The implementation plan listed each finding as a unit of work. The agent worked through them sequentially, and when the consumer-side code + tests passed, it marked the item "shipped." There was no step that said:

> "For each EventType added, verify: (1) handler exists in ConsoleRenderer, (2) emit call exists in production code, (3) C1 test covers the emit call."

This is a "two-sided contract" verification — the producer and consumer are independently testable, but the CONTRACT between them (that the producer emits what the consumer expects) was never verified.

## Why the Audits Didn't Catch It

The three-pass audit (19 findings) was thorough at finding EXISTING bugs. But it was designed to find what's BROKEN, not what's MISSING. The audit read code and found:
- Dead code paths (warn_sink not wired)
- Logic errors (wrong variable used)
- Missing error handling (RuntimeError not caught)

It was NOT designed to check: "for every EventType added, does the producer emit it?" That's a structural completeness check, not a bug-finding check.

The edge-case audit (10 new findings) came closer — it compared the plan against shipped code and found gaps. But it was done AFTER implementation, not DURING. By then, the agent had already marked items as "shipped."

## The Same Bug Class — Still Present

From the audits above, here's what's still affected:

### A. Producer-Consumer Gap (EventType with handler but no emit)
| EventType | Handler? | Producer? | Gap |
|-----------|:-:|:-:|-----|
| `subagent_start` | ✅ | ❌ | FIX-3, known |
| `subagent_end` | ✅ | ❌ | FIX-3, known |
| `cost_alert` | ✅ | ❌ | FIX-4, dormant by design |

### B. Dual-Write Gap (EventLog written but no EventBus emit)
| Location | Kind | EventLog? | EventBus? | Status |
|----------|------|:-:|:-:|-----|
| coder_loop L919 | `context_budget_hard_stop` (circuit breaker) | ✅ | ✅ | **FIXED** (FINDING-V2) |
| coder_loop L559 | `hook_deny` (BEFORE_LLM_CALL) | ✅ | ✅ | Already had emit |
| coder_loop L1229 | `hook_deny` (AFTER_LLM_CALL) | ✅ | ✅ | **FIXED** (dual-write audit) |
| spawn_subagent L85 | `subagent_spawn_start` | ✅ | ✅ | **FIXED** (FIX-3) |
| spawn_subagent L121 | `subagent_spawn_done/fail` | ✅ | ✅ | **FIXED** (FIX-3) |
| spawn_subagent L156 | `subagent_spawn_fail` | ✅ | ✅ | **FIXED** (FIX-3) |

### C. Stats Parsing Gap (EventLog written but stats.py doesn't parse)
| Kind | Written? | Parsed? | Gap |
|------|:-:|:-:|-----|
| `compaction_circuit_breaker` | ✅ | ❌ | NEW-5 |
| `compaction_stage2_start` | ✅ | ❌ | NEW-6 |
| `compaction_stage3_start` | ✅ | ❌ | NEW-6 |
| `subagent_spawn_start` | ✅ | ❌ | Missing |
| `model_msg` | ✅ | ❌ | Low priority (already counted via usage) |
| `telemetry` | ✅ | ❌ | LOGIC-18 (redundant kind) |

### D. C1 Test Coverage Gap (EventType with no producer test)
| EventType | C1 Test? | C0 Test? | Gap |
|-----------|:-:|:-:|-----|
| `compaction_start` | ❌ | ✅ | Producer test missing |
| `compaction_end` | ❌ | ❌ | No test at all |
| `subagent_start` | ❌ | ❌ | No test at all |
| `subagent_end` | ❌ | ❌ | No test at all |
| `cost_alert` | ❌ | ❌ | No test (dormant) |

## Proposed Structural Fix: The Producer-Consumer Contract Check

Add to the tests-writing skill (or as a standalone verification step):

### Rule: Two-Sided Contract Verification

For every **new EventType** or **new EventLog kind** that is operator-visible:

1. **Producer test (C1):** A test that exercises the production code path and asserts the event appears on the EventBus or in session.db. Kill-check: removing the `output.emit()` or `log.append()` call makes the test fail.

2. **Consumer test (C0 or C1):** A test that verifies the handler/renderer processes the event correctly. Kill-check: removing the handler makes the test fail.

3. **Contract check (automated):** A script that:
   - Extracts all EventType literals from `output.py`
   - For each, checks that `output.emit(OutputEvent(type="<et>"))` appears in production code
   - For each, checks that a C1 test exists
   - Reports any gap

4. **Matrix coverage gate:** For every test that involves feature flags, the test docstring MUST name all applicable matrices AND at least one test per matrix MUST exist before the item can be marked "shipped."

### Automated Script

```python
# scripts/check_producer_consumer_contract.py
# Verifies that every EventType has both a producer and a consumer.
# Run as part of `just check` or CI.

# For each EventType:
#   1. Handler exists in ConsoleRenderer? (consumer)
#   2. output.emit() call exists in production code? (producer)
#   3. C1 test exists? (kill-check on producer)
# Report gaps as FAIL.
```

This turns the "not wired" bug class from a human-audit finding into an automated CI gate.

---

## Summary

| Question | Answer |
|----------|--------|
| What went wrong? | Agent shipped consumer-side code (handlers, parsers) but skipped or partially implemented producer-side code (emit calls). Tests verified consumers work given input, not that producers emit. |
| Why didn't the skill catch it? | Kill-check was misapplied to consumer registration, not producer emission. Matrix coverage was declared but not enforced. No structural completeness check existed. |
| Same class of bug elsewhere? | Yes — 3 EventType handlers with no producer, 1 dual-write gap in circuit breaker path, 5 stats parsing gaps, 4 EventTypes with no C1 test. |
| How to prevent it? | Add Producer-Consumer Contract Check as automated CI gate. Require C1 producer test before marking any EventType item "shipped." Enforce matrix coverage (not just declaration). |
