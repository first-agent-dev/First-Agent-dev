# Merged Guardrail Action Plan — Internal v2 + External Verification Reconciled

**Date**: 2026-07-19
**Status**: RECONCILED — Ready for user architectural decisions, then phased execution
**Principle**: Less surface, more simple and robust, all intended functional preserved.
**Mode**: MAX effort, verifiable steps, each phase independently shippable.

---

## §0 Executive Summary

This document reconciles two independent analyses of guardrail gaps in the FA codebase:

1. **Internal v2** (`missing-guardrail-dimensions-2026-07-19.md`) — 10 gaps, verified against production systems
2. **External adversarial** (`external-verification-guardrail-gaps-2026-07-19.md`) — 10 gaps re-verified + 6 new + 5 interaction failures + 4 outside-the-box suggestions

After direct source-code verification, **3 external claims are FALSIFIED**, **5 contradictions are resolved**, and **4 outside-the-box suggestions are evaluated** against the subtraction-first principle. The result is a single merged priority matrix and an updated P1–P5 implementation plan.

---

## §1 Fact Verification — External vs. Actual Code

### 1.1 FALSIFIED: "7 EventTypes" Claim

**External claimed**: `src/fa/output.py` defines `EventType` Literal with **7** members.

**Actual code** (verified by reading `output.py` + running `check_producer_consumer_contract.py`):

```
EventType literals: 14
ConsoleRenderer handlers: 14
Producer emit() calls: 26 across 13 types
C1 tested: 13 types
```

The 14 EventTypes are:
1. `session_start`  2. `turn_start`  3. `llm_response`  4. `tool_call`
5. `hook_deny`  6. `api_retry`  7. `session_end`  8. `context_warn`
9. `compaction_start`  10. `compaction_end`  11. `subagent_start`  12. `subagent_end`
13. `cost_alert`  14. `loop_warn`

**Impact**: ALL recommendations in the external doc assuming a 7-type model must be rebuilt around the actual 14-type model. The 14-type contract check is working and passing.

### 1.2 FALSIFIED: "check_producer_consumer_contract.py does not exist"

**External claimed**: The script doesn't exist on the branch.

**Actual**: The script exists at `scripts/check_producer_consumer_contract.py` (206 lines), runs successfully, and exits 0. It validates all 14 EventTypes for producer-consumer contract compliance AND C1 test coverage.

### 1.3 CONFIRMED: FeatureFlags field count

**External claimed**: 12 fields. **Actual**: 13 fields (the external read an older version or miscounted).

The 13 fields are: `blackboard_enabled`, `telemetry_enabled`, `tool_batching_enabled`, `subagent_spawning_enabled`, `context_budget_enabled`, `context_compaction_enabled`, `pty_pool_max_size`, `worktree_mode`, `fts_db_path`, `prompt_caching`, `offload_threshold`, `max_subagent_spawns_per_session`, `blackboard_filtered_history_include_plans`.

### 1.4 CONFIRMED: check_protected_paths.py exits 0 for dependency hits

Verified in source code (line 159: `return 1 if fail_on_touch else 0`, default `fail_on_touch=False`). The supply-chain advisory weakness is real.

### 1.5 CONFIRMED: 57.5% violation reduction is UNVERIFIED

Both analyses agree. No retrievable source. Excluded from all yield estimates.

### 1.6 CONFIRMED: Auto-TRACE violates AGENTS.md rule #1

Both analyses agree. G2 must be human-mediated.

---

## §2 Contradiction Resolution

### 2.1 G6 Ranking: Internal #1 HIGH vs External WEakened

**Internal v2**: Ranked G6 (error message actionability) as #1 — "highest-ROI improvement because it costs almost nothing but directly improves the next LLM round."

**External**: Weakened G6 — "RuleResult already has `severity`, `code`, `path`, `line`, `message`, `remediation`. The real gap is G2 (no TRACE mechanism to USE the messages), not message quality."

**Resolution**: **Both are right about different scopes.**

- The external is correct that `RuleResult` in `authoring_tcb.py` already has world-class structured diagnostics. The authoring_tcb path does NOT need message improvement.
- The internal was right that the BROADER codebase (provider code, CLI code, inner loop, state.py) has many unstructured `raise ValueError(...)` and `logger.error(...)` calls that lack actionable context.
- The user explicitly said: "properly log all possible errors — it's early dev stage. make logging and error messages explicit where possible." And: "goal is to build robust logging of all events for all usage scenarios with explicit error messaging."

**Merged verdict**: G6 is reframed as **"Error message actionability in non-RuleResult code paths"** — specifically:
- Provider adapter code (`src/fa/providers/`) — unstructured exceptions
- CLI code (`src/fa/cli.py`) — bare `sys.exit(1)` with no context
- Inner loop code (`src/fa/inner_loop/`) — generic `RuntimeError` without remediation hints
- State initialization code — `getattr` fallbacks that swallow errors silently

