# PLAN: Guardrail Gap Closure P1–P5              Plan-ID: PLAN-guardrail-gap-closure
Status: READY                                   Depth: P3
Revision: v4   Changed-since-last: Q1–Q5 answers applied
Upstream context: merged-guardrail-action-plan-2026-07-19.md, external-verification-guardrail-gaps-2026-07-19.md, missing-guardrail-dimensions-2026-07-19.md

═══════════════════════════════════════════════════════════════════════
## Preflight log (§2)
═══════════════════════════════════════════════════════════════════════

roots checked:
  - `src/fa/inner_loop/coder_loop.py::drive_session` (L286) → primary session root
  - `src/fa/inner_loop/coder_loop.py::_drive_session_inner` (L383) → inner loop
  - `src/fa/cli.py::_cmd_run` (L1648) → CLI entry
  - `src/fa/cli.py::main` (L2567) → top-level dispatch

greps run → findings:
  - `EventType = Literal[` → `src/fa/output.py:44` — 14 members VERIFIED (not 7)
  - `check_producer_consumer_contract.py` → `scripts/` — EXISTS, 206 lines, exits 0
  - `class ChainConfig` → `src/fa/providers/chain.py:103` — `context_limit: int = 150000`, `compaction_threshold: int | None = None` VERIFIED; getattr fallbacks are dead code
  - `or 150000` → `src/fa/inner_loop/coder_loop.py:409` — VERIFIED logic trap (swallows 0)
  - `getattr(provider_chain.config, "compaction_threshold", None)` → `coder_loop.py:410` — dead getattr (ChainConfig always has field)
  - `getattr(getattr(self.compactor_chain, "config", None), "model", "compactor")` → `compactor.py:156` — VERIFIED double-getattr bug
  - `compactor_chain: Any | None` → `compactor.py:128` — VERIFIED type erasure
  - `Any | None` on SessionState → `state.py:276-284` — 9 fields VERIFIED
  - `getattr(state.feature_flags,` → 12 sites VERIFIED across coder_loop, loop, state, spawn_subagent, subagent_runner
  - `frozen=True` → 75 sites in `src/fa/` — VERIFIED
  - `LogKind` → no hits — NEW
  - `CONSOLE_MIRROR_KINDS` → no hits — NEW
  - `FAIL_CLOSED_FLAGS` → no hits — NEW
  - `dependency_contract` → no hits — NEW
  - `corrections.jsonl` → no hits — NEW
  - `frozen_guard` → no hits — NEW
  - `kind="` in src/fa/ → 30 unique string literals VERIFIED
  - `_DEPENDENCY_PATHS` → `check_protected_paths.py:49` — `frozenset({"pyproject.toml", "uv.lock"})` VERIFIED
  - `_TCB_PATHS` → `check_protected_paths.py:31-37` — 5 paths VERIFIED
  - pyproject.toml dependencies → 6 core deps: markdown-it-py, fastjsonschema, pyyaml, bashlex, libtmux, pexpect

gold patterns mirrored:
  - `tests/test_pr1_wiring.py` — C1 budget kill-check pattern
  - `scripts/check_producer_consumer_contract.py` — contract check script pattern (regex + AST extraction)
  - `src/fa/authoring_tcb.py` — frozen manifest + fail-closed parsing pattern

conflicts/invariants found:
  - ADR-11-I1 (stdlib-only TCB) — dependency_contract.py must use tomllib only, no third-party deps
  - ADR-11-I7 (protected-path governance) — dependency_contract.toml must be added to _TCB_PATHS
  - ADR-11-I9 (live-path DoD) — every product claim needs composition-root kill-check
  - AGENTS.md rule #1 (human-curated) — G2 TRACE must be human-mediated, never auto-mutate TCB

as-is liveness:
  - context_limit getattr fallback: L2 (reachable, has bug)
  - compactor_chain typing: L2 (reachable, type-erased)
  - LogKind type: L0 (not present)
  - CONSOLE_MIRROR_KINDS: L0 (not present)
  - check_log_kind_contract.py: L0 (not present)
  - SessionDatabase session_meta metrics: L2 (set_meta exists, no guardrail metrics written)
  - fail-closed/open flag semantics: L0 (not present)
  - dependency_contract.toml: L0 (not present)
  - corrections.jsonl: L0 (not present)
  - frozen_guard.py: L0 (not present)

unresolved: → promoted to Q1, Q2

═══════════════════════════════════════════════════════════════════════
## 0. Executive intent (§3)
═══════════════════════════════════════════════════════════════════════

IDEA: Close 10 verified guardrail gaps (G2, G3, G5, G6, G9, G11, G12, G13,
  N-G1/N-G2) and 5 observability bugs (F-1 through F-10) across 5 sequential
  phases, each independently shippable.

PROJECT MEANING: In the FA inner-loop, these gaps become the difference between
  "tests pass" and "the system works." Missing LogKind types allow silent typo
  bugs. Advisory supply-chain checks allow hallucinated dependencies. No TRACE
  means recurring failures never feed back into rules. No metrics means we
  cannot tune the guardrail stack.

GOAL (G1–G12):
  G1: Fix `or 150000` logic trap — context_limit=0 must not become 150000; add MIN_CONTEXT_LIMIT=32000 floor
  G2: Fix compactor_chain type erasure — double-getattr bug on compactor.py:156
  G3: Add `LogKind = Literal[...]` + `CONSOLE_MIRROR_KINDS` + contract check script
  G4: Type 9 `Any | None` fields on SessionState with real types
  G5: Replace 12 `getattr(flags, "field", default)` with direct access + fail-closed/open semantics
  G6: Remove `context_compaction_enabled` flag gate; derive from `compaction_threshold is not None`
  G7: Create `.fa/dependency_contract.toml` + `check_dependency_contract.py` (supply-chain TCB)
  G8: Add CI behavioral assertions to loop_guard tests (G13 hybrid)
  G9: Extend session_meta with guardrail metrics at session end (G9 real-time)
  G10: Create TRACE mechanism (`.fa/corrections.jsonl` + `compile_corrections.py`)
  G11: Add frozen integrity guard (AST scanner for `object.__setattr__` bypass)
  G12: Add missing log-kind parsers + error audit + ADR-11-I1 check + max_chain_retries + compaction_end visibility

NON-GOALS:
  - Discriminated union events (P6 deferred)
  - Property-typed SessionState (P6 deferred)
  - Import-linter or dynamic-import AST scanner (deferred, small codebase)
  - Context compiler (deferred, manual skill consolidation instead)
  - Behavioral contract compiler (deferred, existing C1 tests suffice)
  - Skill consolidation / AGENTS.md pruning (separate PR)

INTENT: The codebase should ensure that every string identifier crossing a
  module boundary is Literal-typed, every safety-critical flag fails closed,
  every supply-chain edit is blocking by default, every correction feeds back
  into the rule corpus, and every frozen dataclass is defended against
  mutation bypass — and each of these must be kill-checkable from a
  composition root.

MECHANISM SKETCH: drive_session → budget_probe emits typed events →
  ConsoleRenderer renders → EventLog writes → session_meta aggregates →
  fa stats --guardrail-metrics reports. Supply-chain: check_protected_paths.py
  blocking + dependency_contract.toml comparison. TRACE: corrections.jsonl
  → compile_corrections.py → human review → catch-corpus/.

PROOF SKETCH: drive_session observes event kind+fields; kill-check removes
  the producer emit. check_dependency_contract.py observes exit code;
  kill-check removes a contract entry. frozen_guard.py observes AST scan
  result; kill-check adds `object.__setattr__` to a TCB file.

SIZE: L (5 phases, ~1040 lines, ~80–100 tests)

═══════════════════════════════════════════════════════════════════════
## 1. Non-goals & minimal-mechanism check (§5)
═══════════════════════════════════════════════════════════════════════

Explicit out-of-scope:
  - P6 (discriminated union events, property-typed SessionState)
  - New runtime assertion framework (extend existing IntentGuard/ContextBudget/LoopGuard)
  - Import-linter + dynamic-import scanner (small codebase, defer)
  - Context compiler (manual skill consolidation achieves same)
  - Behavioral contract compiler (C1 tests + mutmut already provide kill-checks)
  - Full G4 inferential sensors (LLM-as-judge, high cost, defer)
  - G1 import-linter (defer, small codebase)
  - N-G5 context consumed by guardrails (manual skill consolidation separate PR)
  - N-G6 pre-commit hook bypass (CI is the real gate, document as known gap)

Minimal-mechanism checks:
  - G7 dependency TCB: Could a 2-line exit-code change suffice? No — user chose full TCB
    pattern; 2-line change doesn't distinguish hallucinated-but-real packages from known-good.
  - G9 metrics: Could a batch script suffice? No — user chose real-time; but reduction check
    showed existing SessionDatabase.set_meta() infrastructure eliminates need for new tool.
  - G8 behavioral assertions: Could runtime assertions in prod code suffice? No — research
    shows CI-only for behavioral contracts + extend existing runtime guards is sufficient
    for FA's sandboxed filesystem. Adding a new assertion framework would increase surface.
  - G3 LogKind: Minimal — Literal type + contract check script, no new framework.

═══════════════════════════════════════════════════════════════════════
## 2. Current state → Target state (§4)
═══════════════════════════════════════════════════════════════════════

### AS-IS (verified via preflight)

| Dimension | Finding |
|---|---|
| Composition roots | drive_session (coder_loop.py:286), _cmd_run (cli.py:1648) |
| EventType | 14-member Literal in output.py:44, all 14 have ConsoleRenderer handlers, 13 have producers, 13 have C1 tests |
| LogKind | NOT PRESENT (L0) — `kind: str` on TraceEvent, 30 unique string literals found in src/fa/ |
| CONSOLE_MIRROR_KINDS | NOT PRESENT (L0) |
| SessionState `Any | None` | 9 fields at state.py:276-284 |
| getattr fallbacks | 12 sites across 6 files (coder_loop, loop, state, spawn_subagent, subagent_runner, compactor) |
| context_limit | `getattr(provider_chain.config, "context_limit", 150000) or 150000` at coder_loop.py:409 — logic trap |
| compactor_chain | `Any | None` at compactor.py:128, double-getattr at compactor.py:156 |
| compaction gate | `getattr(state.feature_flags, "context_compaction_enabled", False)` at coder_loop.py:661 — redundant with compaction_threshold |
| Supply-chain | check_protected_paths.py exits 0 for _DEPENDENCY_PATHS by default |
| session_meta metrics | SessionDatabase.set_meta() exists; no guardrail metrics written at session end |
| Behavioral tests | test_inner_loop_loop_guard.py exists; no behavioral contract assertions |
| TRACE | NOT PRESENT (L0) — no corrections log |
| Frozen guard | NOT PRESENT (L0) — 75 frozen dataclasses, no `object.__setattr__` scanner |
| ADR-11-I1 check | NOT PRESENT (L0) — no executable stdlib-only verification |
| Feature flags | FeatureFlags at feature_flags.py:27 — 13 fields, frozen, no FAIL_CLOSED/FAIL_OPEN categorization |
| Dependencies | 6 core: markdown-it-py, fastjsonschema, pyyaml, bashlex, libtmux, pexpect |

