# Stage B/C Integration Workplan (Finding-Complete, Phase-Gated)

**Date:** 2026-07-14
**Authors:** Senior Systems Engineering Team & LLM Harness Architects
**Goal:** Close the hostile audit NO-GO by wiring dormant Stage B/C modules into the live runtime, with contracts, invariants, and anti-theater verification.

---

## 0. Operating Rules

1.  **Contracts before call sites:** Do not edit `coder_loop.py` until Phase 0 adapter table is complete.
2.  **One authority per concern:** One prompt assembler, one token meter policy, one DB write serialization policy, one history source-of-truth for compaction.
3.  **§9 wins on conflict:** Hybrid DB partitioning, shared workspace, compactor role in models.yaml, and model-aware compaction thresholds.
4.  **Feature-flag new behavior:** First live wiring of compaction must be flag-gated; default preserves current behavior until integration tests pass.
5.  **Every finding has a done definition:** "Module imported" is not done.
6.  **Anti-theater tests required:** Tests must fail if wiring is removed (import/call-graph or request-payload assertions).
7.  **No API fiction:** If a symbol does not exist, add it deliberately in the owning module with tests—or adapt the integration to the real API.

---

## 1. Finding Register (Track to Zero)

| ID | Sev | Summary | Phase | Done When |
|---|---|---|---|---|
| **FIND-001** | P0 | Compactor unwired in `drive_session` | 4–5 | Stage2/3 run from live loop; events recorded |
| **FIND-004** | P0 | `PromptComposer` unwired / manual messages | 3 | Sole request assembly path |
| **FIND-005** | P0 | `ContextBudget` unwired | 1 | Budget check every turn in live loop |
| **FIND-006** | P0 | `PinnedBuffer` unwired | 2 | Pins every provider call + hash verify |
| **FIND-007** | P0 | Test theater (isolated unit only) | 1–5, 9 | Integration tests assert loop behavior |
| **FIND-002** | P1 | `global_history.db` export absent | 7 | Export on session end + tests |
| **FIND-003** | P1 | Multi-breakpoint cache anchors weak/dead | 3 | Named segment breakpoints |
| **FIND-008** | P1 | Parallel tool paths race on DB writes | 6 | Shared write serialization + stress test |
| **FIND-009** | P2 | Missing SQLite indexes | 6 | Indexes added + query plan smoke |
| **FIND-010** | P2 | JSONL dual-write split-brain risk | 6 | Authority policy implemented + tested |
| **FIND-011** | P2 | Incomplete `\r` resolution | 8 | CR cleaner + cases |
| **FIND-012** | P1 | Model-aware / per-role thresholds absent | 5 | §9.4 resolver + tests |
| **residual** | P1 | Compactor role not in models loader (§9.3) | 5 | Parsed + fallback |
| **residual** | P1 | SIGTERM / subagent cleanup (Gap C / D06) | 8 | Cleanup handlers + test |
| **residual** | P2 | `git grep` colon parse fragility | 8 | Robust parse + test |
| **residual** | P1 | Strike / hard-stop session consistency | 1, 5 | Defined behavior + tests |

---

## 2. Phase 0 — Contract Freeze & Architecture Decisions (Blocking)

### 2.1 Inventory
*   **`ContextBudget` (`src/fa/memory/context_budget.py`):**
    *   Constructor: `__init__(self, limit_tokens: int = 150000, configured_threshold: int | None = None)`
    *   Method: `check(self, current_tokens: int) -> dict[str, Any]`
    *   Method: `record_compaction_attempt(self, tokens_before: int, tokens_after: int) -> bool`
*   **`PinnedBuffer` (`src/fa/memory/pinned_buffer.py`):**
    *   Constructor: `__init__(self, workspace_root: Path)`
    *   Method: `refresh(self) -> None`
    *   Method: `extract_pinned_content(self, extra_instructions: str | None = None) -> str`