This is folded into Phase 5 (P5) of the implementation plan as the NEW-3/NEW-4 items already specified.

**G6 does NOT justify a dedicated new control** — it's a code-quality pass across existing modules. The external's subtraction-first assessment is correct on this point.

### 2.2 G2 TRACE Design: Human-Mediated Only

**No contradiction** — both analyses agree. The implementation plan's Phase 5 already specifies `.fa/corrections.jsonl` + `scripts/compile_corrections.py` as a **human-mediated** mechanism. No automatic TCB mutation.

### 2.3 G1 Import-Linter: Standalone vs. Paired with Dynamic-Import Guard

**External**: Import-linter alone is bypassable via `importlib.import_module()`. Must pair with N-G4.

**Resolution**: Accept the external's interaction analysis (I-1). G1 is retained but **downgraded to MEDIUM** and **must be paired with an AST-based dynamic-import scan**. However, since import-linter adds a new dependency (`grimp` or `import-linter` package), and FA's module structure is small (~6 packages), the pragmatic approach is:

1. Add a **dynamic-import AST scanner** as a Level-1 authoring rule (no new dependency)
2. Defer import-linter until the codebase grows enough to justify the dependency

This aligns with the user's "less surface, more simple" principle.

### 2.4 G3 ADR Invariant Enforcement: Dedicated Control vs. Not Justified

**External applied subtraction-first**: Existing protected-path governance + frozen TCB convention + test-binding covers ~85% of risk. One executable check for `ADR-11-I1` (stdlib-only) is sufficient.

**Resolution**: Accept the external's assessment. G3 does NOT justify a dedicated control. The existing combination of `check_protected_paths.py` + frozen TCB + SKILL.md test-binding is "good enough." Add ONE executable check for `ADR-11-I1` as a quick win (30 minutes), then move on.

### 2.5 G9 Before G13: Measurement Before Enforcement

**External interaction I-4**: "Without G9, G13 contracts can't be validated — there's no data on whether contracts are violated. Without G13, G9 has nothing meaningful to measure."

**Resolution**: Accept the dependency ordering. G9 (meta-observability) ships first, G13 (behavioral contracts) ships second. In the implementation plan, G9's metric collector is in Phase 2, G13's behavioral assertions are in Phase 4.

---

## §3 Reconciled Priority Matrix

| Rank | Gap | Internal Rating | External Rating | **Merged Rating** | Rationale |
|------|-----|----------------|----------------|-------------------|-----------|
| 1 | G2: TRACE / Correction Compilation | HIGH | CONFIRMED HIGH | **HIGH** | Highest strategic value. Human-mediated only per AGENTS.md. |
| 2 | G9: Harness Observability / Meta-Metrics | HIGH | CONFIRMED HIGH | **HIGH** | Foundational — enables data-driven improvement of all other gates. |
| 3 | G12: Supply-Chain Slopsquatting | MEDIUM | CONFIRMED, elevated | **HIGH** | Catastrophic impact (malicious dependency). Simplest fix: make blocking. |
| 4 | G11: Context Rot Defense | MEDIUM | CONFIRMED | **MEDIUM** | Procedural defense insufficient. Needs automatic enforcement. |
| 5 | G4: Inferential Sensors | MEDIUM | CONFIRMED, elevated | **MEDIUM** | Single highest-yield gap for production adoption (external). But high implementation cost. |
| 6 | G13: Behavioral Contract Enforcement | MEDIUM | CONFIRMED | **MEDIUM** | Depends on G9 (I-4). Runtime enforcement of agent loop behavior. |
| 7 | G1: Architecture Fitness (import-linter) | MEDIUM | CONFIRMED but incomplete | **MEDIUM→LOW** | Incomplete without N-G4. Small codebase doesn't justify new dependency. |
| 8 | G6: Error Message Actionability (non-RuleResult) | HIGH | WEAKENED | **MEDIUM→reframed** | RuleResult is already good. Non-RuleResult code paths need work. |
| 9 | G3: ADR Invariant Enforcement | LOW-MEDIUM | REFINED (not justified) | **LOW** | Existing mechanisms cover ~85%. One quick executable check suffices. |
| 10 | G5: Self-Correction Loop Bounding | LOW | WEAKENED | **LOW** | <1% of sessions. 15-minute fix (`max_retry` in FeatureFlags). |

### New Gaps (from External)

| Rank | Gap | Severity | Action |
|------|-----|----------|--------|
| N1 | N-G1: Frozen dataclass mutation bypass | MEDIUM (catastrophic if exploited) | AST scanner for `object.__setattr__` — **include in P5** |
| N2 | N-G2: `__post_init__` silent failure | LOW-MEDIUM | Test that frozen dataclasses don't have mutating `__post_init__` — **include in P5** |
| N3 | N-G4: Dynamic import bypasses static linter | MEDIUM | AST scanner for `importlib.import_module` — **defer, pair with G1** |
| N4 | N-G5: Context consumed by guardrail stack itself | MEDIUM | Skill consolidation — **defer to separate PR** |
| N5 | N-G6: Pre-commit hook bypass via --no-verify | MEDIUM | CI is the real gate — **document as known gap, don't over-engineer** |