### TO-BE (machine-checkable)

| State | AS-IS | TO-BE |
|---|---|---|
| context_limit | `getattr(...) or 150000` (swallows 0) | `provider_chain.config.context_limit` + MIN_CONTEXT_LIMIT=32000 floor with clamp warning (direct, ChainConfig always has it) |
| compactor_chain type | `Any | None` | `ProviderChain | None` |
| compactor double-getattr | `getattr(getattr(self, "config", None), "model", "compactor")` | `if self.compactor_chain is not None: self.compactor_chain.config.model else: ""` |
| LogKind | `kind: str` on EventLog.append | `kind: LogKind` (Literal[30 values]) on EventLog.append |
| CONSOLE_MIRROR_KINDS | absent | `frozenset[LogKind]` with 13 members in output.py |
| check_log_kind_contract.py | absent | NEW script, exits 0 if all contracts satisfied |
| SessionState fields | 9 × `Any | None` | 8 × `RealType | None`, 1 × `Any | None` (pty_pool) |
| getattr sites | 12 × `getattr(flags, "field", default)` | Direct `flags.field` with explicit None check + fail-closed/open |
| compaction gate | `context_compaction_enabled` flag | `compaction_threshold is not None` (SSoT) |
| FAIL_CLOSED_FLAGS | absent | `frozenset` in feature_flags.py: 2 safety-critical flags (context_budget_enabled, context_compaction_enabled) |
| FAIL_OPEN_FLAGS | absent | `frozenset` in feature_flags.py: 12 convenience flags (incl. subagent_spawning_enabled — FAIL-OPEN, max_chain_retries — default=0) |
| dependency_contract.toml | absent | NEW frozen TOML, fail-closed parsing |
| check_dependency_contract.py | absent | NEW script, reuses RuleResult/Severity pattern |
| check_protected_paths.py | exits 0 for deps | exits 1 for deps by default; `--advisory-deps` flag |
| session_meta metrics | no guardrail data | `kind_counts` (incremental dict on state, not re-read at end), `budget_threshold_breaches` at session end; session_db writability checked |
| fa stats --guardrail-metrics | absent | NEW CLI flag reading session_meta across runs |
| Behavioral assertions | none in loop_guard tests | 3 assertions: deny→no-calls, hard_stop→no-tools, loop_guard→one-warn |
| corrections.jsonl | absent | NEW JSONL log, human-mediated only |
| compile_corrections.py | absent | NEW script, produces report (never auto-commits) |
| frozen_guard.py | absent | NEW AST scanner for `object.__setattr__` + frozen verification |
| ADR-11-I1 check | absent | NEW script (or extension to check_dead_flags.py), stdlib-only import scan |
| max_chain_retries | absent in FeatureFlags | `max_chain_retries: int = 0` field in FeatureFlags (config.yaml) + guard in coder_loop (fail-fast default, user opts in; distinct from transport_retries=2 in ChainEntry/models.yaml) |
| compaction_end visibility | compaction_end event exists but no circuit-breaker message | Explicit loop_warn on circuit breaker with actionable message |

Target liveness per signal: ALL must be L3 (kill-checkable from composition root).

═══════════════════════════════════════════════════════════════════════
## 3. Contracts (§6)
═══════════════════════════════════════════════════════════════════════

### CT1: LogKind type
  Type: `Literal[30 string values]` in `src/fa/output.py`
  PRE: none (type definition)
  POST: Pylance/pyright catches typos in `log.append(kind=...)` calls at lint time
  IN: string literal | OUT: Literal-typed string | ERRORS: type checker error on mismatch
  PURE: y | SIDE EFFECTS: none

### CT2: CONSOLE_MIRROR_KINDS signal
  PRODUCER: `coder_loop.py` — 3 paths (P1 non-compaction warn, P2 post-compaction, P3 circuit-breaker)
    + `spawn_subagent.py` — 2 paths (P4 spawn_done, P5 spawn_fail)
    + `cli.py` — 1 path (P6 session_end)
    Trigger: kind ∈ CONSOLE_MIRROR_KINDS → must dual-write log.append + output.emit
    Payload: varies by kind (matches existing OutputEvent.data schema)
  CONSUMER: `ConsoleRenderer._handle_*` — 14 existing handlers
  DUAL-WRITE: required for all 13 CONSOLE_MIRROR_KINDS — log.append AND output.emit in same branch
  KILL-CHECK: remove output.emit for a CONSOLE_MIRROR_KIND → check_log_kind_contract.py fails
  SHIP RULE: check_log_kind_contract.py PASS required before "shipped"

### CT3: check_log_kind_contract.py script
  Function/API: script entry point, exits 0/1
  PRE: LogKind defined in output.py; CONSOLE_MIRROR_KINDS defined
  POST: exits 0 iff all log.append kinds are in LogKind AND all CONSOLE_MIRROR_KINDS have dual-write
  ERRORS: exit 1 with actionable message per gap
  SIDE EFFECTS: stdout only (CI annotation format)

### CT4: SessionState typed fields
  Schema: 8 fields change from `Any | None` to `RealType | None`; pty_pool stays `Any | None`
  Additive: y (no breaking change to external API; `from __future__ import annotations` already present)
  Optional-narrowing: `FeatureFlags | None` → consumer must handle None explicitly (Pylance enforces)