*   **`ObservationMasker` / `FullLLMCompactor` (`src/fa/inner_loop/compaction/compactor.py`):**
    *   `ObservationMasker.__init__(self, recent_turns_to_keep: int = 4)`
    *   `ObservationMasker.mask_history(self, events: list[TraceEvent], store: Any | None = None) -> list[TraceEvent]`
    *   `FullLLMCompactor.__init__(self, compactor_chain: Any | None = None)`
    *   `FullLLMCompactor.compact(self, history_text: str) -> str`
*   **`PromptComposer` (`src/fa/inner_loop/prompt_composer.py`):**
    *   `build_prompt_parts_v2(base_system, agents_md_map, tool_defs, role_id, ...)` $\rightarrow$ `tuple[PromptParts, str]`
    *   `to_anthropic_request_v2(parts, cache_key)` $\rightarrow$ `dict[str, Any]`
    *   `to_openai_request_v2(parts, cache_key)` $\rightarrow$ `dict[str, Any]`
*   **`drive_session` (`src/fa/inner_loop/coder_loop.py`):**
    *   The core sequential loop driver where messages are hand-assembled and passed to `provider_chain.request()`.
*   **`EventLog` / `SessionState` (`src/fa/inner_loop/state.py`):**
    *   `EventLog` appends to JSONL and `.fa/session.db` (SQLite3). `SessionState` holds active counters.
*   **`Blackboard` (`src/fa/blackboard/blackboard.py`):**
    *   Write/query/detect conflicts inside `.fa/session.db`.
*   **`TelemetryLogger` (`src/fa/telemetry/telemetry.py`):**
    *   Structured logger appending to `telemetry.jsonl`.
*   **`ToolRegistry` / `ToolSpec` (`src/fa/inner_loop/registry.py`):**
    *   Defines schemas, descriptors, and call limits.
*   **`models` config loader (`src/fa/providers/config.py`):**
    *   Parses models config.

### 2.2 Adapter Table

| Need (invariant) | Real Symbol Today | Gap | Action |
|---|---|---|---|
| Turn budget decision | `ContextBudget.check` | Unwired in loop | Wire into `coder_loop.py` turn start |
| Every-turn pins | `PinnedBuffer.extract_pinned_content` | Unwired in loop | Wire into `PromptComposer` flow |
| Stage 2 Masking | `ObservationMasker.mask_history` | Unwired in loop | Wire inside `coder_loop.py` at 80% threshold |
| Stage 3 Compaction | `FullLLMCompactor.compact` | Unwired in loop | Wire inside `coder_loop.py` at 90% threshold |
| Sole prompt assembly | `PromptComposer.build_prompt_parts_v2` | `coder_loop` hand-assembles | Refactor `coder_loop` to use composer |
| DB write serialize | `threading.Lock` on `EventLog`/`Blackboard` | No shared connection locks | Standardize SQLite connection locking |
| Compactor role | `compactor` role in `models.yaml` | Loader lacks role parsing | Extend `src/fa/providers/config.py` |

### 2.3 Decisions Locked (D1–D7)

*   **D1 History authority for compaction:** **B) rebuild from EventLog**. It is the absolute source of truth. Compactors read from SQLite `event_log` table rather than mutating a live messages list directly.
*   **D2 DB topology:** **Single `.fa/session.db`** file in WAL mode for active runs, isolated per run.
*   **D3 JSONL:** **Mirror-only**. SQLite3 is the sole authority for queries and reads; JSONL is written as a passive text mirror for Git diff reviewability.
*   **D4 Token meter:** **chars//4 (with tiktoken injection support)**. Pure, centralized, injectable token counter in `context_budget.py`.
*   **D5 Compaction default flag:** **off until Phase 5 green**. Default to False for safety until all integration tests are fully validated.
*   **D6 Hard-stop behavior:** **graceful session stop + user message**. Write terminal `context_budget_hard_stop` event, flush database, and exit with a non-zero code.
*   **D7 Pin vs summary precedence:** **pins always after/outside summary**. Pinned buffer injected outside compaction summarize text so it can never be overwritten or overridden.