---

## §4 External Suggestions Evaluated Against Subtraction-First

Each suggestion is evaluated against three questions from `project-overview.md` §1.2:
1. **Redundancy**: What existing artefact does this make redundant?
2. **Lost capability**: What capability is lost if we omit it?
3. **Precedent**: Is there an open-source agent-stack precedent?

### 4.1 Context Compiler (`scripts/compile_context.py`)

**Proposal**: Deterministic compiler that reads AGENTS.md + SKILL.md → `.fa/session_context.md`, reducing context ~20%.

| Question | Answer |
|----------|--------|
| Redundancy? | Makes manual skill consolidation redundant. Also partially redundant with the existing `knowledge/llms.txt` index (deprecated per ADR-14/15). |
| Lost capability if omitted? | Agents must read full source files every session; context budget degrades as docs grow. |
| Precedent? | No open-source agent stack has a "context compiler." New but derived from existing compilation patterns. |

**Verdict**: ❌ **DEFER.** The 20% context reduction is estimated, not measured. Adding a compilation step adds surface (new script, new output file, new test, new CI step) without proven benefit. The simpler approach is **manual skill consolidation** (prune SKILL.md from 543 to ~350 lines by removing overlap with AGENTS.md). This achieves the same reduction with zero new surface. Revisit if context consumption is measured to exceed 15% of effective capacity after consolidation.

### 4.2 Behavioral Contract Compiler (`scripts/compile_behavior_contract.py`)

**Proposal**: Extract assertions from C1 tests → `.fa/behavior_contract.md`.

| Question | Answer |
|----------|--------|
| Redundancy? | Partially redundant with `check_producer_consumer_contract.py` (already validates producer-consumer wiring). Also partially redundant with `mutmut` mutation testing (already validates test effectiveness). |
| Lost capability if omitted? | No explicit contract document listing all behavioral assertions. Kill-check failure detection remains manual. |
| Precedent? | No direct precedent. ADR-11-I9 (live-path DoD) is the closest existing mechanism. |

**Verdict**: ❌ **DEFER.** The existing C1 test suite + `check_producer_consumer_contract.py` + `mutmut` already provides kill-check validation. Adding a compilation step that extracts assertions into a markdown document is elegant but adds surface without closing a gap that isn't already covered. The "kill-check failure detection" capability is already provided by the C1 tests themselves (if you remove a production call site, the C1 test fails). Revisit if the number of C1 tests exceeds 100 and manual review becomes impractical.

### 4.3 Frozen Integrity Guard (`scripts/frozen_guard.py`)

**Proposal**: AST scanner for `object.__setattr__` usage + verify `frozen=True` on all `@dataclass`.

| Question | Answer |
|----------|--------|
| Redundancy? | Not redundant — no existing check scans for mutation bypass. |
| Lost capability if omitted? | `object.__setattr__` bypass goes undetected. Rare (<0.1%) but catastrophic for TCB integrity. |
| Precedent? | Python-specific defense. No direct precedent in agent stacks, but AST scanning is a proven pattern (used by `authoring_rules/exports.py`, `ruff`, `vulture`). |

**Verdict**: ✅ **ACCEPT — include in Phase 5.** This is a low-effort (2-3 hours), high-value defense that uses existing AST-scanning patterns. The script itself is ~80 lines, produces a deterministic report, and adds zero runtime overhead. It closes N-G1 and N-G2 (frozen integrity + `__post_init__` check) in one mechanism. It fits the "less surface, more robust" principle — one deterministic scanner prevents an entire class of TCB integrity failures.

### 4.4 Dependency Contract TCB (`.fa/dependency_contract.toml`)

**Proposal**: Frozen TOML file defining allowed packages/versions/registries, compared against `pyproject.toml` on each check.

| Question | Answer |
|----------|--------|
| Redundancy? | Partially redundant with `check_protected_paths.py` (already flags dependency manifest edits). Also partially redundant with `pip-audit` (scans for known CVEs). |
| Lost capability if omitted? | No way to distinguish "known-good dependency" from "hallucinated-but-real package." Advisory-only flagging for supply chain. |
| Precedent? | `.fa/session.toml` frozen manifest pattern already exists in `authoring_tcb.py`. `pyproject.toml` + `uv.lock` is the standard Python dependency contract. |

**Verdict**: ⚠️ **SIMPLIFY.** The full TCB pattern (frozen TOML + comparison logic + fail-closed parsing) is over-engineered for the current threat model. The simpler approach achieves 90% of the benefit:

1. **Make `check_protected_paths.py` blocking for dependency edits** (change default exit code for `_DEPENDENCY_PATHS` from 0 to 1). This is a 2-line change.
2. **Add `--allow-dep-edit` flag** for legitimate dependency updates (requires human intent).
3. **Add a comment in `check_protected_paths.py`** noting that the `--allow-dep-edit` flag should be used with explicit review of each new/changed package.

This achieves the supply-chain blocking without adding a new frozen file, new parsing logic, or new CI step. Revisit the full TCB pattern if hallucinated-package attacks are observed in practice.

---

## §5 Updated Phase Implementation Plan (P1–P5)

Based on the reconciled analysis, user decisions, and subtraction-first evaluation.

**Scope cap**: Stop at P5, defer P6 (discriminated union / deep failure-mode closure) per user decision.

### Phase 1: Logic Error Fixes (F-4, F-3) — No architectural changes

Unchanged from the original plan. Pure bug fixes.

| Step | Change | Files | Est. Lines | Risk |
|------|--------|-------|-----------|------|
| 1.1 | Fix `or 150000` swallowing zero | `coder_loop.py` | ~3 | LOW |
| 1.2 | Type `compactor_chain: ProviderChain \| None` + fix dead fallback | `compactor.py` | ~10 | LOW |
| 1.3 | Verify + commit | — | — | — |

**Verification**: `pytest`, `check_producer_consumer_contract.py`, `check_no_mocked_dataclasses.py` all pass.

### Phase 2: LogKind Type + Console-Mirror Subset + Contract Check + G9 Metric Collector

| Step | Change | Files | Est. Lines | Risk |
|------|--------|-------|-----------|------|
| 2.1 | Create `LogKind = Literal[...]` in `output.py` | `output.py` | ~40 | MEDIUM |
| 2.2 | Define `CONSOLE_MIRROR_KINDS` frozenset | `output.py` | ~20 | LOW |
| 2.3 | Type `EventLog.append(kind: LogKind)` | `state.py` | ~3 | MEDIUM |
| 2.4 | Create `scripts/check_log_kind_contract.py` | new file | ~120 | LOW |
| 2.5 | **G9: Extend session_meta with guardrail metrics** (real-time during `fa run`) | `coder_loop.py`, `stats.py` | ~40 | LOW |
| 2.6 | Update SKILL.md I-TW-17 invariant | `SKILL.md` | ~5 | LOW |
| 2.7 | Verify + commit | — | — | — |

**G9 Real-Time Metric Collection** (Step 2.5):
- **Extend existing infrastructure** — no new files or tools
- At session end in `coder_loop.py`, write guardrail metrics to `SessionDatabase.session_meta`:
  - `guardrail_rule_fires`: dict of `{rule_code: count}` for all authoring rule violations
  - `guardrail_overrides`: count of times humans overrode HARD-BLOCK (from CI annotations)
  - `budget_threshold_breaches`: count of `context_budget_warn` + `context_budget_hard_stop` events
  - `kind_counts`: dict of `{log_kind: count}` for all log kinds emitted during session
- Add `fa stats --guardrail-metrics` flag to `src/fa/stats.py` that reads `session_meta` across runs
- Uses existing `SessionDatabase.set_meta()` and `get_meta()` methods
- Per the user's reduction check: extends existing DB + telemetry infrastructure rather than building a new collector

### Phase 3: Type All 9 `Any | None` Fields on SessionState (F-5)

Unchanged from the original plan. Type safety pass.

| Step | Change | Files | Est. Lines | Risk |
|------|--------|-------|-----------|------|
| 3.1 | Add TYPE_CHECKING imports | `state.py` | ~12 | MEDIUM |
| 3.2 | Replace 9 `Any \| None` fields with proper types | `state.py` | ~9 | MEDIUM |
| 3.3 | Update consumer sites (Pylance-guided) | multiple | ~30 | MEDIUM |
| 3.4 | Update `make_session_state()` test factory | `session_wiring.py` | ~10 | LOW |
| 3.5 | Verify + commit | — | — | — |

### Phase 4: Fail-Closed/Open + Compaction SSoT + Remove getattr + G12 Blocking + G13 Behavioral Assertions (LOGIC-10)

Combined with G12 (make supply-chain blocking) and G13 (add behavioral assertions to loop_guard tests).

