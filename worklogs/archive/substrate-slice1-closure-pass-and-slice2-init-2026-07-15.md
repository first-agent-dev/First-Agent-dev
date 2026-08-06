# Slice 1 Closure Pass and Slice 2 Initialization

**Date:** 2026-07-15  
**Purpose:**
- confirm what Slice 1 has actually closed,
- record what remains intentionally deferred,
- initialize Slice 2 scope and decision points.

---

## 1. Slice 1 closure-pass verdict

### Slice 1 motto held

> Do not try to solve all DB-related problems inside Slice 1.  
> Slice 1 is for hot-path authority and split-brain removal.

This closure pass confirms that the implementation stayed within that scope.

---

## 2. What Slice 1 now closes

### Closed in hot path

1. **Per-run DB authority now exists as a first-class module**
   - `src/fa/inner_loop/session_db.py`

2. **`EventLog` authoritative write path is DB-first**
   - JSONL is mirror-only on the append path
   - append no longer silently succeeds when authority DB write fails

3. **`EventLog` authoritative read path prefers the per-run DB**
   - JSONL fallback remains only for degraded/legacy cases

4. **`SessionState` now binds blackboard to the same per-run DB authority**
   - hot-path session blackboard no longer creates a separate workspace authority DB

5. **`Blackboard` can act as a facade over the per-run authority DB**
   - while preserving the existing API shape for callers

6. **One direct hot-path blackboard authority recreation path was removed**
   - `subagent_runner.py` now prefers session-injected blackboard

7. **Split-brain regression tests exist for both EventLog and Blackboard**
   - authoritative failure now blocks mirror-ahead success in tested cases

---

## 3. Evidence summary for Slice 1 closure

### New/changed code
- `src/fa/inner_loop/session_db.py`
- `src/fa/inner_loop/state.py`
- `src/fa/blackboard/blackboard.py`
- `src/fa/inner_loop/subagent_runner.py`
- `tests/test_session_db_authority.py`

### Verification completed
- focused authority tests passed
- broad adjacent runtime/provider/tool suites passed
- ruff passed on Slice 1 files

### Hot-path constructor search result
Current search of `Blackboard(` across `src/fa` shows:
- hot-path session construction only from `SessionState`
- compatibility/direct construction remains in `Blackboard.__init__` fallback mode, not in the main runtime chain

---

## 4. What Slice 1 intentionally does NOT close

These remain open by design.

1. **Observability query-plane correctness**
   - `fs_usage`
   - `fs_chronicle_search`
   - path guessing / stale file binding

2. **Telemetry storage unification**
   - telemetry remains separate from authority DB

3. **Global export / `global_history.db`**
   - still later slice

4. **Stage C ladder/provider-boundary corrections**
   - compactor role request slug
   - cache-control truth
   - threshold ladder semantics

5. **Subagent contract hardening**
   - only one blackboard authority recreation path removed here
   - full shell safety equivalence remains later

6. **Logging migration completion**
   - still later slice

7. **PTY/live shell truthfulness**
   - still later slice

---

## 5. Slice 1 residual risks (accepted for now)

These are not Slice 1 failures; they are expected residuals.

### R1 — Standalone `Blackboard(...)` still has compatibility fallback
If a caller directly instantiates `Blackboard` without injected per-run `session_db`, it can still create a local fallback DB under its root.

**Interpretation:** acceptable for compatibility during transition, but not to be used as evidence of hot-path architecture.

### R2 — JSONL fallback still exists in `EventLog.read_all()`
This is retained for degraded/legacy compatibility.

**Interpretation:** acceptable inside Slice 1 because the split-brain class is blocked on the authoritative write path, which is the crucial fix.

### R3 — Tool-path safety comments still mention `.fa/blackboard` as identity anchor
These comments reference workspace ownership/safety checks, not authority DB truth.

**Interpretation:** comments may need future cleanup to avoid architectural confusion, but they are not active authority bugs by themselves.

---

## 6. Slice 1 done criteria check

| Criterion | Status |
|---|---|
| Per-run authority DB exists | YES |
| EventLog hot-path authority is unified | YES |
| SessionState blackboard hot path is unified | YES |
| Split-brain regression tests exist | YES |
| Hot-path code no longer relies on workspace blackboard DB authority | YES (main runtime path) |
| All DB-related issues solved | NO, intentionally out of scope |