---

## 3. Phase-by-Phase Execution Plan (Verifiable Slices)

### Phase 1 — ContextBudget in the live loop (gates only)
*   **Closes:** `FIND-005` (ContextBudget unwired)
*   **Wiring:** Wire `ContextBudget` check sequentially at the start of each turn in `drive_session()` before making any provider calls.
*   **Tests:** Implement `test_drive_session_budget_warn_event` and `test_drive_session_budget_hard_stop` asserting correct gating boundaries.

### Phase 2 — PinnedBuffer every turn (before compaction)
*   **Closes:** `FIND-006` (PinnedBuffer unwired)
*   **Wiring:** Wire `PinnedBuffer` extraction on every turn, injecting it as a system block inside prompt assembly.
*   **Tests:** Implement `test_pins_present_each_turn_no_compaction` verifying constraint hashes are visible in request payloads.

### Phase 3 — PromptComposer is the only assembly path
*   **Closes:** `FIND-004` (PromptComposer unwired), `FIND-003` (Multi-breakpoint cache anchors)
*   **Wiring:** Refactor `coder_loop.py` to completely pass all messages, tools, and pins through `PromptComposer` to calculate role cache keys. Attach `cache_control` breakpoints at the end of the system prompt, tool definitions, and compaction summary blocks.
*   **Tests:** Implement `test_drive_session_orders_prompt_segments` verifying Anthropic-shaped breakpoint payloads.

### Phase 4 — Stage 2 Observation Masking (schema-safe)
*   **Closes:** `FIND-001` partial (Stage 2 compactor)
*   **Wiring:** Gate under `context_compaction_enabled` flag. At 80% threshold, trigger `ObservationMasker.mask_history` to strip tool output payloads exceeding 200 characters outside the recent 4-turn tail window.
*   **Tests:** Implement `test_stage2_protects_tail_window` asserting that older bulky stdout results are masked while recent ones remain full.

### Phase 5 — Stage 3 + §9.3 + §9.4 + pins interaction
*   **Closes:** `FIND-001` complete, `FIND-012` (threshold logic), §9.3, §9.4
*   **Wiring:** Parse `compactor` role in `models.yaml`. Calculate dynamic thresholds (`min(80% limit, 150000)`). If Stage 2 is insufficient, trigger `FullLLMCompactor.compact` to summarize older conversation under the 4 headers.
*   **Tests:** Implement `test_circuit_breaker_stops_session` verifying compaction terminates if under 10% space is reclaimed consecutively 3 times.

### Phase 6 — SQLite write safety, indexes, JSONL authority
*   **Closes:** `FIND-008` (parallel write races), `FIND-009` (missing indexes), `FIND-010` (JSONL split-brain)
*   **Wiring:** Enforce process-wide synchronized thread locks for SQLite connections. Create indexes over PK/query columns. Implement SQLite authority.
*   **Tests:** Implement `test_parallel_tool_batch_event_writes` stress-testing 5 concurrent writing threads without locks or busy exceptions.

### Phase 7 — Hybrid global history export (§9.1 / FIND-002)
*   **Closes:** `FIND-002` (global history absent)
*   **Wiring:** Write global exporter that appends metadata summary records to `workspace_root / ".fa" / "global_history.db"` on session end.
*   **Tests:** Implement `test_global_history_export_idempotent`.

### Phase 8 — Residuals (PTY, grep, lifecycle)
*   **Closes:** `FIND-011` (PTY carriage returns), Gap C/D06 (worktree leaks), residuals
*   **Wiring:** Complete `resolve_cr(text)` carriage return cleanups and register atexit handlers in `SessionState` to clean up dangling paths.
*   **Tests:** Implement `test_resolve_carriage_returns`.

### Phase 9 — Hostile re-audit & ship gate
*   **Closes:** `FIND-007` (Test theater)
*   **Action:** Re-run the hostile systems auditor suite in the CI pipeline, requiring 100% green before release.