| Step | Change | Files | Est. Lines | Risk |
|------|--------|-------|-----------|------|
| 4.1 | Define `FAIL_CLOSED_FLAGS` / `FAIL_OPEN_FLAGS` | `feature_flags.py` | ~25 | LOW |
| 4.2 | Replace 12 `getattr(flags, "field", default)` with direct access | `coder_loop.py`, `loop.py`, `state.py`, etc. | ~40 | MEDIUM |
| 4.3 | Fail-closed pattern for safety-critical flags | `coder_loop.py`, `spawn_subagent.py` | ~10 | LOW |
| 4.4 | F-10: Remove `context_compaction_enabled` flag gate, derive from threshold | `coder_loop.py` | ~5 | MEDIUM |
| 4.5 | **NEW: G12 full TCB — Create `.fa/dependency_contract.toml` + `check_dependency_contract.py`** | new files + `check_protected_paths.py` | ~120 | MEDIUM |
| 4.6 | **NEW: G13 hybrid — Add behavioral assertions to loop_guard tests + extend runtime safety checks** | `test_inner_loop_loop_guard.py`, `coder_loop.py` | ~40 | MEDIUM |
| 4.7 | **NEW: LOGIC-10 actionable console guidance for abnormal_stop** | `coder_loop.py` | ~15 | LOW |
| 4.8 | Verify + commit | — | — | — |

**G12 Implementation** (Step 4.5 — Full TCB pattern):
- Create `.fa/dependency_contract.toml` with frozen contract:
  - `[kernel]` table (version = "0.1")
  - `[packages.core]` — required dependencies with exact versions
  - `[packages.dev]` — optional development dependencies
  - `[packages.security_critical]` — packages that must pass `pip-audit`
  - `[registries]` — allowed package sources
  - Unknown keys → fail-closed (same as `authoring_tcb.py` manifest)
- Create `scripts/check_dependency_contract.py` (~80 lines):
  - Parse contract via `tomllib`, compare against `pyproject.toml`
  - Unknown packages → `ADVISORY`; missing security-critical → `HARD-BLOCK`
  - Reuse `RuleResult` + `Severity` from `authoring_tcb.py` for output format
- Update `check_protected_paths.py`:
  - Add `.fa/dependency_contract.toml` to `_TCB_PATHS`
  - Make dependency manifest edits blocking by default (exit 1 for `_DEPENDENCY_PATHS`)
  - Add `--advisory-deps` flag for legitimate updates
- Wire into CI: `justfile` target `dependency-check`
- Seed initial contract from current `pyproject.toml` dependencies

**G13 Implementation** (Step 4.6 — Hybrid approach):
- **CI-only behavioral assertions** in `test_inner_loop_loop_guard.py`:
  - "If IntentGuard denies, no provider calls made after denial"
  - "If context_budget_hard_stop fires, no tool calls within 50ms"
  - "If loop_guard triggers, exactly one loop_warn event emitted"
- **Runtime safety-critical extensions** (extend existing, not new framework):
  - `ContextBudget` hard-stop: add explicit `loop_warn` event with actionable message
  - `max_retry` check: add thin guard in inner loop (Phase 5 Step 5.11)
  - Compaction circuit breaker: already handled in Phase 5 Step 5.12
- **NO new runtime assertion framework** — the existing `IntentGuard` + `ContextBudget` + `LoopGuard` ARE the runtime contracts

### Phase 5: Coverage Gaps + Documentation + Small Fixes + G2 TRACE + G6 Non-RuleResult + Frozen Guard

The largest phase — closes remaining observability gaps, adds the TRACE mechanism, improves non-RuleResult error messages, and adds the frozen integrity guard.

| Step | Change | Files | Est. Lines | Risk |
|------|--------|-------|-----------|------|
| 5.1 | F-7: Add missing log kind parsers to `fa stats` | `stats.py` | ~150 | LOW-MEDIUM |
| 5.2 | F-8: Update SKILL.md §5 + add I-TW-20 invariant | `SKILL.md` | ~10 | LOW |
| 5.3 | F-9: Document `output_bus` None window | `state.py` | ~8 | LOW |
| 5.4 | NEW-8: Move `import sqlite3` to top of state.py | `state.py` | ~2 | LOW |
| 5.5 | LOGIC-16: Add `EventLog.count()` and `EventLog.tail()` | `state.py`, `session_db.py` | ~40 | LOW-MEDIUM |
| 5.6 | LOGIC-10: Already included in Phase 4 Step 4.7 | — | — | — |
| 5.7 | **G2: Create `.fa/corrections.jsonl` + `scripts/compile_corrections.py`** (TRACE mechanism) | new files | ~120 | MEDIUM |
| 5.8 | **G6: Error message audit for non-RuleResult code paths** | `providers/*.py`, `cli.py`, `coder_loop.py` | ~40 | LOW |
| 5.9 | **N-G1/N-G2: Frozen Integrity Guard** (`scripts/frozen_guard.py`) | new file | ~80 | LOW |
| 5.10 | **G3 quick win: ADR-11-I1 stdlib-only executable check** | new file or add to `check_dead_flags.py` | ~20 | LOW |
| 5.11 | **G5 quick win: Add `max_retry` to FeatureFlags** | `feature_flags.py`, `coder_loop.py` | ~5 | LOW |
| 5.12 | **G11: Add compaction_end circuit-breaker visibility** (user chose "use compaction_end") | `coder_loop.py` | ~10 | LOW |
| 5.13 | Verify + commit | — | — | — |

