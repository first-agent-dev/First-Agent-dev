# Skill Gaps Analysis — tests-writing/SKILL.md

> **Created:** 2026-07-19
> **Goal:** Identify gaps and logic errors in the tests-writing skill that led to
> incomplete, overconfident test coverage during the PR #53 observability work.
> Apply root-cause analysis from the "not wired" bug class to make the skill
> force agents to write exhaustive, concrete tests that surface bugs.

---

## Methodology

Reviewed the current skill against three sources of ground truth:

1. **Root cause analysis** (RC-1/2/3) — documented structural failures
2. **Contract check script output** — objective gaps (2 CONSUMER-ONLY, 5 NO-C1-test)
3. **Actual test files** (P4, P5, edge-cases) vs. production code paths in coder_loop.py

Each gap below is linked to a concrete failure case from the PR #53 work.

---

## GAP 1: Kill-Check Vacuous Pass — No Existence Pre-Check

**Current text (§3, item 1):**
> "Kill-check — removing the production call site fails this test"

**What went wrong:**
The kill-check assumes the call site EXISTS. When FIX-3 (subagent) was "shipped,"
the emit call was never written in spawn_subagent.py. There was nothing to remove,
so the kill-check passed vacuously. The test verified the consumer (handler) was
wired, not that the producer (emit) existed at all.

**Why it's a logic error:**
Kill-check is a WIRING verification (the existing call site is connected correctly).
It is NOT a COMPLETENESS verification (the call site was written at all). The skill
conflates two distinct failure modes:

| Failure mode | Kill-check catches? | What catches it? |
|---|---|---|
| Call site exists but not wired | ✅ Yes | Kill-check |
| Call site never written | ❌ No (vacuous pass) | Needs explicit existence check |

**Fix:** Add a mandatory pre-check step before kill-check can be applied:

> **Existence pre-check (mandatory before kill-check):** Before declaring a feature
> "shipped," verify the production emit call SITE EXISTS in the source tree. If the
> call site cannot be located, the feature is NOT shipped — it is NOT WIRED, and
> the kill-check is vacuous.

This should be a new item in the anti-theater checklist and a new invariant.

---

## GAP 2: "Production Call Site" Ambiguity — Producer vs. Consumer

**Current text:**
> "removing the production call site must fail the test"

**What went wrong:**
For FIX-3, the plan's kill-check was: "removing `FailureClassifierObserver` registration
makes the test fail." This is a CONSUMER kill-check. The real kill-check should have
been: "removing `output_bus.emit(OutputEvent(type='subagent_start'))` from
spawn_subagent.py makes the test fail."

The skill's wording is ambiguous enough that an LLM agent can interpret "production
call site" as either the producer (emit) or the consumer (handler registration).

**Why it's a logic error:**
In event-driven architectures, there are TWO production call sites:
1. **Producer:** `output.emit(OutputEvent(type="X", ...))` — the code that SENDS the event
2. **Consumer:** `renderer._handle_X(event)` — the code that RECEIVES the event

Both need to exist and be wired. But the skill's kill-check principle doesn't
distinguish between them. When the agent applied kill-check to the consumer side,
it appeared to satisfy the skill's requirements while completely missing the
producer-side gap.

**Fix:** Redefine "production call site" explicitly:

> **Kill-check target = PRODUCER call site.** For event-driven features, "production
> call site" means the `output.emit()` / `log.append()` call in the loop/tools code
> — the code that PRODUCES the signal. Consumer handler registration is necessary
> but NOT sufficient for kill-check. A valid kill-check for an EventType must target
> the emit call, not the handler.

---

## GAP 3: Matrix Declaration ≠ Matrix Coverage

**Current text (I-TW-6):**
> "Flag (and provider, when relevant) matrix explicit in fixture or body."

**What went wrong:**
P4 tests all declared `matrix=A` (budget on, compaction OFF) in their docstrings.
No test ever exercised matrix B (compaction ON). The compaction-enabled hard-stop
path (circuit breaker at L919 and "still exceeds" at L974) was never tested.
FIX-1's gap (context_warn missing in circuit breaker) survived because no test
ever ran that path.

**Why it's a logic error:**
The skill treats "naming the matrix in the docstring" as the invariant. But naming
and COVERING are different operations. The invariant should be:

> For every flag combination that creates a distinct code path, at least one test
> MUST exercise that combination before the feature can be marked "shipped."

The current invariant is a declaration convention, not a coverage gate. It's the
difference between:
- ❌ "I named matrix B in my test plan" (current)
- ✅ "A test exists that runs with matrix B flags and asserts the expected behavior"

**Fix:** Replace I-TW-6 with:

> **I-TW-6 (revised):** For every feature that involves feature flags, identify ALL
> applicable matrix combinations (A/B/C/P). At least one C1 test per combination
> MUST exist before the feature can be marked "shipped." Naming the matrix in the
> docstring is necessary but NOT sufficient — the test must actually exercise
> that flag combination.

Add to the anti-theater checklist:
> **Matrix coverage gate:** For every test docstring that names a matrix, verify
> at least one test per matrix combination exists. If a matrix combination has
> no test, the feature is NOT shipped for that combination.

