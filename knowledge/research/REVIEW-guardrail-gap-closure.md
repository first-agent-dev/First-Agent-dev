# Production-Readiness Review: PLAN-guardrail-gap-closure.md

**Reviewer:** Based on source code verification against `main` branch
**Date:** 2026-07-20
**Verdict:** NOT READY — 4 blocking issues, 5 significant gaps, 3 correct-by-design items that need re-scoping

---

## BLOCKING ISSUES (must fix before execution)

### B1. G1 fix is wrong — `context_limit=0` should be rejected, not silently accepted

**Plan says (S1):** Replace `getattr(...) or 150000` with direct `provider_chain.config.context_limit`.

**What the code actually does today:**

```python
# coder_loop.py:409
context_limit = getattr(provider_chain.config, "context_limit", 150000) or 150000
```

**And ChainConfig already validates:**

```python
# chain.py:64-65
if config.context_limit <= 0:
    raise ConfigurationError(f"role {config.role!r}: context_limit must be a positive integer")
```

**The real bug:** The `or 150000` fallback was a belt-and-suspenders pattern that accidentally converts `0` → `150000`. But `0` should NEVER reach this line because `ChainConfig.validate()` rejects it upstream. The `or` is dead code *for valid configs*, but it masks a deeper issue: what if `context_limit` comes from a source that skips validation?

**Correct fix:** Not just remove the `or` — add an explicit floor:

```python
MIN_CONTEXT_LIMIT = 32_000  # Below this, context budget is meaningless

context_limit = provider_chain.config.context_limit
if context_limit < MIN_CONTEXT_LIMIT:
    # Log and clamp, don't crash — the session can still run
    state.log.append(
        actor="runtime",
        kind="context_budget_warn",
        content={"message": f"context_limit={context_limit} below floor {MIN_CONTEXT_LIMIT}, clamped"},
    )
    context_limit = MIN_CONTEXT_LIMIT
```

**Why the plan's fix is dangerous:** Direct access without the floor means a misconfigured `models.yaml` with `context_limit: 100` (typo for 100000) would silently create a broken session. The `or 150000` was wrong because it swallowed 0, but removing it entirely without a floor swallows typos.

**User's context:** They confirmed 150000 is the right default for modern models (250k–1M context, effective working zone ~150k). A floor of 32000 prevents catastrophic misconfiguration while allowing smaller models.

### B2. G1 fix misses the adaptive context story

**User stated:** "по идее модуль должен быть адаптивным и считать по формуле в зависимости от модели — max context берется из ответа по api. не тестировалось, работает ли, но попытка написать такой код была."

**What this means for the plan:** The `context_limit` should eventually come from the API response metadata, not just `models.yaml`. The plan's S1 fix hardcodes a single source of truth (`provider_chain.config.context_limit`) without acknowledging this evolution path.

**Current code has no adaptive mechanism.** The grep for `adaptive`, `max_output_tokens`, `response.*model` in coder_loop.py shows nothing related to dynamic context sizing. This is a missing capability, not a bug.