**G2 TRACE Implementation** (Step 5.7):
- `.fa/corrections.jsonl` format: `{"ts": "...", "code": "FA-AUTHORING-...", "remediation": "...", "path": "...", "corrected_by": "human"}`
- `scripts/compile_corrections.py` reads the JSONL, groups by code, produces:
  - Summary of most common correction patterns
  - Candidate Level-1 rule specifications (for human review)
  - Updates to `catch-corpus/` fixtures (requires human approval)
- **Human-mediated only**: The script produces a report, not a commit. A human reviews and decides what to adopt.
- The script is NOT a new guardrail — it's a mining tool that feeds the existing `authoring_tcb` pipeline.

**G6 Error Message Audit** (Step 5.8):
- Scan `src/fa/providers/*.py`, `src/fa/cli.py`, `src/fa/inner_loop/coder_loop.py` for:
  - `raise ValueError(...)` without "expected X, got Y" format
  - `raise RuntimeError(...)` without remediation hint
  - `logger.error(...)` without structured context
  - `sys.exit(1)` without error message
- For each hit, rewrite to include (1) what, (2) why, (3) how to fix
- Per user's intent: "make logging and error messages explicit where possible"

**Frozen Integrity Guard** (Step 5.9):
- AST scan for `object.__setattr__` usage in `src/fa/`
- Verify `frozen=True` on all `@dataclass` that have TCB relevance
- Verify no `__post_init__` on frozen dataclasses (N-G2)
- Produces `.fa/frozen_integrity_report.md`
- Wired into `just check`

**G3 Quick Win** (Step 5.10):
- One script (or extension to `check_dead_flags.py`) that:
  - Reads `authoring_tcb.py` imports
  - Verifies all imports are stdlib (`sys.stdlib_module_names` in Python 3.10+)
  - Exits 1 if any third-party import found
- Covers ADR-11-I1 (stdlib-only kernel) with an executable check
- ~20 lines, no new dependencies

---

## §6 Summary: What Ships in Each Phase

| Phase | Key Deliverables | Gaps Closed | Est. Lines | Est. Tests |
|-------|-----------------|-------------|-----------|-----------|
| P1 | Bug fixes (or 150000, compactor_chain typing) | F-4, F-3 | ~15 | 3-5 |
| P2 | LogKind Literal, CONSOLE_MIRROR_KINDS, log kind contract check, G9 session_meta metrics | F-2, F-1, G9 | ~230 | 20-25 |
| P3 | Type 9 Any\|None fields on SessionState | F-5 | ~60 | 5-8 |
| P4 | Fail-closed/open flags, compaction SSoT, getattr removal, G12 full TCB dependency contract, G13 hybrid behavioral assertions, LOGIC-10 | F-6, F-10, G12, G13 | ~250 | 18-25 |
| P5 | Stats parsers, TRACE mechanism, error audit, frozen guard, G3 check, G5 max_retry, G11 visibility | F-7, F-8, F-9, G2, G6, G3, G5, G11, N-G1, N-G2 | ~485 | 30-40 |
| **Total** | | **All P1-P5 gaps** | **~1040** | **~76-103** |

**P6 (Deep Failure-Mode Closure)** is deferred per user decision. When resumed, it would add:
- Discriminated union events (`src/fa/events.py`)
- Property-typed SessionState
- Typed stats parsing
- Estimated ~400 lines + 25-35 tests

---

## §7 Architectural Decision Points for User Review

Before execution begins, the following decisions need confirmation:

### Decision 1: G12 Supply-Chain Blocking Strategy — RESOLVED (User chose Option B)

**User chose**: Full TCB pattern — `.fa/dependency_contract.toml` frozen contract + comparison logic.

**Implementation plan** (updated for full TCB):
1. **Create `.fa/dependency_contract.toml`** — frozen TOML with:
   - `[kernel]` table (version, same pattern as `session.toml`)
   - `[packages.core]` — required dependencies with exact versions
   - `[packages.dev]` — optional development dependencies
   - `[packages.security_critical]` — packages that must pass `pip-audit`
   - `[registries]` — allowed package sources (`pypi`, `github`, `local`)
   - Unknown keys → fail-closed (same pattern as `authoring_tcb.py` manifest parsing)
2. **Add `scripts/check_dependency_contract.py`** (~80 lines):
   - Parse `.fa/dependency_contract.toml` via `tomllib` (stdlib-only, like TCB)
   - Read `pyproject.toml` dependencies via `tomllib`
   - Compare: packages in pyproject but not in contract → `ADVISORY` with `expires_on`
   - Packages in `security_critical` but not in contract → `HARD-BLOCK` (exit 1)
   - Packages not in allowed registries → `HARD-BLOCK`
   - Output: same JSON/text format as `authoring_tcb.py` (reuse `KernelReport` pattern)