---

## GAP 4: No Two-Sided Contract Verification

**Current text:**
No concept of "producer-consumer contract" exists in the skill.

**What went wrong:**
6 out of 6 failures in PR #53 were the agent shipping the CONSUMER side (handler,
renderer, parser) but not the PRODUCER side (emit call in loop/tools). The skill
treats each finding as a unit of work and each test as proof of that unit. But
the CONTRACT between producer and consumer was never verified.

**Why it's a logic error:**
In event-driven systems, correctness requires BOTH sides:
- Producer emits → Consumer handles (happy path)
- Producer doesn't emit → Consumer never runs (but test might pass vacuously)
- Consumer doesn't handle → Producer output is invisible (but emit still works)

The skill has no mechanism to verify the contract is COMPLETE — that for every
EventType, both the producer emit and the consumer handler exist and are connected.

**Fix:** Add a new section on two-sided contracts:

> ### Two-Sided Contract Verification (event-driven systems)
>
> For every EventType or observable signal in the system:
>
> 1. **Producer proof (C1):** Test exercises the production code path and asserts
>    the signal is emitted. Kill-check: removing the emit call fails the test.
>
> 2. **Consumer proof (C0 or C1):** Test verifies the handler/renderer processes
>    the signal correctly. Kill-check: removing the handler fails the test.
>
> 3. **Contract check (automated):** A script that extracts all signal types from
>    the type definition and verifies that both producer emit and consumer handler
>    exist. Any gap = FAIL (exit 1).
>
> **Ordering rule:** Producer proof MUST exist before marking a feature "shipped."
> Consumer proof alone is INCOMPLETE — it proves the handler works GIVEN input,
> not that the input is ever produced.

---

## GAP 5: No Path Inventory Step

**Current text:**
No requirement to inventory ALL code paths that should emit a signal.

**What went wrong:**
There are at least 3 code paths that should emit `context_warn` in coder_loop.py:
1. Budget check → warn threshold (non-compaction, matrix A) — ✅ tested in P4
2. Budget check → stage3 after compaction (compaction, L974, matrix B) — ✅ tested in edge-cases
3. Circuit breaker → hard-stop (compaction, L919, matrix B) — ❌ MISSING (FINDING-V2)

The skill doesn't require the agent to enumerate all production paths that should
emit a given EventType. Without this inventory, it's easy to test one path and
assume coverage is complete.

**Why it's a logic error:**
Coverage is path-sensitive. A single EventType might be emitted from multiple
locations in production code, each triggered by different conditions. Testing one
path doesn't prove the others work.

**Fix:** Add a "path inventory" step:

> **Path inventory (mandatory for EventType claims):** Before writing tests for an
> EventType, enumerate ALL production code paths that should emit it. For each path,
> note the triggering condition, the file/line, and the flag combination required.
> At least one test per path must exist before the feature can be marked "shipped."
>
> Example:
> | Path | Trigger | Location | Flags |
> |------|---------|----------|-------|
> | 1 | Budget > warn threshold | coder_loop.py L515 | A (budget on, compaction off) |
> | 2 | Stage3 after compaction still exceeds | coder_loop.py L974 | B (both on) |
> | 3 | Circuit breaker fires | coder_loop.py L919 | B (both on) |

---

## GAP 6: C0 Consumer-Only Tests Create False Confidence

**Current text (§1):**
> "C0 Unit: Incomplete alone for session claims"

**What went wrong:**
The P4 test file has 3 C0 consumer-only tests at the bottom:
- `test_context_warn_visible_at_standard_detail` — proves handler renders context_warn
- `test_compaction_start_renders` — proves handler renders compaction_start
- `test_loop_warn_renders` — proves handler renders loop_warn

These tests create a false sense of coverage. They prove the handler works GIVEN
an event, but they do NOT prove the event is ever emitted by production code.
The skill's warning ("incomplete alone") is too weak — it doesn't explicitly
call out the consumer-only risk.

**Fix:** Strengthen the C0 warning and add an explicit rule:

> **C0 consumer-only tests are necessary but NEVER sufficient for event claims.**
> A C0 test that verifies a handler processes an event correctly does NOT prove
> the event is ever emitted. Every C0 consumer test for an EventType MUST be
> paired with a C1 producer test that exercises the production code path and
> asserts the emit call fires. Without this pairing, the C0 test is theater —
> it proves a dead handler works.

---

## GAP 7: No Dual-Write Consistency Rule

**Current text:**
No mention of dual-write systems.

**What went wrong:**
The observability system has two write paths:
1. **EventLog** (`log.append`) → session.db (authority) + JSONL (human-readable)
2. **EventBus** (`output.emit`) → ConsoleRenderer (operator visibility)

In the circuit breaker path (L919), EventLog was written but EventBus was NOT.
This is a dual-write gap — one write path is complete, the other is missing.

The skill has no rule requiring consistency between dual write paths.

**Fix:** Add a dual-write consistency rule:

> **Dual-write consistency (mandatory for systems with multiple output paths):**
> When a system writes to multiple outputs (e.g., EventLog + EventBus, database +
> cache, file + network), every code path that writes to one output MUST also write
> to the other. Verify this with a structural check: for every `log.append()` call
> with an operator-visible kind, verify a corresponding `output.emit()` call exists
> in the same code path, and vice versa.

---

## GAP 8: Output Format Missing Producer Verification

**Current output format:**
```
- root: drive_session | cli:<subcommand>
- test: tests/<file>.py::test_<name>
- matrix: A-gates-only | B-full-cascade | C-defaults | P-<family>
- oracle: event:<kind> | outcome:<stop_reason> | ...
- kill-check: removing <module.symbol / call site> fails the named test
- efficiency: call_count=N | early-stop (if claimed)
- pyramid: A
```

**Missing fields:**
- **producer:** Where the emit call is in production code (file:line)
- **paths-covered:** All code paths that should emit this event type
- **contract-check:** Whether the automated contract check passes

**Fix:** Add these fields to the output format:

```
- producer: <file.py>:<line> emit call site
- paths-covered: N/M paths (list any uncovered)
- contract-check: PASS | FAIL (<gaps>)
```

---

## GAP 9: Invariants Don't Cover Contract Completeness

**Current invariants (I-TW-1 through I-TW-13):**
None cover producer-consumer contracts, kill-check targeting, matrix enforcement,
dual-write consistency, or path inventory.

**Missing invariants:**

| ID | Invariant |
|----|-----------|
| I-TW-14 | For event-driven contracts, verify both producer (emit) and consumer (handler) exist before marking "shipped." |
| I-TW-15 | Kill-check targets the PRODUCER call site (emit), not the consumer registration. |
| I-TW-16 | Matrix coverage is enforced (≥1 test per flag combination), not just declared. |
| I-TW-17 | Dual-write systems require consistency: every write-to-A path must also write-to-B. |
| I-TW-18 | Path inventory is mandatory for EventType claims: enumerate ALL production paths, test each. |
| I-TW-19 | Existence pre-check: before kill-check, verify the emit call site EXISTS in source. Vacuous kill-check = not shipped. |

---

## GAP 10: Decision Tree Missing Contract Verification Steps

**Current decision tree has 11 steps.** None ask:
- "Is this a two-sided contract (producer/consumer)?"
- "Are all production code paths that emit this signal tested?"
- "Is the kill-check targeting the PRODUCER (emit) or the CONSUMER (handler)?"
- "Does the system have dual write paths? Are both consistent?"

**Fix:** Insert these as steps 4a-4d after the current step 4 (kill-check):

> 4a. **Two-sided contract?** If event-driven → verify both producer and consumer.
> 4b. **Kill-check target?** Must be the PRODUCER emit call, not the consumer handler.
> 4c. **Dual-write?** If system writes to EventLog + EventBus → verify both paths.
> 4d. **Path inventory?** For EventType claims → enumerate ALL emit paths, test each.

---

## CI Wiring Status: Contract Check Script is INERT

The `scripts/check_producer_consumer_contract.py` script is:

| CI surface | Wired? | Evidence |
|---|---|---|
| `just check` (justfile) | ❌ NO | `check: lock-check lint typecheck authoring-check test` |
| `check` (Makefile) | ❌ NO | `check: lock-check lint typecheck authoring-check test` |
| `.pre-commit-config.yaml` | ❌ NO | Not listed in any hook |
| Any CI workflow | ❌ NO | Not referenced anywhere |

The script must be manually run. It currently **exits 1** due to:
- `subagent_start` — CONSUMER ONLY (handler exists, no emit)
- `subagent_end` — CONSUMER ONLY (handler exists, no emit)
- 5 EventTypes with NO C1 test (warnings, not errors)

**Decision needed:** Wire it now (CI breaks until gaps are fixed) or fix gaps first
then wire?

---

## Summary: Root Cause → Gap → Fix Mapping

| Root Cause | Skill Gap | Proposed Fix |
|---|---|---|
| RC-1: Kill-check misapplied to consumer | GAP 1: Vacuous pass, GAP 2: Producer vs Consumer ambiguity | Existence pre-check + redefine kill-check target as producer |
| RC-2: Matrix declared not enforced | GAP 3: Declaration ≠ Coverage | Matrix coverage gate: ≥1 test per flag combination |
| RC-3: No structural completeness check | GAP 4: No two-sided contract, GAP 7: No dual-write rule | Contract check section + dual-write consistency rule |
| Unlisted: Path sensitivity | GAP 5: No path inventory | Mandatory path inventory for EventType claims |
| Unlisted: C0 false confidence | GAP 6: C0 consumer-only = theater | Explicit rule: C0 consumer MUST pair with C1 producer |
| Unlisted: Missing output fields | GAP 8: No producer/paths in output format | Add producer, paths-covered, contract-check fields |
| Unlisted: Invariant gaps | GAP 9: I-TW-* missing 6 invariants | Add I-TW-14 through I-TW-19 |
| Unlisted: Decision tree gaps | GAP 10: No contract steps in decision tree | Add 4a-4d after step 4 |