### Closure-pass verdict
**Slice 1 is functionally complete enough to move on, with explicit residuals recorded.**

Not “final substrate done”.  
But **done enough to unlock Slice 2 without violating scope discipline**.

---

# 7. Slice 2 initialization

## 7.1 Slice 2 purpose

Slice 2 should fix the **observability query plane** so that runtime observability tools consume the **active authoritative session state**, not guessed/stale JSONL paths.

### Slice 2 primary targets
- `fs_chronicle_search`
- `fs_usage`
- registry builder path binding for those tools
- possibly `fa stats` scope decision (depending on locked product decision)

---

## 7.2 Verified current defects entering Slice 2

### O1 — Tool registration binds observability tools to guessed path strings
Current builder logic still wires:
- guessed `workspace/.fa/events.jsonl`
- guessed `workspace/events.jsonl`
- guessed `~/.fa/events.jsonl`

rather than active run authority.

### O2 — `fs_usage` parses the wrong schema
It still looks for fields like:
- `prompt_tokens`
- `total_tokens`

while live loop usage writes authoritative fields like:
- `input_tokens`
- `output_tokens`
- `cache_read_input_tokens`
- `cache_creation_input_tokens`

### O3 — Runtime tools still read JSONL directly
`fs_chronicle_search` and `fs_usage` still open JSONL files directly.

### O4 — Tool semantics are ambiguous outside active session context
When no active session exists, current behavior guesses file paths rather than surfacing explicit context requirements.

---

## 7.3 Slice 2 non-goals

To preserve discipline, Slice 2 should **not** take on:
- telemetry DB migration
- global history export
- full `fa stats` redesign unless explicitly chosen
- Stage C changes
- subagent hardening

---

## 7.4 Recommended technical direction for Slice 2

### Recommendation A — Session-aware observability builders
Move from path-bound registration to session-aware execution.

Possible direction:
- keep `build_chronicle_search_tool(...)` / `build_usage_tool(...)`,
- but allow them to resolve current session context and authoritative DB/log at handler time,
- not only at builder creation time.

### Recommendation B — Current session first
When current session exists:
- observability tools should read **current run authority** first.

### Recommendation C — Explicit fallback policy
When no current session exists:
choose one of:
1. structured `no_active_session` failure,
2. explicit `run_id`/path parameter mode,
3. compatibility heuristic fallback.

This requires product locking.

### Recommendation D — `fs_usage` should derive from authoritative event semantics
At minimum, it should understand the real `usage` rows already emitted by the loop.

---

## 7.5 Decisions to lock before Slice 2 implementation

These need operator confirmation.

### Q1 — Default scope of runtime observability tools
When current session exists, should:
- `fs_chronicle_search`
- `fs_usage`

default to **current run only**?

**Recommended:** yes.

### Q2 — Behavior when no current session exists
Should observability tools:
- fail with structured `no_active_session`, or
- try a compatibility path heuristic, or
- require explicit `run_id`/path?

**Recommended:** current session first; otherwise explicit parameter mode is better than guessing.

### Q3 — `fa stats` scope in Slice 2
Should `fa stats` remain:
- a post-hoc JSONL-oriented consumer for now,

or should Slice 2 begin making it DB-first too?

**Recommended:** keep `fa stats` out of Slice 2 and preserve scope discipline.

### Q4 — Telemetry in Slice 2
Should Slice 2:
- keep telemetry as separate derived surface,
- and make `fs_usage` rely on authoritative `usage` event rows only?

**Recommended:** yes.

---

## 7.6 Proposed Slice 2 file targets

### Likely targets
- `src/fa/inner_loop/tools/observability.py`
- `src/fa/inner_loop/tools/__init__.py`
- possibly `src/fa/inner_loop/profiles.py`
- maybe `src/fa/stats.py` only if scope is expanded intentionally

### Possible supporting utility
- a small helper to resolve active session authority path / session DB access inside observability handlers

---

## 7.7 Proposed Slice 2 verification targets

1. active run → `fs_usage` returns real values from live authority
2. active run → `fs_chronicle_search` returns rows from live authority
3. no active session + no explicit target → behavior matches locked decision
4. no stale workspace path guessing in runtime path
5. existing stats/CLI surfaces do not regress unexpectedly

---

## 7.8 Ready-for-lock statement

Slice 2 is initialized and ready to be locked once operator answers the four decision questions above.