3. **Update `check_protected_paths.py`**:
   - Add `.fa/dependency_contract.toml` to `_TCB_PATHS`
   - Make dependency manifest edits blocking by default (exit 1 for `_DEPENDENCY_PATHS`)
   - Add `--advisory-deps` flag to restore advisory behavior for legitimate updates
4. **Wire into CI**: Add `justfile` target `dependency-check` → runs `check_dependency_contract.py`
5. **Seed the contract**: Generate initial `.fa/dependency_contract.toml` from current `pyproject.toml` dependencies

### Decision 2: G9 Metric Collector — RESOLVED (User chose Option B + reduction check)

**User chose**: Real-time instrumented collection during `fa run`.

**Reduction check result**: FA ALREADY has real-time metric collection infrastructure:

| Existing Component | What It Collects | Storage |
|---|---|---|
| `SessionDatabase.event_log` table | All 30 log kinds with `kind`, `run_id`, timestamps | Per-run SQLite, indexed by `kind` and `run_id` |
| `TelemetryLogger` | Per-tool-call: `prompt_tokens`, `completion_tokens`, `cost_usd`, `model_id`, `tool_name`, `test_result`, `cache_hit`, `latency_ms` | `telemetry.jsonl` |
| `Blackboard` | Structured state with conflict detection, read/write sets | Same per-run SQLite |
| `session_meta` table | Arbitrary key-value metadata per session | Same per-run SQLite |

**What's missing** (not a new tool — an extension):
1. **Guardrail-specific metrics in `session_meta`**: At session end, write `guardrail_rule_fires`, `guardrail_overrides`, `budget_threshold_breaches` to `session_meta`.
2. **Cross-run aggregation**: A `fa stats --guardrail-metrics` CLI command that reads `session_meta` across runs.
3. **Rule violation counts per kind**: Extend `EventLog.append()` to increment a `kind_counts` dict in session state, flushed to `session_meta` at session end.

**Implementation**: Extend existing `SessionDatabase.set_meta()` + `TelemetryLogger.log()` patterns. No new files needed — add 2-3 `set_meta()` calls in `coder_loop.py`'s session-end path. Add a `--guardrail-metrics` flag to the existing `fa stats` command (in `src/fa/stats.py`).

### Decision 3: G13 Behavioral Contract Enforcement — RESOLVED (Research-based)

**Research findings from production systems**:

| System | Enforcement Model | When It Runs | Reversibility |
|--------|------------------|-------------|---------------|
| **Cursor BugBot** | Review-time only (PR-level) | After PR opened, before merge | Diff can be rejected |
| **Claude Code hooks** | Runtime (PreToolUse/PostToolUse) | During agent loop, before/after tool call | PreToolUse can block; PostToolUse cannot undo |
| **Kastra** | Runtime policy interception | Before tool execution, between agent and outside system | Blocks dangerous actions before they happen |
| **Codex CLI hooks** | Runtime (6 events, same model as Claude Code) | During agent loop | Same exit-2 blocking pattern |

**Key insight from Kastra/Cursor research**:
- Runtime enforcement is justified when the agent can **change the outside world** (database writes, deployments, API calls that cost money or mutate state)
- CI-only enforcement is sufficient when the agent **only edits files in a sandbox** and all actions are reversible via git