**Minimum production-ready fix for S1:**
1. Remove the `or 150000` trap
2. Add the MIN_CONTEXT_LIMIT floor
3. Add a TODO/ADR reference for adaptive context sizing from API metadata
4. Do NOT attempt the adaptive mechanism in this plan (it's out of scope — separate spike)

### B3. G5 max_retry — plan assumes it doesn't exist, but transport_retries=2 already exists

**Plan says (S22):** "Add `max_retry: int = 5` to FeatureFlags" — implies no retry mechanism exists.

**What actually exists:**

```python
# chain.py:55
DEFAULT_TRANSPORT_RETRIES = 2

# chain.py:94
transport_retries: int = DEFAULT_TRANSPORT_RETRIES

# transport.py:101
max_attempts = 1 + max(transport_retries, 0)  # = 3 attempts (1 initial + 2 retries)
```

**The user was right:** "насколько я помню, стоит 2" — `DEFAULT_TRANSPORT_RETRIES = 2` confirms this.

**The problem:** The plan conflates two different retry concepts:
1. **Transport-level retries** (already exists: `transport_retries=2`) — retries network failures at the HTTP level within a single provider
2. **Chain-level retries** (the plan's `max_retry`) — retries across the provider chain when ALL providers fail

These are different! Transport retries handle `ConnectionError` / `TimeoutError`. Chain-level retries handle `ProviderChainExhaustedError` (all entries tried and failed).

**Current behavior when all providers fail:** The coder_loop catches `ProviderChainExhaustedError` and exits with `stop_reason="chain_exhausted"` — no retry at the session level. This is correct for transport errors but wrong for transient API errors (429 rate limiting, 503 service unavailable).

**Correct fix for S22:**
1. Rename from `max_retry` to `max_chain_retries` to avoid confusion with `transport_retries`
2. Document the relationship: `max_chain_retries` controls how many times the entire provider chain is retried before giving up
3. Default should be `0` (fail-fast, current behavior), not `5` (aggressive retry) — user can opt into retries
4. Add a guard that counts `ProviderChainExhaustedError` occurrences in the session loop

### B4. G9 metrics — plan doesn't verify that session_db is wired at session end

**Plan says (S9):** "Add set_meta calls at session end" with `if state.session_db is not None:`

**What the code actually does:** The session-end path in coder_loop.py uses `finish()` helper which returns a `SessionOutcome`. The `session_db` is set on `state` earlier but there's no guarantee it's still connected when the session ends (connection could have been closed, SQLite lock, etc.).

**Also:** The plan doesn't check that `state.log.read_all()` returns the full event log at session end. If the log is truncated (memory pressure, compaction), the metrics would be wrong.

**Correct fix:**
1. Verify `state.session_db` is writable before set_meta (try/except with logging)
2. Count events incrementally during the session (not re-read at end) — store in a dict on state
3. Write metrics in the `finish()` helper, not in the session-end log.append block

---

## SIGNIFICANT GAPS (should fix before execution, not blockers)

### S1. Plan doesn't account for ChainConfig validation that already rejects context_limit ≤ 0

The plan treats the `or 150000` as if it's the only defense against bad context_limit values. But `chain.py:64-65` already has:

```python
if config.context_limit <= 0:
    raise ConfigurationError(...)
```

This means the `or 150000` is unreachable for validated configs. The real fix should be:
1. Trust ChainConfig validation (it's already there)
2. Add MIN_CONTEXT_LIMIT floor as defense-in-depth
3. The `getattr` fallback can be removed since ChainConfig always has the field

### S2. Plan doesn't reference the existing `knowledge/trace/` directory

The CLI already references `knowledge/trace/codebase_map.json` and `knowledge/trace/gotchas.md`:

```python
# cli.py:838-839
codebase_map_path = (workspace / "knowledge" / "trace" / "codebase_map.json",)
gotchas_path = (workspace / "knowledge" / "trace" / "gotchas.md",)
```

The plan proposes `.fa/corrections.jsonl` for TRACE but doesn't acknowledge the existing `knowledge/trace/` infrastructure. This could be a conflict or an opportunity for consolidation.

**Recommendation:** Use `.fa/corrections.jsonl` as planned (it's in the TCB-protected `.fa/` directory), but add a cross-reference from `knowledge/trace/gotchas.md` to the corrections log, or vice versa.

### S3. Plan's LogKind has 30 members but doesn't verify against actual code

The plan lists 30 LogKind values (S4) but the count came from a grep for `kind="` string literals in `src/fa/`. This grep may miss:
- Kinds constructed dynamically (`kind=f"{prefix}_warn"`)
- Kinds in YAML/config files
- Kinds in test fixtures that don't exist in production code

**Recommendation:** Before implementing S4, run the contract check script to verify the exact set. The plan should acknowledge that the 30-member list is a preflight estimate, not a verified enumeration.

### S4. Plan's FAIL_CLOSED_FLAGS puts subagent_spawning_enabled in wrong category

```python
FAIL_CLOSED_FLAGS: frozenset[str] = frozenset(
    {
        "context_budget_enabled",  # ✓ safety-critical
        "context_compaction_enabled",  # ✓ safety-critical
        "subagent_spawning_enabled",  # ✗ WRONG — this is a convenience feature
    }
)
```

**Why it's wrong:** If `feature_flags is None` and `subagent_spawning_enabled` defaults to `True` (fail-closed), that means subagents are spawned when the system can't read its own configuration. This is DANGEROUS — unconfigured subagents could spawn uncontrollably.

**Correct categorization:** `subagent_spawning_enabled` should be FAIL-OPEN (default = False when flags missing). If we can't read the flags, we should NOT spawn subagents.

### S5. Plan doesn't handle the `getattr` sites in the compactor correctly

The plan says (S2) to replace the double-getattr, but there's also the `getattr(state.feature_flags, ...)` at `coder_loop.py:610-661` that the plan addresses in S13. However, S2 and S13 are in different phases with S2 in Phase 1 and S13 in Phase 4. Between these phases, some getattr sites will remain. This is fine for sequential execution but could cause confusion if phases are partially applied.

---

## CORRECT-BY-DESIGN (acknowledged but need re-scoping for clarity)

### C1. `context_compaction_enabled` is redundant but removing it is a breaking change

The plan marks it as deprecated in S14. But FeatureFlags is a frozen dataclass — removing a field would break any code that constructs `FeatureFlags(context_compaction_enabled=True)`. The plan should explicitly state: "deprecate in P4, remove in P6 or later." Don't delete the field, just stop reading it.

### C2. The `or 150000` is actually a symptom of getattr-with-fallback pattern

The plan addresses this in two places (S1 for context_limit, S13 for all 12 getattr sites). The root cause is the same: defensive coding that accidentally created logic traps. The plan should note this as a systematic pattern, not isolated bugs.

### C3. Transport retries vs. chain retries are different mechanisms

The plan's `max_retry: int = 5` in S22 doesn't distinguish between transport retries (already exist at 2) and session-level retries (don't exist). See B3 above.

---

## CORRECTIVE ACTIONS (what to change in the plan before execution)

| ID | Change | Affected Steps | Priority |
|---|---|---|---|
| CA1 | Replace S1 with: direct access + MIN_CONTEXT_LIMIT=32000 floor + warn on clamp | S1 | BLOCKING |
| CA2 | Add TODO/ADR reference for adaptive context from API metadata | S1 (new sub-step) | Significant |
| CA3 | Rename `max_retry` to `max_chain_retries`, default=0 (fail-fast), document relationship to `transport_retries=2` | S22 | BLOCKING |
| CA4 | Move `subagent_spawning_enabled` from FAIL_CLOSED to FAIL_OPEN | S13 | Significant |
| CA5 | Add incremental event counting (dict on state) instead of re-reading log at session end | S9 | Significant |
| CA6 | Add session_db writability check before set_meta | S9 | Significant |
| CA7 | Note that LogKind 30-member list is preflight estimate, verify with contract check before S4 | S4 | Minor |
| CA8 | Cross-reference `.fa/corrections.jsonl` with existing `knowledge/trace/` infrastructure | S20 | Minor |
| CA9 | Explicitly state: don't delete `context_compaction_enabled` field, just stop reading it | S14 | Minor |

---

## SUMMARY

**The plan is solid in structure** (phases, contracts, kill-checks, anti-theater gate) but has 4 blocking issues in the actual code changes it proposes:

1. **G1 fix could introduce new silent failures** — needs a floor, not just direct access
2. **G5 conflates transport retries with chain retries** — the user's memory was right (2 retries exist), but at the wrong level
3. **G9 metrics could silently fail** — session_db may not be writable at session end
4. **Fail-closed categorization has a safety error** — subagent spawning should default to OFF when flags are missing

The user's priorities (G9 metrics, G2 TRACE, G5 retries) align with the plan's Phase 2 (G9), Phase 5 (G2), and Phase 5 (G5). If I were sequencing this for production, I'd reorder to surface these sooner:

**Suggested execution priority:**
1. **G1 fix with floor** (B1) — 15 minutes, prevents the most common misconfiguration
2. **G9 metrics with incremental counting** (B4, S9) — 2-4 hours, gives you data immediately
3. **G2 TRACE** (S20) — 2-4 hours, starts accumulating corrections from day one
4. **G5 chain retries** (B3, S22) — 1-2 hours, correct naming and defaults
5. Then the rest of the plan in order (LogKind → types → flags → guards)