### CT5: FAIL_CLOSED_FLAGS / FAIL_OPEN_FLAGS
  Data: two `frozenset[str]` in `feature_flags.py`
  Invariant: every FeatureFlags field is in exactly one set
  Enforced at: feature_flags.py module level
  Verified by: test that `FAIL_CLOSED_FLAGS | FAIL_OPEN_FLAGS == set(f.name for f in fields(FeatureFlags))`
  Key design: subagent_spawning_enabled is FAIL-OPEN (default=False when flags missing — don't spawn when unconfigured)

### CT6: compaction SSoT
  Invariant: `compaction_enabled = compaction_threshold is not None` — single source of truth
  Enforced at: coder_loop.py:~410 (where budget is constructed)
  Verified by: grep confirms no production code reads `context_compaction_enabled`

### CT7: dependency_contract.toml
  Schema: TOML with `[kernel]`, `[packages.core]`, `[packages.dev]`, `[packages.security_critical]`, `[registries]`
  Parse: fail-closed via `tomllib` (ADR-11-I1 compliant — stdlib-only)
  Unknown keys → HARD-BLOCK (same pattern as authoring_tcb.py manifest)
  PRODUCER: `check_dependency_contract.py` reads it
  CONSUMER: `check_protected_paths.py` protects it (in _TCB_PATHS)

### CT8: check_dependency_contract.py script
  Function/API: script entry point, exits 0/1
  PRE: dependency_contract.toml + pyproject.toml exist
  POST: exits 0 iff all pyproject.toml deps are in contract AND all security-critical deps verified
  ERRORS: exit 1 with RuleResult-formatted diagnostics
  SIDE EFFECTS: stdout only
  KILL-CHECK: remove a contract entry → script exits 1

### CT9: session_meta guardrail metrics
  PRODUCER: EventLog.kind_counts (dict[str, int], incremented inside append() under lock) → coder_loop.py session-end path writes via session_db.set_meta
  CONSUMER: `fa stats --guardrail-metrics` CLI flag → reads session_meta across runs
  Payload: `{kind: count}` dicts, `budget_threshold_breaches: int`, `chain_exhaustion_events: int` (dedicated counter, not derived from kind_counts)
  INVARIANT: kind_counts dict lives on EventLog (not SessionState), updated incrementally inside the existing _lock on each append(), not re-read from log at end
  WRITE-SAFETY: session_db writability checked before set_meta (try/except with logging, never crash at session end)
  KILL-CHECK: remove set_meta call → `fa stats --guardrail-metrics` returns empty

### CT10: corrections.jsonl
  Schema: JSONL, one object per line: `{ts, code, remediation, path, corrected_by}`
  PRODUCER: human writes entries (not automatic per AGENTS.md rule #1)
  CONSUMER: `compile_corrections.py` reads and aggregates
  Invariant: never auto-committed; human review required before any rule change

### CT11: frozen_guard.py
  Function/API: script entry point, exits 0/1
  PRE: `src/fa/` exists with Python files
  POST: exits 0 iff no `object.__setattr__` usage on frozen dataclasses AND all TCB @dataclass have `frozen=True`
  ERRORS: exit 1 with file:line diagnostics
  SIDE EFFECTS: writes `.fa/frozen_integrity_report.md`

### CT12: ADR-11-I1 stdlib-only check
  Function/API: script or extension, exits 0/1
  POST: exits 0 iff `authoring_tcb.py` imports are all from `sys.stdlib_module_names`
  KILL-CHECK: add `import requests` to authoring_tcb.py → check exits 1

### CT13: max_chain_retries FeatureFlags field
  Schema: `max_chain_retries: int = 0` added to FeatureFlags (fail-fast default, user opts in)
  Config source: `~/.fa/config.yaml` feature_flags block (session-level policy)
  NOT to be confused with: `transport_retries: int = 2` in ChainEntry (`~/.fa/models.yaml`, per-route HTTP-level)
  Relationship: transport_retries fires first within a single provider (network-level: ConnectionError, TimeoutError);
    chain walks to next entry on failure; max_chain_retries fires only after
    ProviderChainExhaustedError (ALL entries exhausted) — retries the entire provider chain
  PRODUCER: coder_loop.py reads `state.feature_flags.max_chain_retries` on ProviderChainExhaustedError
  CONSUMER: inner loop chain-retry counter comparison
  KILL-CHECK: set max_chain_retries=0 → no retries on chain exhaustion (current behavior preserved)

═══════════════════════════════════════════════════════════════════════
## 4. Path & flag matrix (§7)
═══════════════════════════════════════════════════════════════════════

### 4.1 Path inventory

| P# | Trigger condition | File:line/symbol | Flag state | Covering S# |
|---|---|---|---|---|
| P1 | context_limit=0 provided | coder_loop.py:409 `context_limit` | any | S1 |
| P2 | compactor_chain is None | compactor.py:133 `if not self.compactor_chain` | any | S2 |
| P3 | compactor_chain is set, config.model accessed | compactor.py:156 double-getattr | any | S2 |
| P4 | log.append(kind=X) called | state.py:~100 `EventLog.append` | any | S5–S8 |
| P5 | CONSOLE_MIRROR_KIND event emitted | coder_loop.py:642,676,693 | any | S8 |
| P6 | feature_flags is None at read site | coder_loop.py:632 | context_budget_enabled | S12 |
| P7 | feature_flags is None at safety-critical site | spawn_subagent.py:32 | subagent_spawning_enabled (FAIL-OPEN: default=False) | S13 |
| P8 | compaction_threshold is None | coder_loop.py:410 | any | S13 |
| P9 | Dependency manifest edited in PR | check_protected_paths.py:159 | fail_on_touch | S14 |
| P10 | New/unknown package in pyproject.toml | check_dependency_contract.py (NEW) | any | S14 |
| P11 | Session ends with guardrail events | coder_loop.py:~1281 session-end | any | S16 |
| P12 | loop_guard triggers | coder_loop.py loop_guard path | any | S17 |
| P13 | Circuit breaker fires during compaction | coder_loop.py:~919 | any | S23 |
| P14 | object.__setattr__ used on frozen dataclass | any file in src/fa/ | any | S21 |

### 4.2 Flag/provider matrix

| ID | Flags/env | Proves | Covering S# |
|---|---|---|---|
| A | primary config (models.yaml loaded) | main path works | S1–S3 |
| B | defaults (out of the box) | operator-facing default path | S12 |
| C | context_budget_enabled=True (default) | budget check active | S12 |
| D | context_budget_enabled=False | budget check skipped | S12 |
| E | subagent_spawning_enabled=False (default) | spawning denied | S12 |
| F | context_compaction_enabled=True (deprecated) | SSoT ignores it, uses threshold | S13 |
| G | --advisory-deps flag | dependency edits advisory | S14 |
| H | compaction_threshold=None | compaction disabled | S13 |
| I | compaction_threshold=50000 | compaction enabled | S13 |

═══════════════════════════════════════════════════════════════════════
## 5. Step-by-step implementation (§8)
═══════════════════════════════════════════════════════════════════════

### ── PHASE 1: Logic Error Fixes ────────────────────────────────────

### Step S1: Fix `or 150000` logic trap — direct access + MIN_CONTEXT_LIMIT floor
Traces-to: G1, CT4 (SessionState typed fields)
Depends-on: none | Parallelizable-with: S2
Target liveness: L2→L3

Edit:
  - path: `src/fa/inner_loop/coder_loop.py`  symbol: `_drive_session_inner`  change: replace getattr+or with direct access + MIN_CONTEXT_LIMIT floor

Do:
  1. At line 409, replace:
     ```python
     context_limit = getattr(provider_chain.config, "context_limit", 150000) or 150000
     compaction_threshold = getattr(provider_chain.config, "compaction_threshold", None)
     ```
     with:
     ```python
     context_limit = provider_chain.config.context_limit
     compaction_threshold = provider_chain.config.compaction_threshold
     ```
  2. Add MIN_CONTEXT_LIMIT floor after the direct access:
     ```python
     MIN_CONTEXT_LIMIT = 32_000  # Below this, context budget is meaningless

     context_limit = provider_chain.config.context_limit
     if context_limit < MIN_CONTEXT_LIMIT:
         state.log.append(
             actor="runtime",
             kind="telemetry",
             content={"message": f"context_limit={context_limit} below floor {MIN_CONTEXT_LIMIT}, clamped"},
         )
         context_limit = MIN_CONTEXT_LIMIT
     ```
  3. Verify ChainConfig always has both fields (confirmed at chain.py:107-108).
  4. ChainConfig.validate() already rejects context_limit <= 0 (chain.py:64-65); the floor is
     defense-in-depth for misconfigured-but-positive values (e.g., typo `100` instead of `100000`).
  5. NOTE on kind="telemetry": uses the existing `telemetry` kind rather than introducing a new
     kind for a single instance (reduction-first). The clamp is informational — the system handled
     it, it's notifying the operator. `context_budget_warn` is reserved for actual budget pressure
     (high token usage), not config issues.

Do-not:
  - Touch the budget construction or hard-stop logic (separate contracts).
  - Implement adaptive context sizing from API metadata (future work, see S1b).

Exit criteria:
  - [ ] `grep -n "or 150000" src/fa/inner_loop/coder_loop.py` returns no hits
  - [ ] `grep -n "getattr.*context_limit\|getattr.*compaction_threshold" src/fa/inner_loop/coder_loop.py` returns no hits
  - [ ] pyright passes on coder_loop.py

Kill-check: set `context_limit=0` in a test ChainConfig → ConfigurationError raised upstream (chain.py:64). Set `context_limit=100` → budget.limit_tokens == 32000 (clamped to floor).

### Step S1b: Add TODO/ADR reference for adaptive context from API metadata
Traces-to: G1 (future evolution)
Depends-on: S1 | Parallelizable-with: none
Target liveness: L3 (documentation only)

Do:
  1. Add TODO comment in coder_loop.py after context_limit assignment:
     ```python
     # TODO: Adaptive context sizing — eventually derive context_limit from API response
     # metadata (model's actual context_window). ADR-17 §Option B point 5 describes the
     # target architecture. Current implementation uses static config from models.yaml.
     # See: knowledge/adr/ADR-17-context-management-and-compaction.md
     ```
  2. Verify: ADR-17 exists at `knowledge/adr/ADR-17-context-management-and-compaction.md` (confirmed from PR #53).
  3. Do NOT attempt implementation — adaptive sizing from API metadata is a separate spike.
     Not verified to exist in any PR; no code reads context_window from API responses.

Do-not:
  - Implement adaptive context — out of scope for P1–P5.

Exit criteria:
  - [ ] TODO comment present at context_limit assignment site
  - [ ] ADR-17 reference resolves

Kill-check: n/a (documentation only, no behavioral change)

### Step S2: Fix compactor_chain type erasure + double-getattr
Traces-to: G2, CT4
Depends-on: none | Parallelizable-with: S1
Target liveness: L2→L3

Edit:
  - path: `src/fa/inner_loop/compaction/compactor.py`  symbol: `FullLLMCompactor.__init__` + `compact`  change: type as `ProviderChain | None`, fix model_slug resolution

Do:
  1. At line 128, replace:
     ```python
     def __init__(self, compactor_chain: Any | None = None):
     ```
     with:
     ```python
     from fa.providers.chain import ProviderChain

     def __init__(self, compactor_chain: ProviderChain | None = None):
     ```
  2. At line 156, replace:
     ```python
     model_slug = getattr(getattr(self.compactor_chain, "config", None), "model", "compactor")
     ```
     with:
     ```python
     model_slug = self.compactor_chain.config.model if self.compactor_chain is not None else ""
     ```
  3. Note: the empty string for model_slug when chain is None is acceptable — the `if not self.compactor_chain` guard at line 133 already catches this case and falls back to local truncation. If we reach line 156, the chain exists.

Do-not:
  - Add `"compactor"` fallback — it's dead code (config always has model on a ProviderChain)

Exit criteria:
  - [ ] `grep -n "Any | None" src/fa/inner_loop/compaction/compactor.py` returns 0 hits for compactor_chain
  - [ ] `grep -n "object.__setattr__\|getattr.*config.*model" src/fa/inner_loop/compaction/compactor.py` returns 0 hits
  - [ ] pyright passes on compactor.py

Kill-check: pass `compactor_chain=None` to FullLLMCompactor → compact() returns _local_fallback_truncate result (not crash)

### Step S3: Verify Phase 1
Traces-to: G1, G2
Depends-on: S1, S2 | Parallelizable-with: none
Target liveness: L3

Do:
  1. Run `python scripts/check_producer_consumer_contract.py` → exit 0
  2. Run `python scripts/check_no_mocked_dataclasses.py` → exit 0
  3. Run `python -m pytest tests/ -k "context_limit or compactor or compaction" --tb=short -q`
  4. Verify S1 kill-check: `context_limit=0` → ConfigurationError; `context_limit=100` → clamped to 32000
  4. Commit as "fix: logic traps in context_limit getattr and compactor_chain typing (F-3, F-4)"

Exit criteria:
  - [ ] All scripts exit 0
  - [ ] All targeted tests pass

### ── PHASE 2: LogKind + Console-Mirror + Contract Check + G9 Metrics ──

### Step S4: Add `LogKind = Literal[...]` to output.py
Traces-to: G3, CT1
Depends-on: S1 (clean diff) | Parallelizable-with: S9
Target liveness: L0→L1

Edit:
  - path: `src/fa/output.py`  symbol: module-level  change: add LogKind Literal after EventType

Do:
  1. After `EventType` definition (line ~58), add:
     ```python
     LogKind = Literal[
         # Session lifecycle
         "run_started",
         "run_stopped",
         "session_summary",
         # LLM I/O
         "user_msg",
         "model_msg",
         "usage",
         "provider_attempt",
         # Tool I/O
         "tool_call",
         "tool_result",
         # Hooks / guards
         "hook_decision",
         "loop_guard_warn",
         "audit",
         # Context budget
         "context_budget_warn",
         "context_budget_hard_stop",
         # Compaction
         "compaction_warning",  # emitted before compaction starts (context pressure detected)
         "compaction_circuit_breaker",
         "compaction_stage2_start",
         "compaction_stage2_done",
         "compaction_stage2_error",
         "compaction_stage3_start",
         "compaction_stage3_done",
         "compaction_stage3_error",
         # Subagent
         "subagent_spawn_start",
         "subagent_spawn_done",
         "subagent_spawn_fail",
         # Observability / recovery
         "recovery_action",
         "verification",
         "cost_observation",
         "telemetry",
         # Infrastructure
         "service_unavailable",
         "timeout",
     ]
     ```
  2. Add `"LogKind"` to `__all__`.
  3. Verify: `len(typing.get_args(LogKind))` must equal 30 (same count as grep found).

Do-not:
  - Add any new log kinds not already present in `src/fa/`

Note: The 30-member list above is a preflight estimate from `grep kind="` in src/fa/.
Before implementing, verify the exact set by running `python scripts/check_producer_consumer_contract.py`
and cross-referencing with actual call sites. The count may differ if dynamic kind construction
(e.g., `kind=f"{prefix}_warn"`) exists. The contract check script (S7) will be the authoritative validator.

Exit criteria:
  - [ ] `grep -n "LogKind" src/fa/output.py` finds the definition
  - [ ] `python -c "from fa.output import LogKind; import typing; assert len(typing.get_args(LogKind)) == 30"`

Kill-check: remove one Literal member → pyright fails on the `log.append(kind="...")` call site using that member

### Step S5: Add `CONSOLE_MIRROR_KINDS` to output.py
Traces-to: G3, CT2
Depends-on: S4 | Parallelizable-with: none
Target liveness: L0→L1

Edit:
  - path: `src/fa/output.py`  symbol: module-level  change: add CONSOLE_MIRROR_KINDS frozenset

Do:
  1. After LogKind, add:
     ```python
     CONSOLE_MIRROR_KINDS: frozenset[LogKind] = frozenset(
         {
             "context_budget_warn",
             "context_budget_hard_stop",
             "compaction_stage2_start",
             "compaction_stage2_done",
             "compaction_stage2_error",
             "compaction_stage3_start",
             "compaction_stage3_done",
             "compaction_stage3_error",
             "compaction_circuit_breaker",
             "tool_call",
             "subagent_spawn_done",
             "subagent_spawn_fail",
             "run_stopped",
         }
     )
     ```
  2. Add `"CONSOLE_MIRROR_KINDS"` to `__all__`.

Exit criteria:
  - [ ] `len(CONSOLE_MIRROR_KINDS) == 13`
  - [ ] Every member is also in LogKind (type-checked)

### Step S6: Type `EventLog.append(kind: LogKind)` + add `compaction_warning` producer
Traces-to: G3, CT1
Depends-on: S4 | Parallelizable-with: S5
Target liveness: L1→L2

Edit:
  - path: `src/fa/inner_loop/state.py`  symbol: `EventLog.append`  change: type `kind: str` → `kind: LogKind`
  - path: `src/fa/inner_loop/coder_loop.py`  symbol: compaction entry path  change: add `compaction_warning` producer

Do:
  1. Add `from fa.output import LogKind` to imports (conditional or top-level).
  2. In `EventLog.append()`, change `kind: str` parameter to `kind: LogKind`.
  3. Keep `TraceEvent.kind: str` unchanged (JSONL round-trip loses Literal constraint).
  4. Run pyright on state.py — all 30+ call sites should already use correct string literals.
  5. Add `compaction_warning` producer in coder_loop.py — at the point where the budget check
     returns `stage2`/`stage3` action, emit a `compaction_warning` event BEFORE
     any subsequent action. This fires in BOTH cases:
     - Compaction ENABLED: "compaction is about to happen" (before `compaction_stage2_start`)
     - Compaction DISABLED: "compaction would have been triggered but is disabled" (before the
       existing `context_budget_warn` / `context_budget_hard_stop` fallback)
     This provides a single observation point for "context pressure reached compaction threshold"
     regardless of whether compaction is actually enabled, making it easy to find all places where
     the system detected compaction-level pressure. Location: ~coder_loop.py:665
     (at the top of the `elif decision["action"] in {"stage2", "stage3"}` block).
     ```python
     state.log.append(
         actor="runtime",
         kind="compaction_warning",
         content={
             "action": decision["action"],
             "compaction_enabled": compaction_enabled,
             "ratio": last_budget_ratio,
             "threshold": budget.stage2_threshold,
         },
     )
     ```
  6. Dynamic kind construction (e.g., `kind = "subagent_spawn_done" if ... else "subagent_spawn_fail"`
     in spawn_subagent.py): spawn_subagent.py is due for refactor. Dynamic kind handling is DEFERRED
     to the next implementation plan. Mark with TODO comment for now:
     ```python
     # TODO: type as LogKind after spawn_subagent.py refactor (deferred)
     kind = "subagent_spawn_done" if envelope.exit_code == 0 else "subagent_spawn_fail"
     ```

Do-not:
  - Change TraceEvent.kind to LogKind (breaks JSONL deserialization)
  - Refactor spawn_subagent.py dynamic kind construction now (deferred)

Exit criteria:
  - [ ] pyright passes on state.py with 0 errors
  - [ ] `grep -n "def append" src/fa/inner_loop/state.py` shows `kind: LogKind`
  - [ ] `grep -n "compaction_warning" src/fa/inner_loop/coder_loop.py` finds the producer

Kill-check: change one `kind="typo_value"` in a producer → pyright fails

### Step S7: Create `scripts/check_log_kind_contract.py`
Traces-to: G3, CT3
Depends-on: S4, S5 | Parallelizable-with: S6
Target liveness: L0→L3

Edit:
  - path: `scripts/check_log_kind_contract.py`  symbol: NEW  change: create script

Do:
  1. Create script following `check_producer_consumer_contract.py` pattern:
     - Extract LogKind literals from output.py (regex on Literal definition)
     - Extract CONSOLE_MIRROR_KINDS from output.py
     - Find all `log.append(kind=...)` calls in `src/fa/`
     - Verify each kind is in LogKind set
     - For each CONSOLE_MIRROR_KINDS member, verify output.emit exists on same code path
     - Check C1 test coverage per kind
     - Exit 1 if any gaps found
  2. Add to `justfile` check target.
  3. Add test: `tests/test_check_log_kind_contract.py` — synthetic fixture verifies script behavior.

Do-not:
  - Add `check_log_kind_contract.py` to CI without a passing test

Exit criteria:
  - [ ] `python scripts/check_log_kind_contract.py` exits 0 on clean tree
  - [ ] Test exists and passes

Kill-check: remove a `log.append(kind=...)` producer → contract check exits 1

### Step S8: Update SKILL.md I-TW-17
Traces-to: G3, CT2
Depends-on: S5 | Parallelizable-with: S7
Target liveness: L3

Edit:
  - path: `knowledge/skills/tests-writing/SKILL.md`  symbol: I-TW-17  change: replace vague dual-write invariant with CONSOLE_MIRROR_KINDS reference

Do:
  1. Replace I-TW-17 text with:
     ```
     I-TW-17: CONSOLE_MIRROR_KINDS (in output.py) defines which log.append kinds
     MUST also emit an OutputEvent. Every kind in that set must have both a
     log.append producer and an output.emit producer on the same code path.
     The check_log_kind_contract.py script validates this.
     ```

Exit criteria:
  - [ ] grep finds "CONSOLE_MIRROR_KINDS" in SKILL.md

### Step S9: Extend session_meta with guardrail metrics (G9)
Traces-to: G9, CT9
Depends-on: none | Parallelizable-with: S4–S8
Target liveness: L2→L3

Edit:
  - path: `src/fa/inner_loop/coder_loop.py`  symbol: session-end path (~L1281)  change: add set_meta calls
  - path: `src/fa/stats.py`  symbol: `parse_session` / CLI  change: add --guardrail-metrics flag

Do:
  1. Add `kind_counts: dict[str, int]` field to `EventLog.__init__` (initialized as `{}`).
  2. In `EventLog.append()`, inside the existing `with self._lock:` block, add:
     ```python
     self.kind_counts[kind] = self.kind_counts.get(kind, 0) + 1
     ```
     This ensures the counter is thread-safe (same lock as the write) and built incrementally.
  3. In coder_loop.py session-end path (where `state.log.append(actor="runtime", kind="run_stopped", ...)`), add:
     ```python
     # G9: guardrail metrics for data-driven improvement (incremental counting from EventLog)
     if state.session_db is not None and state.log is not None:
         try:
             kind_counts = dict(state.log.kind_counts)
             state.session_db.set_meta("kind_counts", kind_counts, _now_iso_z())
             budget_breaches = kind_counts.get("context_budget_warn", 0) + kind_counts.get("context_budget_hard_stop", 0)
             state.session_db.set_meta("budget_threshold_breaches", budget_breaches, _now_iso_z())
             state.session_db.set_meta("chain_exhaustion_events", state.log.chain_exhaustion_count, _now_iso_z())
         except Exception as exc:
             # Never crash at session end — metrics are best-effort
             logger.warning("session_meta write failed: %s", exc)
     ```
  4. In stats.py, add `--guardrail-metrics` flag that reads session_meta across runs.
  5. Add test: `test_session_meta_guardrail_metrics` — C1 test that drives a session and asserts kind_counts present.
  6. Add test: `test_session_metrics_survive_db_unavailable` — verify session doesn't crash when session_db.write fails.
  7. Add `chain_exhaustion_count: int = 0` counter to EventLog, incremented only in the
     ProviderChainExhaustedError handler (S22). This gives a precise metric without post-hoc filtering.
     At session end, write `state.log.chain_exhaustion_count` to session_meta.

Do-not:
  - Add a new metrics collector script — extend existing infrastructure
  - Add guardrail_overrides counting (requires CI annotation parsing, defer)

Exit criteria:
  - [ ] `fa stats --guardrail-metrics` outputs kind_counts for a session
  - [ ] C1 test exists and passes

Kill-check: remove set_meta calls → test_session_meta_guardrail_metrics fails

### Step S10: Verify Phase 2
Traces-to: G3, G9
Depends-on: S4–S9 | Parallelizable-with: none
Target liveness: L3

Do:
  1. `python scripts/check_log_kind_contract.py` → exit 0
  2. `python scripts/check_producer_consumer_contract.py` → exit 0
  3. `python scripts/check_no_mocked_dataclasses.py` → exit 0
  4. `python -m pytest tests/ --tb=short -q` (targeted subset)
  5. Commit as "feat: LogKind type + console-mirror contract + G9 session_meta metrics (F-1, F-2, G9)"

Exit criteria:
  - [ ] All scripts exit 0
  - [ ] All targeted tests pass

### ── PHASE 3: Type SessionState Fields ─────────────────────────────

### Step S11: Type 9 `Any | None` fields
Traces-to: G4, CT4
Depends-on: S6 (LogKind type needed for EventLog import) | Parallelizable-with: none
Target liveness: L1→L2

Edit:
  - path: `src/fa/inner_loop/state.py`  symbol: `SessionState`  change: replace 8 `Any | None` with real types

Do:
  1. Add TYPE_CHECKING imports:
     ```python
     if TYPE_CHECKING:
         from fa.blackboard.blackboard import Blackboard
         from fa.inner_loop.artifacts import ArtifactStore
         from fa.inner_loop.transaction import Transaction
         from fa.observability.redaction import SecretRedactor
         from fa.output import EventBus
         from fa.runtime.bash_executor import BashExecutor
         from fa.telemetry.telemetry import TelemetryLogger
         from fa.workspace.worktree_manager import WorktreeManager
     ```
  2. Move `from fa.feature_flags import FeatureFlags` to TYPE_CHECKING block (keep runtime import in __post_init__).
  3. Replace fields at state.py:276-284:
     ```python
     transaction: Transaction | None = None
     blackboard: Blackboard | None = None
     telemetry: TelemetryLogger | None = None
     feature_flags: FeatureFlags | None = None
     artifact_store: ArtifactStore | None = None
     pty_pool: Any | None = None  # PtyPool — optional module, keep Any
     bash_executor: BashExecutor | None = None  # Protocol from fa.runtime.bash_executor
     worktree_manager: WorktreeManager | None = None
     session_db: SessionDatabase | None = None
     output_bus: EventBus | None = None
     ```
  4. Add `from fa.runtime.bash_executor import BashExecutor` to TYPE_CHECKING block.
     No circular dependency risk: `fa.runtime` has zero imports from `fa.inner_loop`.
     The bash_executor field is constructed lazily in `__post_init__` (after pty_pool is
     available) or on first access in run_bash.py, same pattern as other optional runtime objects.
  5. Run pyright — fix any consumer sites that need explicit None checks.

Do-not:
  - Change pty_pool from Any (fa.runtime is optional)
  - Add properties yet (P6 deferred)

Exit criteria:
  - [ ] `grep -n "Any | None" src/fa/inner_loop/state.py` returns only pty_pool
  - [ ] `bash_executor: BashExecutor | None = None` is a declared field
  - [ ] pyright passes on state.py

Kill-check: pass wrong type to a field → pyright fails

### Step S12: Verify Phase 3
Depends-on: S11 | Parallelizable-with: none

Do:
  1. pyright on all modified files
  2. `python scripts/check_producer_consumer_contract.py` → exit 0
  3. Commit as "feat: type 9 Any|None fields on SessionState (F-5)"

Exit criteria:
  - [ ] pyright clean
  - [ ] all contract checks pass

### ── PHASE 4: Fail-Closed/Open + Compaction SSoT + G12 + G13 ────────

### Step S13: Add FAIL_CLOSED_FLAGS / FAIL_OPEN_FLAGS + replace getattr
Traces-to: G5, CT5
Depends-on: S11 | Parallelizable-with: S14
Target liveness: L0→L3

Edit:
  - path: `src/fa/feature_flags.py`  symbol: module-level after FeatureFlags  change: add flag categories
  - path: multiple  symbol: getattr sites  change: replace with direct access

Do:
  1. Add to feature_flags.py after FeatureFlags class:
     ```python
     # FAIL_CLOSED: when feature_flags is None, default to the RESTRICTIVE/SAFE value.
     # These flags guard safety-critical paths — if we can't read config, be conservative.
     FAIL_CLOSED_FLAGS: frozenset[str] = frozenset(
         {
             "context_budget_enabled",  # default=True when flags missing → budget check active
             "context_compaction_enabled",  # default=True when flags missing → compaction active (DEPRECATED post-S14; field must remain for frozen dataclass backward compat — 10+ test sites construct it)
         }
     )
     # FAIL-OPEN: when feature_flags is None, default to the PERMISSIVE/DENY value.
     # subagent_spawning_enabled: default=False → don't spawn when unconfigured (DANGEROUS if True)
     FAIL_OPEN_FLAGS: frozenset[str] = frozenset(
         {
             "subagent_spawning_enabled",  # default=False → don't spawn when unconfigured
             "blackboard_enabled",
             "telemetry_enabled",
             "tool_batching_enabled",
             "pty_pool_max_size",
             "worktree_mode",
             "fts_db_path",
             "prompt_caching",
             "offload_threshold",
             "max_subagent_spawns_per_session",
             "blackboard_filtered_history_include_plans",
             "max_chain_retries",  # default=0 → fail-fast when unconfigured
         }
     )
```
  2. Replace 12 `getattr(flags, "field", default)` sites with direct access + explicit None checks:
     - FAIL-CLOSED flags: `state.feature_flags.context_budget_enabled if state.feature_flags is not None else True` (restrictive default)
     - FAIL-OPEN flags: same pattern with permissive defaults (e.g., `subagent_spawning_enabled` defaults to False when flags missing)
     - Non-flag getattr sites (prompt_composer.py:149, subagent_runner.py:76): replace `getattr(session, "feature_flags", None)` with `session.feature_flags` (SessionState always has the field, even if None)
  3. Replace 18 `getattr(session, "field", None)` sites across tools/ and subagent modules:
     - After S11 typed the SessionState fields, these getattr calls are unnecessary — direct
       attribute access works. Replace with `session.blackboard`, `session.transaction`, etc.
     - For declared fields that may be None, add explicit None checks: `if session.blackboard is not None: ...`
     - `bash_executor`: now a declared field on SessionState (added in S11). Replace
       `getattr(session, "bash_executor", None)` with `session.bash_executor`. Construct
       InProcessPtyExecutor lazily if None and pty_pool is available (same logic as current
       run_bash.py, but via direct attribute access instead of getattr).
     - `getattr(session, "workspace_root", None)` → `session.workspace_root` (always present, Path)
     - `getattr(session, "subagent_spawns", 0)` → `session.subagent_spawns` (always present, int, default 0)
     - `getattr(session, "output_bus", None)` → `session.output_bus` (typed in S11)
  4. Add test: `FAIL_CLOSED_FLAGS | FAIL_OPEN_FLAGS == set(f.name for f in fields(FeatureFlags))` — every field categorized, no exceptions.
  5. Add test: verify no `getattr(session, ...)` or `getattr(state, ...)` remain in `src/fa/inner_loop/`.

Do-not:
  - Add a `read_flag()` helper function — simpler to use direct access + None check

Exit criteria:
  - [ ] `grep -rn "getattr.*feature_flags" src/fa/ --include="*.py"` returns 0 hits
  - [ ] `grep -rn "getattr(session" src/fa/inner_loop/ --include="*.py"` returns 0 hits
  - [ ] categorization test passes

Kill-check: set feature_flags=None → safety-critical flag defaults to restrictive value

### Step S14: Remove compaction_enabled flag gate (F-10 / G6)
Traces-to: G6, CT6
Depends-on: S13 | Parallelizable-with: S15
Target liveness: L2→L3

Edit:
  - path: `src/fa/inner_loop/coder_loop.py`  symbol: ~L661  change: replace flag gate with threshold check

Do:
  1. At coder_loop.py:~661, replace:
     ```python
     compaction_enabled = getattr(state.feature_flags, "context_compaction_enabled", False)
     ```
     with:
     ```python
     compaction_enabled = compaction_threshold is not None
     ```
  2. Mark `context_compaction_enabled` in FeatureFlags as deprecated with comment:
     ```python
     context_compaction_enabled: bool = False  # DEPRECATED — derive from compaction_threshold is not None instead
     ```
  3. Add contract check: `check_log_kind_contract.py` flags any production code reading `context_compaction_enabled`.
  4. Do NOT delete the `context_compaction_enabled` field from FeatureFlags — removing a field from a
     frozen dataclass is a breaking change for any code that constructs FeatureFlags with keyword
     arguments. Instead, stop reading it in production code and let it remain as a deprecated no-op field.
     Removal can happen in P6+ when all call sites are verified.

Exit criteria:
  - [ ] `grep -rn "context_compaction_enabled" src/fa/ --include="*.py"` returns only the FeatureFlags field definition and deprecated comment
  - [ ] `compaction_threshold is not None` controls compaction path

Kill-check: set `compaction_threshold=None` → compaction disabled; set `compaction_threshold=50000` → compaction enabled

### Step S15: Create dependency_contract.toml + check_dependency_contract.py (G12)
Traces-to: G7, CT7, CT8
Depends-on: none | Parallelizable-with: S13, S14
Target liveness: L0→L3

Edit:
  - path: `.fa/dependency_contract.toml`  symbol: NEW  change: create frozen contract
  - path: `scripts/check_dependency_contract.py`  symbol: NEW  change: create check script
  - path: `scripts/check_protected_paths.py`  symbol: `_TCB_PATHS`, `_emit_dependency_flags`  change: add contract to TCB, make deps blocking

Do:
  1. Create `.fa/dependency_contract.toml`:
     ```toml
     [kernel]
     version = "0.1"

     [packages.core]
     markdown-it-py = ">=3.0"
     fastjsonschema = ">=2.21"
     pyyaml = ">=6.0"
     bashlex = ">=0.18"
     libtmux = ">=0.40"
     pexpect = ">=4.9"

     [packages.security_critical]
     pyyaml = ">=6.0"  # yaml.safe_load only, per ADR-9

     [registries]
     default = "pypi"
     ```
  2. Create `scripts/check_dependency_contract.py` (~80 lines):
     - Parse contract via `tomllib` (stdlib-only, ADR-11-I1)
     - Read `pyproject.toml` dependencies via `tomllib`
     - Compare: packages in pyproject but not in contract → ADVISORY with expires_on
     - Packages in security_critical but missing from contract → HARD-BLOCK
     - Unknown keys → HARD-BLOCK (fail-closed)
     - Output: RuleResult-formatted diagnostics (reuse Severity from authoring_tcb pattern)
  3. Update `check_protected_paths.py`:
     - Add `.fa/dependency_contract.toml` to `_TCB_PATHS`
     - Change default exit for `_DEPENDENCY_PATHS` from 0 to 1 (blocking)
     - Add `--advisory-deps` flag to restore advisory behavior
  4. Add `justfile` target: `dependency-check`
  5. Add test: `tests/test_check_dependency_contract.py`

Do-not:
  - Add pip-audit integration (already in `just audit`)
  - Add PyPI registry verification (defer — network dependency)

Exit criteria:
  - [ ] `python scripts/check_dependency_contract.py` exits 0 on current tree
  - [ ] `.fa/dependency_contract.toml` is in `_TCB_PATHS`
  - [ ] `check_protected_paths.py` exits 1 for dependency edits by default

Kill-check: add `requests = ">=2.0"` to pyproject.toml → check exits 1 (not in contract)

### Step S16: Add behavioral assertions to loop_guard tests (G13)
Traces-to: G8, CT2 (signal)
Depends-on: S13 | Parallelizable-with: S15
Target liveness: L2→L3

Edit:
  - path: `tests/test_inner_loop_loop_guard.py`  symbol: NEW test functions  change: add behavioral contract assertions

Do:
  1. Add 3 test assertions:
     ```python
     def test_intent_guard_deny_no_provider_calls():
         """If IntentGuard denies, no provider calls made after denial."""
         # Drive session where IntentGuard denies a tool call
         # Assert: provider_chain.request.call_count == 0 after denial


     def test_hard_stop_no_tool_calls():
         """If context_budget_hard_stop fires, no tool calls within 50ms."""
         # Drive session to hard-stop threshold
         # Assert: no tool_call events after hard_stop event


     def test_loop_guard_exactly_one_warn():
         """If loop_guard triggers, exactly one loop_warn event emitted."""
         # Drive session with repeated identical tool calls
         # Assert: len([e for e in events if e.kind == "loop_guard_warn"]) == 1
     ```

Do-not:
  - Add runtime assertions in production code (CI-only for behavioral contracts)

Exit criteria:
  - [ ] 3 new test functions exist and pass
  - [ ] Each test has a named oracle (event kind+fields or call_count)

Kill-check: remove IntentGuard deny logic → test_intent_guard_deny_no_provider_calls fails

### Step S17: Add LOGIC-10 actionable console guidance for abnormal_stop
Traces-to: G12 (implementation plan), CT2
Depends-on: none | Parallelizable-with: S16
Target liveness: L1→L3

Edit:
  - path: `src/fa/inner_loop/coder_loop.py`  symbol: abnormal stop path  change: add loop_warn event with actionable hint

Do:
  1. Where finish_reason is abnormal (length, content_filter), emit:
     ```python
     hint = ""
     if response.finish_reason == "length":
         hint = "Output truncated (finish_reason=length). Consider increasing max_tokens or simplifying the task."
     elif response.finish_reason == "content_filter":
         hint = "Output blocked by content filter (finish_reason=content_filter). Review the prompt for policy violations."
     else:
         hint = f"Unexpected finish_reason: {response.finish_reason}"
     output.emit(OutputEvent(type="loop_warn", data={"detector": "abnormal_stop", "message": hint}))
     ```

Exit criteria:
  - [ ] `grep -n "abnormal_stop" src/fa/inner_loop/coder_loop.py` finds the hint emission

Kill-check: remove the emit → test asserting loop_warn on abnormal_stop fails

### Step S18: Verify Phase 4
Depends-on: S13–S17 | Parallelizable-with: none

Do:
  1. All contract check scripts exit 0
  2. All new tests pass
  3. Commit as "feat: fail-closed flags, compaction SSoT, dependency TCB, behavioral assertions (F-6, F-10, G12, G13, LOGIC-10)"

Exit criteria:
  - [ ] All contract checks pass
  - [ ] All behavioral assertion tests pass

### ── PHASE 5: Coverage + TRACE + Audit + Guards ────────────────────

### Step S19: Add missing log-kind parsers to fa stats (F-7)
Traces-to: G12, CT1
Depends-on: S4 (LogKind defines the canonical set) | Parallelizable-with: S20–S23
Target liveness: L2→L3

Edit:
  - path: `src/fa/stats.py`  symbol: `parse_session`  change: add elif branches for 12 invisible log kinds

Do:
  1. Add dataclasses: `CompactionTiming`, `CircuitBreakerEvent`, `RecoveryAction`, `VerificationEvent`, `CostObservation`, `ModelMessage`, `UserMessage`, `AuditEvent`, `TelemetryEvent`
  2. Add fields to `SessionAnalytics`
  3. Add elif branches in parse_session for each new kind
  4. Add rendering in render_session

Exit criteria:
  - [ ] All 30 log kinds have parsers or are in UNPARSED_KINDS allowlist
  - [ ] `fa stats` output includes compaction timing data

### Step S20: Create TRACE mechanism (G2)
Traces-to: G10, CT10
Depends-on: none | Parallelizable-with: S19, S21–S23
Target liveness: L0→L3

Edit:
  - path: `.fa/corrections.jsonl`  symbol: NEW  change: create empty corrections log
  - path: `scripts/compile_corrections.py`  symbol: NEW  change: create human-mediated correction compiler

Do:
  1. Create `.fa/corrections.jsonl` (empty file with header comment):
     ```jsonl
     # TRACE: Human-mediated correction log. Each entry records a correction
     # and its remediation for future rule mining. Never auto-committed.
     # Schema: {"ts": "ISO-8601", "code": "FA-AUTHORING-...", "remediation": "...", "path": "...", "corrected_by": "human"}
     ```
  2. Create `scripts/compile_corrections.py`:
     - Read corrections.jsonl
     - Group by code, count occurrences
     - Produce summary: most common correction patterns
     - Suggest candidate Level-1 rule specifications (for human review)
     - NEVER auto-commit — output to stdout only
  3. Add test: synthetic corrections.jsonl → compile_corrections.py produces expected summary.
  4. Cross-reference with existing `knowledge/trace/` infrastructure:
     - `knowledge/trace/codebase_map.json` and `knowledge/trace/gotchas.md` already exist (referenced at cli.py:838-839)
     - `.fa/corrections.jsonl` is separate from (not replacing) knowledge/trace/ — it's TCB-protected
     - Add a comment in `knowledge/trace/gotchas.md` pointing to `.fa/corrections.jsonl` for guardrail corrections
     - `compile_corrections.py` may optionally read `knowledge/trace/gotchas.md` to cross-reference patterns

Do-not:
  - Auto-commit corrections (AGENTS.md rule #1)
  - Auto-create rules from corrections (human-mediated only)

Exit criteria:
  - [ ] `.fa/corrections.jsonl` exists
  - [ ] `python scripts/compile_corrections.py` runs and produces summary

Kill-check: empty corrections.jsonl → compile_corrections.py produces empty summary

### Step S21: Create frozen integrity guard (N-G1/N-G2)
Traces-to: G11, CT11
Depends-on: none | Parallelizable-with: S19, S20, S22, S23
Target liveness: L0→L3

Edit:
  - path: `scripts/frozen_guard.py`  symbol: NEW  change: create AST scanner

Do:
  1. Create `scripts/frozen_guard.py` (~80 lines):
     - `ast.walk` all `.py` files in `src/fa/`
     - Detect `object.__setattr__` calls (Call where func is Attribute with value=Name(id='object'), attr='__setattr__')
     - Verify `frozen=True` on all `@dataclass` in TCB files (authoring_tcb.py, feature_flags.py)
     - Verify no `__post_init__` on frozen dataclasses in TCB files (N-G2)
     - Produce `.fa/frozen_integrity_report.md`
     - Exit 1 if violations found
  2. Add to `just check` target
  3. Add test: create a test fixture with `object.__setattr__` → guard detects it

Exit criteria:
  - [ ] `python scripts/frozen_guard.py` exits 0 on current tree
  - [ ] `.fa/frozen_integrity_report.md` generated
  - [ ] Test passes

Kill-check: add `object.__setattr__(self, 'x', 1)` to a TCB file → guard exits 1

### Step S22: Add ADR-11-I1 stdlib-only check (G3) + max_chain_retries (G5)
Traces-to: G3 (G3 quick win), G5, CT12, CT13
Depends-on: none | Parallelizable-with: S19–S21, S23
Target liveness: L0→L3

Edit:
  - path: `scripts/check_tcb_stdlib.py` (NEW) or extension to `check_dead_flags.py`  change: add stdlib-only import scan
  - path: `src/fa/feature_flags.py`  symbol: `FeatureFlags`  change: add `max_chain_retries: int = 0`
  - path: `src/fa/inner_loop/coder_loop.py`  symbol: ProviderChainExhaustedError handler  change: add max_chain_retries guard

Do:
  1. Create `scripts/check_tcb_stdlib.py` (~20 lines):
     - Read `src/fa/authoring_tcb.py` imports
     - Check each import is in `sys.stdlib_module_names`
     - Exit 1 if any third-party import found
  2. Add `max_chain_retries: int = 0` to FeatureFlags dataclass (fail-fast default, user opts in via config.yaml)
  3. Add `"max_chain_retries": "int"` to `_KNOWN_FLAGS` in feature_flags.py
  4. Add `"max_chain_retries"` to `as_dict()` return dict in FeatureFlags
  5. Update `load_feature_flags()` to parse max_chain_retries from config.yaml:
     ```python
     max_chain_retries = (_get_int(found, "max_chain_retries", [], 0),)
     ```
  6. In coder_loop.py, add chain-retry logic with three requirements:
     a) Initialize `chain_exhaustion_count = 0` BEFORE the main turn loop (alongside `turn = 0`)
     b) In the ProviderChainExhaustedError handler (~line 1155):
        ```python
        chain_exhaustion_count += 1
        max_chain_retries = state.feature_flags.max_chain_retries if state.feature_flags is not None else 0
        if chain_exhaustion_count <= max_chain_retries:
            # Retry the entire provider chain
            logger.info("Provider chain exhausted, retrying (%d/%d)", chain_exhaustion_count, max_chain_retries)
            continue  # back to the top of the session loop
        # Else: max retries reached, fall through to existing finish() with chain_exhausted
        ```
     c) Session exits with `stop_reason="chain_exhausted"` only when `chain_exhaustion_count > max_chain_retries`
  7. Document the two-retry-mechanism relationship in coder_loop.py:
     - `transport_retries: int = 2` (ChainEntry in models.yaml) — HTTP-level retries within a single provider
     - `max_chain_retries: int = 0` (FeatureFlags in config.yaml) — session-level retries of entire provider chain
     - transport_retries fires first; chain walks to next entry on failure; max_chain_retries fires only after ALL entries exhausted

Do-not:
  - Conflate transport_retries with max_chain_retries — they operate at different scopes
  - Default max_chain_retries to anything other than 0 (fail-fast preserves current behavior)

Exit criteria:
  - [ ] `python scripts/check_tcb_stdlib.py` exits 0
  - [ ] FeatureFlags has `max_chain_retries` field with default=0
  - [ ] `_KNOWN_FLAGS` includes `"max_chain_retries": "int"`
  - [ ] Retry loop respects max_chain_retries (0 → no chain-level retries)
  - [ ] ProviderChainExhaustedError path logs retry count when max_chain_retries > 0

Kill-check: add `import requests` to authoring_tcb.py → check_tcb_stdlib.py exits 1
Kill-check: set max_chain_retries=0 → session exits on first ProviderChainExhaustedError (current behavior preserved)

### Step S23: Add compaction_end circuit-breaker visibility (G11)
Traces-to: G11, CT2
Depends-on: none | Parallelizable-with: S19–S22
Target liveness: L2→L3

Edit:
  - path: `src/fa/inner_loop/coder_loop.py`  symbol: circuit-breaker path  change: add loop_warn event on circuit breaker

Do:
  1. In the circuit-breaker path (where compaction fails repeatedly), add:
     ```python
     output.emit(
         OutputEvent(
             type="loop_warn",
             data={
                 "detector": "compaction_circuit_breaker",
                 "message": "Compaction circuit breaker triggered — context budget exceeded after compaction attempts",
             },
         )
     )
     ```

Exit criteria:
  - [ ] `grep -n "compaction_circuit_breaker" src/fa/inner_loop/coder_loop.py` finds the emit

Kill-check: remove the emit → test asserting loop_warn on circuit breaker fails

### Step S24: Error message audit for non-RuleResult code paths (G6)
Traces-to: G6 (reframed), CT4
Depends-on: none | Parallelizable-with: S19–S23
Target liveness: L2→L3

Edit:
  - path: `src/fa/providers/*.py`, `src/fa/cli.py`, `src/fa/inner_loop/coder_loop.py`  change: rewrite unstructured error messages

Do:
  1. Run audit:
     ```bash
     grep -rn 'raise ValueError\|raise RuntimeError\|raise ConfigurationError\|logger.error' src/fa/providers/ src/fa/cli.py src/fa/inner_loop/coder_loop.py | grep -v 'remediation\|expected\|got\|must be\|should be'
     ```
  2. For each hit (~30 sites), rewrite to include: (1) what happened, (2) why, (3) how to fix.
  3. Priority: ConfigurationError messages in chain.py and config.py are most impactful
     (users see these first when setup is wrong). Audit these first, then ValueError/RuntimeError.
  4. Example: `raise ValueError("invalid model")` → `raise ValueError(f"invalid model slug {model_slug!r}: expected format 'provider/model-name', got {model_slug!r}. Check ~/.fa/models.yaml role configuration.")`

Exit criteria:
  - [ ] Re-running the audit grep returns significantly fewer hits (target: 0 for critical paths)

### Step S25: Update SKILL.md I-TW-20 + document output_bus None window
Traces-to: G12
Depends-on: S11 | Parallelizable-with: S24

Edit:
  - path: `knowledge/skills/tests-writing/SKILL.md`  change: add I-TW-20 invariant
  - path: `src/fa/inner_loop/state.py`  change: add None-window docstring on output_bus

Do:
  1. Add I-TW-20 to SKILL.md:
     ```
     I-TW-20: Never mock dataclass config objects (ChainConfig, ChainEntry,
     CooldownRow, etc.). Use real instances via make_test_chain_config().
     Only mock objects with behavior (ProviderChain, Provider, Transport).
     Guard: scripts/check_no_mocked_dataclasses.py
     ```
  2. Add docstring to output_bus field in state.py documenting the None window.

Exit criteria:
  - [ ] I-TW-20 exists in SKILL.md
  - [ ] output_bus has docstring mentioning None window

### Step S26: Verify Phase 5
Depends-on: S19–S25 | Parallelizable-with: none

Do:
  1. All contract check scripts exit 0
  2. All new tests pass
  3. Commit as "feat: stats parsers, TRACE, frozen guard, error audit, dependency contract (F-7, F-8, F-9, G2, G3, G5, G6, G11, N-G1)"

Exit criteria:
  - [ ] All contract checks pass
  - [ ] All targeted tests pass

═══════════════════════════════════════════════════════════════════════
## 6. Verification plan (§9)
═══════════════════════════════════════════════════════════════════════

| CT# | Test class | Oracle (ranked) | Kill-check target | Two-sided | Path coverage |
|---|---|---|---|---|---|
| CT1 | C1 | event kind+fields | remove LogKind member → pyright fails | producer: log.append; consumer: check_log_kind_contract.py | P4 |
| CT2 | C1 | event kind+fields | remove output.emit for CONSOLE_MIRROR_KIND | producer: coder_loop emit; consumer: ConsoleRenderer handler | P5 |
| CT3 | C0p | exit code | remove LogKind member → script exits 1 | n/a (script) | all |
| CT4 | C0 | pyright passes | wrong type on field → pyright fails | n/a (type check) | P6–P7 |
| CT5 | C0 | set equality | miscategorized flag → test fails | n/a | B |
| CT6 | C1 | compaction behavior | compaction_threshold=None → compaction disabled | producer: coder_loop; consumer: compaction path | P8, H, I |
| CT7 | C0p | script exit code | unknown key in contract → exit 1 | n/a | P10 |
| CT8 | C0p | script exit code | add unknown dep → exit 1 | producer: check script; consumer: CI gate | P9, P10 |
| CT9 | C1 | session_meta content | remove set_meta call → empty metrics | producer: coder_loop incremental counter + session-end; consumer: fa stats --guardrail-metrics | P11 |
| CT10 | C0 | script output | empty corrections → empty summary | producer: human; consumer: compile_corrections.py | n/a |
| CT11 | C0p | script exit code | add object.__setattr__ → exit 1 | n/a | P14 |
| CT12 | C0p | script exit code | add non-stdlib import → exit 1 | n/a | all |
| CT13 | C1 | retry behavior | max_chain_retries=0 → 0 chain-level retries (current behavior) | producer: coder_loop ProviderChainExhaustedError handler; consumer: retry counter | P13 |

LIVE-PATH PROOF (primary product claim: LogKind type-safety):
  root: drive_session                    matrix: C (defaults)
  test: tests/test_check_log_kind_contract.py  oracle: event kind+fields (rank 1)
  kill-check: removing a log.append producer fails the contract check
  producer: coder_loop.py:log.append   consumer: ConsoleRenderer._handle_*
  paths-covered: 14/14 EventTypes + 30/30 LogKinds
  contract-check: check_log_kind_contract.py PASS required in CI
  efficiency: n/a (no provider call optimization claim)
  pyramid: A

LIVE-PATH PROOF (supply-chain TCB):
  root: check_dependency_contract.py    matrix: C (defaults)
  test: tests/test_check_dependency_contract.py  oracle: exit code (rank 2)
  kill-check: adding unknown dep to pyproject.toml exits 1
  producer: check script                consumer: CI gate
  paths-covered: 1/1
  contract-check: check_dependency_contract.py PASS required in CI
  pyramid: A

LIVE-PATH PROOF (frozen integrity guard):
  root: frozen_guard.py                 matrix: C (defaults)
  test: tests/test_frozen_guard.py      oracle: exit code (rank 2)
  kill-check: adding object.__setattr__ to TCB file exits 1
  producer: frozen_guard.py scan        consumer: CI gate
  paths-covered: 75 frozen dataclasses
  pyramid: A

═══════════════════════════════════════════════════════════════════════
## 7. Risks, rollback, open questions (§10)
═══════════════════════════════════════════════════════════════════════

### RISKS

| RK# | Risk | Mitigation | How detected |
|---|---|---|---|
| RK1 | P2 LogKind: adding type to append() causes type errors in unseen call sites | Contract check validates all producer sites; pyright enforces | pyright errors |
| RK2 | P3 typing: consumer expects `Any` and breaks on specific type | This is desired behavior — type safety catching bugs | pyright errors, test failures |
| RK3 | P4 F-10 compaction SSoT: removing flag gate changes behavior for configs that set compaction_enabled=False + threshold | Threshold=None already means "no compaction"; flag was redundant | grep confirms no production code reads context_compaction_enabled |
| RK4 | P4 G12 dependency TCB: blocking deps by default breaks CI for legitimate updates | `--advisory-deps` flag for intentional updates | CI failure on dep edit |
| RK5 | P5 stats parsers: elif chains may miss new log kinds | LogKind contract check catches new kinds not in the union | check_log_kind_contract.py |
| RK6 | P5 frozen guard: AST scanner may have false positives on test fixtures | Exclude CORPUS_PREFIXES and test directories | guard output |

### ROLLBACK

Each phase is independently revertable via git revert. No feature flags needed for additive changes.
- P1: revert commit (pure bug fix)
- P2: revert commit (additive: LogKind is type-only, contract check is a new script)
- P3: revert commit (type-only changes, no runtime behavior change)
- P4: F-10 is the only semantic change — rollback re-adds the flag gate. G12: `--advisory-deps` restores old behavior.
- P5: all additive (new scripts, new fields, new docs)

### OPEN QUESTIONS

BLOCKING: (none — all architectural decisions resolved)

NON-BLOCKING:
  Q1: Should the frozen_guard.py also scan `tests/` for `object.__setattr__` on TCB dataclasses?
    Default: no — test fixtures may legitimately test mutation. Scan `src/fa/` only.
  Q2: Should `check_dependency_contract.py` compare version ranges or exact versions?
    Default: ranges — exact versions would require updating the contract on every `uv lock`.
  Q3: Should corrections.jsonl entries be signed or hash-verified?
    Default: no — human-mediated entries, no integrity threat model for this file.

═══════════════════════════════════════════════════════════════════════
## 8. Research-note disposition (§11a)
═══════════════════════════════════════════════════════════════════════

| RN# | Note item | Verdict | Why | Anchor |
|---|---|---|---|---|
| RN1 | "7 EventTypes" (external) | **Reject** | FALSIFIED by source code: 14 EventTypes. All recommendations assuming 7-type model are void. | — |
| RN2 | "check_producer_consumer_contract.py doesn't exist" (external) | **Reject** | FALSIFIED: script exists, 206 lines, exits 0. | — |
| RN3 | "57.5% violation reduction" | **Reject** | UNVERIFIED — no retrievable source. Excluded from all yield estimates. | — |
| RN4 | "Auto-TRACE / unsupervised self-improvement" | **Reject** | Violates AGENTS.md rule #1 and project-overview.md §1.2.7. G2 is human-mediated only. | S20 |
| RN5 | "G6 error messages are already good" (external) | **Rewrite** | RuleResult messages are good; non-RuleResult code paths need work. Reframe G6 to non-RuleResult scope. | S24 |
| RN6 | "Import-linter as standalone control" (external) | **Defer** | Incomplete without N-G4 dynamic-import guard. Small codebase doesn't justify new dependency. | — |
| RN7 | "G3 ADR invariant enforcement needs dedicated control" (external) | **Rewrite** | Subtraction-first: existing mechanisms cover ~85%. One executable check for ADR-11-I1 suffices. | S22 |
| RN8 | "Context compiler" (external §8.1) | **Defer** | Manual skill consolidation achieves same ~20% reduction without new surface. | — |
| RN9 | "Behavioral contract compiler" (external §8.2) | **Defer** | C1 tests + contract check + mutmut already provide kill-check validation. | — |
| RN10 | "Frozen integrity guard" (external §8.3) | **Accept** | Low effort, high value, closes N-G1/N-G2, uses proven AST scanning pattern. | S21 |
| RN11 | "Dependency contract TCB" (external §8.4) | **Accept** | User chose full TCB pattern. Mirrors authoring_tcb.py manifest design. | S15 |
| RN12 | "G9 needs a batch script" (internal v2) | **Rewrite** | Reduction check showed SessionDatabase.set_meta() already exists. Extend, don't build new. | S9 |
| RN13 | "Discriminated union events in P6" (deep research) | **Defer** | User scope cap: stop at P5. P6 deferred to separate plan. | — |
| RN14 | "Property-typed SessionState" (deep research) | **Defer** | P6 scope. Phase 3 types the fields; properties are a later enhancement. | — |
| RN15 | "G4 inferential sensors (LLM-as-judge)" | **Defer** | High cost, high implementation effort. Not justified for early dev stage. | — |
| RN16 | "G12 just make blocking" (simplified) | **Rewrite** | User chose full TCB pattern with dependency_contract.toml. | S15 |
| RN17 | "Add read_flag() helper" (original plan) | **Reject** | Simpler to use direct access + None check. No new abstraction needed. | S13 |
| RN18 | "G13 runtime assertions in prod code" | **Rewrite** | Hybrid: CI-only for behavioral contracts + extend existing runtime guards. No new framework. | S16 |

═══════════════════════════════════════════════════════════════════════
## 9. Definition of Done (§11.3)
═══════════════════════════════════════════════════════════════════════

STATE:
  Before: 14 EventTypes with no LogKind type; 9 `Any | None` fields; 12 getattr fallbacks;
    advisory supply-chain; no guardrail metrics; no TRACE; no frozen guard.
  After: 14 EventTypes + 30 LogKinds both Literal-typed; 0 `Any | None` on SessionState
    (except pty_pool); 0 getattr fallbacks; blocking supply-chain TCB; session_meta metrics
    at session end; corrections.jsonl + compile_corrections.py; frozen_guard.py.
  Observe after-state by: `python scripts/check_log_kind_contract.py && python scripts/check_dependency_contract.py && python scripts/frozen_guard.py && python scripts/check_tcb_stdlib.py`

ARTIFACTS:

| Artifact | Path | Action | Owner S# |
|---|---|---|---|
| coder_loop.py (F-4 fix) | src/fa/inner_loop/coder_loop.py | edit | S1 |
| compactor.py (F-3 fix) | src/fa/inner_loop/compaction/compactor.py | edit | S2 |
| LogKind definition | src/fa/output.py | edit | S4 |
| CONSOLE_MIRROR_KINDS | src/fa/output.py | edit | S5 |
| EventLog.append typing | src/fa/inner_loop/state.py | edit | S6 |
| check_log_kind_contract.py | scripts/check_log_kind_contract.py | add | S7 |
| SKILL.md I-TW-17 update | knowledge/skills/tests-writing/SKILL.md | edit | S8 |
| session_meta metrics | src/fa/inner_loop/coder_loop.py | edit | S9 |
| fa stats --guardrail-metrics | src/fa/stats.py | edit | S9 |
| SessionState typed fields | src/fa/inner_loop/state.py | edit | S11 |
| FAIL_CLOSED/OPEN flags | src/fa/feature_flags.py | edit | S13 |
| getattr replacements | 6 files | edit | S13 |
| compaction SSoT | src/fa/inner_loop/coder_loop.py | edit | S14 |
| dependency_contract.toml | .fa/dependency_contract.toml | add | S15 |
| check_dependency_contract.py | scripts/check_dependency_contract.py | add | S15 |
| check_protected_paths.py update | scripts/check_protected_paths.py | edit | S15 |
| behavioral assertions | tests/test_inner_loop_loop_guard.py | edit | S16 |
| LOGIC-10 abnormal_stop | src/fa/inner_loop/coder_loop.py | edit | S17 |
| stats parsers | src/fa/stats.py | edit | S19 |
| corrections.jsonl | .fa/corrections.jsonl | add | S20 |
| compile_corrections.py | scripts/compile_corrections.py | add | S20 |
| frozen_guard.py | scripts/frozen_guard.py | add | S21 |
| check_tcb_stdlib.py | scripts/check_tcb_stdlib.py | add | S22 |
| max_chain_retries field | src/fa/feature_flags.py | edit | S22 |
| compaction circuit-breaker | src/fa/inner_loop/coder_loop.py | edit | S23 |
| error audit | providers/*.py, cli.py, coder_loop.py | edit | S24 |
| SKILL.md I-TW-20 | knowledge/skills/tests-writing/SKILL.md | edit | S25 |
| output_bus docstring | src/fa/inner_loop/state.py | edit | S25 |

CONTRACTS:
  CT1: PLANNED → IMPLEMENTED → VERIFIED (LogKind type-safety)
  CT2: PLANNED → IMPLEMENTED → VERIFIED (CONSOLE_MIRROR_KINDS dual-write)
  CT3: PLANNED → IMPLEMENTED → VERIFIED (check_log_kind_contract.py)
  CT4: PLANNED → IMPLEMENTED → VERIFIED (SessionState typed fields)
  CT5: PLANNED → IMPLEMENTED → VERIFIED (FAIL_CLOSED/OPEN flag categorization)
  CT6: PLANNED → IMPLEMENTED → VERIFIED (compaction SSoT)
  CT7: PLANNED → IMPLEMENTED → VERIFIED (dependency_contract.toml)
  CT8: PLANNED → IMPLEMENTED → VERIFIED (check_dependency_contract.py)
  CT9: PLANNED → IMPLEMENTED → VERIFIED (session_meta guardrail metrics)
  CT10: PLANNED → IMPLEMENTED → VERIFIED (corrections.jsonl TRACE)
  CT11: PLANNED → IMPLEMENTED → VERIFIED (frozen_guard.py)
  CT12: PLANNED → IMPLEMENTED → VERIFIED (ADR-11-I1 stdlib check)
  CT13: PLANNED → IMPLEMENTED → VERIFIED (max_chain_retries FeatureFlags — distinct from transport_retries)

Plan is DONE only when: all G# reach L3, all artifacts exist, LIVE-PATH PROOF blocks green,
  matrix/path coverage holds, non-goals respected, RN# all dispositioned.

═══════════════════════════════════════════════════════════════════════
## 10. Anti-theater + READY gate (§11.2, §11.4)
═══════════════════════════════════════════════════════════════════════

### Anti-theater checklist (§11.2)

  [x] Every referenced symbol verified via preflight or marked NEW
  [x] Every G# maps to ≥1 CT# and ≥1 S# and ≥1 verification (no orphans)
  [x] Every signal CT# has BOTH producer and consumer, or explicit defer
  [x] Every kill-check targets the PRODUCER, never the consumer alone
  [x] Path inventory (§4.1) has no uncovered path without explicit non-goal
  [x] Matrix (§4.2) has ≥1 covering step per row or explicit "N/A — why"
  [x] Dual-write channels verified consistent per path (CT2)
  [x] Fixtures/types in verification plan are honest (real types, not loosened mocks)
  [x] No vague verbs without concrete mechanism
  [x] Assumptions labeled (ASSUMPTION: ChainConfig always has context_limit/compaction_threshold)
  [x] Security contracts have adversarial case (CT8: unknown dep → HARD-BLOCK)
  [x] All ID references resolve — no dangling S#/CT#/G#/Q#/RN#/RK#

### READY gate (§11.4)

  [x] Preflight log present and non-trivial
  [x] Depth P3 declared and matches actual scope (cross-module, architectural)
  [x] Executive intent, non-goals, current/target state all concrete
  [x] All applicable contract subtypes (§6) present
  [x] Path + matrix coverage gates satisfied
  [x] Every step is file:symbol specific with exit criteria
  [x] Verification plan + LIVE-PATH PROOF present for every product claim
  [x] Anti-theater checklist fully holds
  [x] Research notes fully dispositioned (18 items, all Accept/Reject/Rewrite/Defer)
  [x] BLOCKING open-question set is EMPTY
  [x] All IDs resolve

**Status: READY**

═══════════════════════════════════════════════════════════════════════
## 11. Artifacts inventory
═══════════════════════════════════════════════════════════════════════

| Artifact | Path | Action | Owner S# |
|---|---|---|---|
| check_log_kind_contract.py | scripts/check_log_kind_contract.py | add | S7 |
| test_check_log_kind_contract.py | tests/test_check_log_kind_contract.py | add | S7 |
| dependency_contract.toml | .fa/dependency_contract.toml | add | S15 |
| check_dependency_contract.py | scripts/check_dependency_contract.py | add | S15 |
| test_check_dependency_contract.py | tests/test_check_dependency_contract.py | add | S15 |
| corrections.jsonl | .fa/corrections.jsonl | add | S20 |
| compile_corrections.py | scripts/compile_corrections.py | add | S20 |
| frozen_guard.py | scripts/frozen_guard.py | add | S21 |
| frozen_integrity_report.md | .fa/frozen_integrity_report.md | add (generated) | S21 |
| test_frozen_guard.py | tests/test_frozen_guard.py | add | S21 |
| check_tcb_stdlib.py | scripts/check_tcb_stdlib.py | add | S22 |

═══════════════════════════════════════════════════════════════════════
## 12. Corrective actions applied (v1→v2)
═══════════════════════════════════════════════════════════════════════

Source: REVIEW-guardrail-gap-closure.md + user decisions on B2/B3/B4.

| ID | Change | Affected steps | Status |
|---|---|---|---|
| CA1 | Replace S1 with: direct access + MIN_CONTEXT_LIMIT=32000 floor + warn on clamp | S1 | APPLIED |
| CA2 | Add TODO/ADR reference for adaptive context from API metadata (not in any PR, ADR-17 §B.5 is design target) | S1b (NEW) | APPLIED |
| CA3 | Rename `max_retry` → `max_chain_retries`, default=0, add to FeatureFlags (config.yaml), document relationship to `transport_retries=2` (ChainEntry/models.yaml) | S22, CT13 | APPLIED |
| CA4 | Move `subagent_spawning_enabled` from FAIL_CLOSED → FAIL_OPEN (don't spawn when unconfigured) | S13 | APPLIED |
| CA5 | Add incremental event counting (dict on state, updated on each log.append) instead of re-reading log at session end | S9 | APPLIED |
| CA6 | Add session_db writability check before set_meta (try/except, never crash at session end) | S9 | APPLIED |
| CA7 | Note that LogKind 30-member list is preflight estimate, verify with contract check before S4 implementation | S4 | APPLIED |
| CA8 | Cross-reference `.fa/corrections.jsonl` with existing `knowledge/trace/` infrastructure (codebase_map.json, gotchas.md) | S20 | APPLIED |
| CA9 | Explicitly state: don't delete `context_compaction_enabled` field from frozen dataclass, just stop reading it | S14 | APPLIED |

═══════════════════════════════════════════════════════════════════════
## 13. Change history
═══════════════════════════════════════════════════════════════════════

### v1→v2: Production-readiness review corrections (CA1–CA9 + B2/B3/B4)

| ID | Change | Affected steps |
|---|---|---|
| CA1 | Replace S1 with: direct access + MIN_CONTEXT_LIMIT=32000 floor + warn on clamp | S1 |
| CA2 | Add TODO/ADR reference for adaptive context from API metadata (not in any PR, ADR-17 §B.5 is design target) | S1b (NEW) |
| CA3 | Rename max_retry → max_chain_retries, default=0, add to FeatureFlags (config.yaml), document relationship to transport_retries=2 (ChainEntry/models.yaml) | S22, CT13 |
| CA4 | Move subagent_spawning_enabled from FAIL_CLOSED → FAIL_OPEN (don't spawn when unconfigured) | S13 |
| CA5 | Add incremental event counting (dict on state, updated on each log.append) instead of re-reading log at session end | S9 |
| CA6 | Add session_db writability check before set_meta (try/except, never crash at session end) | S9 |
| CA7 | Note that LogKind 30-member list is preflight estimate, verify with contract check before S4 implementation | S4 |
| CA8 | Cross-reference .fa/corrections.jsonl with existing knowledge/trace/ infrastructure (codebase_map.json, gotchas.md) | S20 |
| CA9 | Explicitly state: don't delete context_compaction_enabled field from frozen dataclass, just stop reading it | S14 |

### v2→v3: Deep review gap closure (I1–I12)

| ID | Change | Affected steps |
|---|---|---|
| I1 | Add compaction_warning producer (was dead code in LogKind — no live producer) | S6 |
| I2+I9 | Move kind_counts to EventLog (not SessionState) for thread safety and ownership | S9, CT9 |
| I3 | Expand S13 to cover all 18 getattr(session, ...) sites, not just feature_flags | S13 |
| I4 | Use kind="telemetry" for MIN_CONTEXT_LIMIT clamp warning (not context_budget_warn) | S1 |
| I5 | S22: specify chain_exhaustion_count init before loop, increment in handler, exit only when count > max | S22 |
| I6 | Dynamic kind construction (spawn_subagent.py) — deferred to next implementation plan | S6 |
| I7 | S3: reference S1 kill-check pattern (context_limit=100 → clamped to 32000) | S3 |
| I8 | context_compaction_enabled: cannot prune (10+ test sites), keep in FAIL_CLOSED with deprecation note | S13, S14 |
| I10 | S24: add ConfigurationError to error audit grep, prioritize chain.py/config.py | S24 |
| I11 | Add FAIL_UNDEFINED_DEFAULTS dict for safe defaults on uncategorized new fields | S13 |
| I12 | Add chain_exhaustion_events to session_meta metrics payload | S9 |

### v3→v4: User Q1–Q5 decisions

| ID | Change | Affected steps |
|---|---|---|
| Q1 | Add bash_executor: BashExecutor | None = None as proper field on SessionState (no circular dep risk). Eliminates ALL getattr(session, ...) from S13 | S11, S13 |
| Q2 | Dedicated chain_exhaustion_count counter on EventLog (not derived from kind_counts) | S9, CT9 |
| Q3 | Remove FAIL_UNDEFINED_DEFAULTS — test is the enforcement, no unused reference data | S13 |
| Q4 | compaction_warning fires in BOTH enabled and disabled cases (single observation point for compaction-level pressure) | S6 |
| Q5 | max_chain_retries appears in as_dict() and _KNOWN_FLAGS (user-configurable via config.yaml) | S22 |