**For FA's agent loop specifically**:
- FA's agent loop runs in a sandboxed filesystem (git-controlled, reversible)
- The **irreversible** actions are: API calls (costs money, can't undo), infinite loops (time waste), security boundary violations
- Budget enforcement is already partially runtime (`ContextBudget` hard-stop)
- Hook enforcement already blocks dangerous tool calls at runtime (`IntentGuard`)

**Recommended approach: Hybrid — CI-only for behavioral contracts + runtime for safety-critical checks**

1. **CI-only behavioral assertions** in `test_inner_loop_loop_guard.py`:
   - "If IntentGuard denies, no provider calls made after denial"
   - "If context_budget_hard_stop fires, no tool calls within 50ms"
   - "If loop_guard triggers, exactly one loop_warn event emitted"
   - These validate the CONTRACT in CI without adding runtime surface.

2. **Runtime safety-critical checks** (already partially exist, extend in Phase 4):
   - `ContextBudget` hard-stop → already runtime, extend with explicit log
   - `max_retry` check in inner loop → add as thin runtime guard
   - Compaction circuit breaker → user already chose "use compaction_end" for visibility

3. **NO new runtime assertion framework** — the existing `IntentGuard` + `ContextBudget` + `LoopGuard` are the runtime contracts. Extend them with explicit logging (Phase 5 G11/G6), don't add a new layer.

This aligns with the user's "less surface, more simple" principle and the Kastra lesson: "small scoped rules plus hard tool boundaries are easier to review."

### Decision 4: G6 Error Message Audit Scope — RESOLVED (User chose Option A)

**User chose**: Focused audit on providers + CLI + inner_loop (~30 sites, 2-3 hours).

**Implementation**: Scan these modules for unstructured error messages:
- `src/fa/providers/*.py` — provider adapter exceptions
- `src/fa/cli.py` — bare `sys.exit(1)` calls
- `src/fa/inner_loop/coder_loop.py` — generic `RuntimeError`
- `src/fa/inner_loop/state.py` — `getattr` fallbacks that swallow errors silently

Rewrite each to include: (1) what happened, (2) why, (3) how to fix.

### Decision 5: Phase 2 G9 Metric Collector — RESOLVED (Include in Phase 2)

G9 is foundational for validating G13 contracts and measuring G2 TRACE effectiveness. Per the reduction check, G9 extends existing infrastructure rather than adding a new tool.

**Implementation**: Extend `SessionDatabase.set_meta()` with guardrail metrics at session end. Add `--guardrail-metrics` flag to `fa stats`. No new files needed.

---

## §8 Interaction Failure Mitigations (Cross-Reference)

| Interaction | Risk | Mitigation | Phase |
|------------|------|-----------|-------|
| I-1: G1 + N-G4 (import-linter + dynamic import bypass) | Bypassable layer enforcement | Defer G1; add AST dynamic-import scanner as authoring rule when codebase grows | Deferred |
| I-2: G6 + G2 (messages + TRACE) | Improving messages without TRACE doesn't close failure mode | G2 ships in P5; G6 ships in P5 but AFTER G2 | P5 |
| I-3: G12 + G3 (advisory + ADR) | False security from advisory-only controls | G12 made blocking in P4; G3 gets one executable check in P5 | P4, P5 |
| I-4: G13 + G9 (contracts + measurement) | Contracts in a vacuum without data | G9 ships in P2; G13 ships in P4 | P2, P4 |
| I-5: G11 + AGENTS.md (procedural + no enforcement) | Context rot with no automatic detection | G11 compaction_end visibility in P5; ADR-17 enforcement deferred | P5 |

---

## §9 External Verification Self-Assessment Score: Adjusted

The external rated itself 6/10. After direct code verification:

| External Claim | Verified Status | Impact on Confidence |
|---------------|----------------|---------------------|
| "7 EventTypes" | ❌ FALSIFIED (14) | Major — core factual error |
| "check_producer_consumer_contract.py doesn't exist" | ❌ FALSIFIED (exists, 206 lines) | Major — core factual error |
| "12 FeatureFlags fields" | ⚠️ Minor error (13) | Minor |
| "RuleResult already has structured messages" | ✅ CONFIRMED | Strengthens |
| "check_protected_paths.py exits 0 for deps" | ✅ CONFIRMED | Strengthens |
| "57.5% violation reduction unverifiable" | ✅ CONFIRMED | Strengthens |
| "Auto-TRACE violates AGENTS.md #1" | ✅ CONFIRMED | Strengthens |
| 6 new gaps (N-G1 through N-G6) | ✅ Largely confirmed | Strengthens |
| 5 interaction failures | ✅ Confirmed | Strengthens |

**Adjusted confidence**: **5/10** (down from 6/10 due to two core factual errors that invalidated significant portions of the analysis). The structural analysis, interaction detection, and new gap identification remain valuable. The outside-the-box suggestions were well-reasoned even though some were over-engineered. The external's greatest contribution is the **interaction failure analysis** (§3) and the **subtraction-first evaluation** (§4), both of which held up under verification.

---

## §10 Key Evidence References (Verified Against Actual Code)

| Claim | Source | Verification |
|-------|--------|-------------|
| 14 EventType literals | `src/fa/output.py` lines 42-56 | ✅ Read directly; `check_producer_consumer_contract.py` confirms |
| `check_producer_consumer_contract.py` exists | `scripts/` directory listing | ✅ File exists, 206 lines, exits 0 |
| FeatureFlags has 13 fields | `src/fa/feature_flags.py` lines 27-39 | ✅ Read directly |
| `check_protected_paths.py` exits 0 for deps | `scripts/check_protected_paths.py` line 159 | ✅ Read directly |
| RuleResult has `remediation` field | `src/fa/authoring_tcb.py` lines 99-147 | ✅ Read directly |
| `authoring_tcb.py` is stdlib-only | `src/fa/authoring_tcb.py` imports section | ✅ Only stdlib imports |
| `Severity.__bool__` override exists | `src/fa/authoring_tcb.py` lines 71-81 | ✅ Returns `True` for all members |
| BugBot 80% resolution rate | `aicodereview.cc` (2026-05-03) | ✅ External verified |
| CSA 2026-05: ~20% hallucinated packages | CSA research note | ✅ External verified |
| TRACE paper: arXiv:2606.13174 | Peer-reviewed | ✅ External verified |
