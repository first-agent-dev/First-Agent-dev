# Gap-Closing Implementation Plan — PR #53 Observability + FA Provider Chain

**Date**: 2026-07-19
**Status**: IMPLEMENTATION PLAN — Ready for phased execution
**Principle**: Less surface, more simple and robust, all intended functional preserved.
**Mode**: MAX effort, verifiable steps, each phase independently shippable.

---

## User Decisions (Confirmed)

| Finding | Decision | Rationale |
|---------|----------|-----------|
| F-1 | Accept disjoint, define explicit console-mirror subset | Less surface — unify would require 30→13 or 13→30, both increase surface. Accept the two systems serve different purposes, formalize which log kinds MUST have OutputEvent mirrors. |
| F-2 | `LogKind = Literal[...]` + second contract check | Same structural fix that prevented "not wired" bugs on OutputEvent side, now applied to log.append side. Simple, robust. |
| F-3 | Type `compactor_chain` as `ProviderChain | None` + fix dead fallback | Senior engineer: the double-getattr and dead "compactor" fallback are bugs. Type the field properly and fix the model_slug resolution. |
| F-5 | Option A — type all 9 fields with actual types + `from __future__ import annotations` | Most surface reduction: eliminates 19 getattr workarounds, gives Pylance enforcement. `from __future__ import annotations` already in state.py so forward refs work. |
| F-6 | Safety-critical flags fail CLOSED, convenience flags fail OPEN | Budget/compaction/sandbox → fail closed. Telemetry/worktree/output → fail open. Explicit, auditable. |
| F-10 | Single source of truth: `compaction_threshold is not None` | Most semantically fitting — the threshold IS the declaration of intent to compact. The feature flag is redundant. Remove the flag gate, derive "enabled" from threshold. |

---

## Phase 0: Pre-requisites (No code changes)

### Step 0.1: Capture baseline test count
```bash
cd /home/user/First-Agent-dev && python -m pytest --tb=no -q 2>&1 | tail -1
```
Record the number. Every subsequent step must preserve or increase it.

### Step 0.2: Verify existing contract checks pass
```bash
python scripts/check_producer_consumer_contract.py  # must exit 0
python scripts/check_no_mocked_dataclasses.py         # must exit 0
```

---

## Phase 1: F-4 + F-3 — Logic Error Fixes (No architectural changes, pure bug fixes)

**Goal**: Fix two concrete logic errors that can cause silent misbehavior.

### Step 1.1: Fix F-4 — `or 150000` swallows zero

**File**: `src/fa/inner_loop/coder_loop.py`

**Current** (line ~409):
```python
context_limit = getattr(provider_chain.config, "context_limit", 150000) or 150000
```

**New**:
```python
context_limit = provider_chain.config.context_limit
```

**Rationale**: ChainConfig always has `context_limit: int = 150000`. The getattr fallback is dead code. The `or 150000` is a logic trap (swallows zero). Direct attribute access is both correct and simpler.

**Same line fix for compaction_threshold**:
```python
compaction_threshold = getattr(provider_chain.config, "compaction_threshold", None)
```
→
```python
compaction_threshold = provider_chain.config.compaction_threshold
```

**Tests**: Run `pytest tests/ -k "context_limit or budget" --tb=short`. Any test that relied on `context_limit=0` being swallowed to 150000 should now be updated to use the correct value.

### Step 1.2: Fix F-3 — Type `compactor_chain` properly + fix dead fallback

**File**: `src/fa/inner_loop/compaction/compactor.py`

**Current**:
```python
class FullLLMCompactor:
    def __init__(self, compactor_chain: Any | None = None):
        self.compactor_chain = compactor_chain

    def compact(self, history_text: str) -> str:
        ...
        model_slug = getattr(getattr(self.compactor_chain, "config", None), "model", "compactor")
```

**New**:
```python
from fa.providers.chain import ProviderChain


class FullLLMCompactor:
    def __init__(self, compactor_chain: ProviderChain | None = None):
        self.compactor_chain = compactor_chain

    def compact(self, history_text: str) -> str:
        ...
        if self.compactor_chain is not None:
            model_slug = self.compactor_chain.config.model
        else:
            model_slug = ""
```

**Rationale**: The double-getattr is a bug. The "compactor" fallback is dead code (never reached in practice because config always exists on a ProviderChain). If `compactor_chain` is `None`, the `if not self.compactor_chain` guard already catches it and falls back to local truncation. If `compactor_chain` is set but its config.model is empty string, that's a config validation error that should surface, not be silently hidden.

**Also update the call site** in `coder_loop.py`:
The `compactor_chain: ProviderChain | None = None` parameter is already correctly typed in `drive_session` and `_drive_session_inner`. No change needed there.

**Tests**: Run `pytest tests/ -k "compactor or compaction" --tb=short`.

### Step 1.3: Verify Phase 1

```bash
python -m pytest --tb=short -q 2>&1 | tail -1
python scripts/check_producer_consumer_contract.py
python scripts/check_no_mocked_dataclasses.py
```

All must pass. Commit.

---

## Phase 2: F-2 + F-1 — LogKind Type + Console-Mirror Subset + Contract Check

**Goal**: Add structural type safety to log.append(kinds), define which log kinds are console-mirrored, add a second contract check.

### Step 2.1: Create `LogKind = Literal[...]` in `src/fa/output.py`

**Add to `src/fa/output.py`** (after EventType definition):

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
    "compaction_warning",
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

**Export**: Add `LogKind` to `__all__`.

**Note on completeness**: This is the exhaustive set of 30 log kinds found by `grep -rn "kind=" src/fa/ --include="*.py"`. If a new kind is added, the contract check (Step 2.4) will flag it.

### Step 2.2: Define console-mirror subset (F-1 decision)

**Add to `src/fa/output.py`**:

```python
# Console-mirror subset: log kinds that MUST also emit an OutputEvent.
# These are the events the operator needs to see in real-time on stderr.
# Rationale: EventLog is the audit trail (30 kinds, machine-readable).
# EventBus is the console display (14 types, human-readable).
# Only these log kinds require dual-write; the rest are audit-only.
CONSOLE_MIRROR_KINDS: frozenset[LogKind] = frozenset(
    {
        "context_budget_warn",  # → context_warn
        "context_budget_hard_stop",  # → context_warn (critical)
        "compaction_stage2_start",  # → compaction_start
        "compaction_stage2_done",  # → compaction_end
        "compaction_stage2_error",  # → compaction_end (error)
        "compaction_stage3_start",  # → compaction_start
        "compaction_stage3_done",  # → compaction_end
        "compaction_stage3_error",  # → compaction_end (error)
        "compaction_circuit_breaker",  # → compaction_end (circuit_breaker)
        "tool_call",  # → tool_call (shared name)
        "subagent_spawn_done",  # → subagent_end
        "subagent_spawn_fail",  # → subagent_end
        "run_stopped",  # → session_end / hook_deny / api_retry
    }
)
```

This replaces the vague I-TW-17 invariant with a precise, auditable enumeration.

### Step 2.3: Annotate `EventLog.append` parameter with `LogKind`

**File**: `src/fa/inner_loop/state.py`

**Current**:
```python
def append(
    self,
    *,
    actor: str,
    kind: str,
    ...
) -> TraceEvent:
```

**New**:
```python
from fa.output import LogKind

def append(
    self,
    *,
    actor: str,
    kind: LogKind,
    ...
) -> TraceEvent:
```

**Impact**: All 30+ call sites of `log.append(kind=...)` already use the correct string literals. Pylance/pyright will now validate them at lint time. No runtime change.

**TraceEvent.kind** also needs updating:
```python
@dataclass(frozen=True)
class TraceEvent:
    ...
    kind: LogKind  # was: str
    ...
```

Wait — `TraceEvent.kind` is written to JSONL as a string. The `LogKind` type is just a type annotation; at runtime it's still a string. This is safe.

However, `read_all()` reconstructs `TraceEvent` from JSONL/DB where `kind` comes back as `str`. We need to keep `TraceEvent.kind` as `str` (because JSONL round-trip loses the Literal constraint) and only enforce the type at the `append()` boundary.

**Revised approach**: Keep `TraceEvent.kind: str` (it's a data container that may come from disk). Only type `EventLog.append(kind: LogKind)` as the enforcement point. The contract check validates that producers use valid LogKind values.

Actually, the cleanest approach: add the type to `append()` only. `TraceEvent` remains `kind: str` for deserialization compatibility. The contract check (Step 2.4) validates all producer sites use valid kinds.

### Step 2.4: Create `scripts/check_log_kind_contract.py`

**Architecture** (mirrors `check_producer_consumer_contract.py`):

1. Extract all `LogKind` literals from `output.py` (the canonical registry)
2. Find all `log.append(kind=...)` calls in production code under `src/fa/`
3. For each call, verify the kind string is in the LogKind set
4. For each LogKind in CONSOLE_MIRROR_KINDS, verify there is a corresponding `output.emit(OutputEvent(type=...))` in the same module
5. For each LogKind, verify there is at least one C1 test that exercises it
6. Report gaps as FAIL with actionable messages

**Exit behavior**: Exit 1 if any gaps found. Exit 0 if all contracts satisfied.

**Wire into CI**: Add to `justfile` and `Makefile` alongside the existing contract check.

### Step 2.5: Update SKILL.md I-TW-17 invariant

Replace the current vague dual-write invariant with:

```
I-TW-17: CONSOLE_MIRROR_KINDS (in output.py) defines which log.append kinds
MUST also emit an OutputEvent. Every kind in that set must have both a
log.append producer and an output.emit producer on the same code path.
The check_log_kind_contract.py script validates this.
```

### Step 2.6: Verify Phase 2

```bash
python -m pytest --tb=short -q 2>&1 | tail -1
python scripts/check_log_kind_contract.py          # new script
python scripts/check_producer_consumer_contract.py  # existing
python scripts/check_no_mocked_dataclasses.py        # existing
```

All must pass. Commit.

---

## Phase 3: F-5 — Type All 9 `Any | None` Fields on SessionState

**Goal**: Replace 9 `Any | None` fields with proper types, using `from __future__ import annotations` for forward references.

### Step 3.1: Add TYPE_CHECKING imports to `state.py`

**File**: `src/fa/inner_loop/state.py` (already has `from __future__ import annotations`)

**Add to the TYPE_CHECKING block**:
```python
if TYPE_CHECKING:
    from fa.blackboard.blackboard import Blackboard
    from fa.inner_loop.artifacts import ArtifactStore
    from fa.inner_loop.transaction import Transaction
    from fa.observability.redaction import SecretRedactor
    from fa.output import EventBus
    from fa.telemetry.telemetry import TelemetryLogger
    from fa.workspace.worktree_manager import WorktreeManager
```

Note: `SessionDatabase` is already imported at the top of the file (non-conditional). `PtyPool` requires a conditional import since `fa.runtime` may not be available.

### Step 3.2: Replace the 9 `Any | None` fields

**Current**:
```python
transaction: Any | None = None
blackboard: Any | None = None
telemetry: Any | None = None
feature_flags: Any | None = None
artifact_store: Any | None = None
pty_pool: Any | None = None
worktree_manager: Any | None = None
session_db: Any | None = None
output_bus: Any | None = None
```

**New**:
```python
transaction: Transaction | None = None
blackboard: Blackboard | None = None
telemetry: TelemetryLogger | None = None
feature_flags: FeatureFlags | None = None
artifact_store: ArtifactStore | None = None
pty_pool: Any | None = None  # PtyPool — kept as Any because fa.runtime is optional
worktree_manager: WorktreeManager | None = None
session_db: SessionDatabase | None = None
output_bus: EventBus | None = None
```

**Note on `pty_pool`**: `fa.runtime.PtyPool` is in an optional module. We keep it as `Any | None` for now, with a comment explaining why. A future PR can add it to TYPE_CHECKING if `fa.runtime` stabilizes.

**Note on `FeatureFlags`**: Already imported at module level in `state.py` (the `__post_init__` method imports it). We need to move it to TYPE_CHECKING or import at the top.

Actually, looking at `state.py`, `FeatureFlags` is imported inside `__post_init__` with `from fa.feature_flags import FeatureFlags`. We need to add it to `TYPE_CHECKING` for the type annotation, but the runtime import inside `__post_init__` can stay (it's the actual runtime usage).

### Step 3.3: Update consumer sites to use typed access

With proper types, Pylance will enforce None checks. Key sites to update:

**In `state.py` `__post_init__`**:
- `getattr(self.feature_flags, "blackboard_enabled", True)` → `self.feature_flags.blackboard_enabled if self.feature_flags is not None else True` (but this will be addressed in Phase 4 with the fail-closed/open pattern)

**In `spawn_subagent.py`**:
- `getattr(session, "output_bus", None)` → `session.output_bus` (Pylance enforces None check)

**In `coder_loop.py`**:
- `getattr(state.feature_flags, "context_budget_enabled", True)` → `state.feature_flags.context_budget_enabled if state.feature_flags is not None else True` (Phase 4 will refine this)

**In `loop.py`**:
- `getattr(state.feature_flags, "tool_batching_enabled", True)` → `state.feature_flags.tool_batching_enabled if state.feature_flags is not None else True` (Phase 4)

**In `subagent_runner.py`**:
- `ff = getattr(session, "feature_flags", None)` → `ff = session.feature_flags` (Pylance: `SessionState.feature_flags` is `FeatureFlags | None`)

**Strategy**: Don't replace ALL getattr sites in Phase 3 — just the ones that become obviously unnecessary with the new types. The fail-closed/open pattern (Phase 4) will handle the rest systematically.

### Step 3.4: Update `make_session_state()` in test fixtures

**File**: `tests/fixtures/session_wiring.py`

Update the factory to accept and set the now-typed fields properly. Since `from __future__ import annotations` is used, type annotations are strings and don't require the actual imports at test time.

### Step 3.5: Verify Phase 3

```bash
python -m pytest --tb=short -q 2>&1 | tail -1
python scripts/check_log_kind_contract.py
python scripts/check_producer_consumer_contract.py
python scripts/check_no_mocked_dataclasses.py
```

All must pass. Commit.

---

## Phase 4: F-6 + F-10 + P1 — Fail-Closed/Open + Compaction SSoT + Remove getattr Duplicated Defaults

**Goal**: Fix the fail-open safety flag pattern, establish single source of truth for compaction, and eliminate all `getattr(flags, "field", default)` duplicated defaults in production code.

### Step 4.1: Define safety-critical vs convenience flags

**Add to `src/fa/feature_flags.py`** (after the FeatureFlags class):

```python
# Fail-closed safety flags: if the flag cannot be read, assume the
# RESTRICTIVE setting. These flags control resource limits or safety
# boundaries — a misread should err on the side of caution.
FAIL_CLOSED_FLAGS: frozenset[str] = frozenset(
    {
        "context_budget_enabled",  # If unreadable, budget IS enabled → restrictive
        "context_compaction_enabled",  # If unreadable, compaction OFF → restrictive (see F-10)
        "subagent_spawning_enabled",  # If unreadable, spawning OFF → restrictive
    }
)

# Fail-open convenience flags: if the flag cannot be read, assume the
# PERMISSIVE setting. These flags control optional features — a misread
# should not break functionality.
FAIL_OPEN_FLAGS: frozenset[str] = frozenset(
    {
        "blackboard_enabled",  # If unreadable, blackboard ON → permissive
        "telemetry_enabled",  # If unreadable, telemetry ON → permissive
        "tool_batching_enabled",  # If unreadable, batching ON → permissive
        "pty_pool_max_size",  # If unreadable, default size → permissive
        "offload_threshold",  # If unreadable, default threshold → permissive
        "worktree_mode",  # If unreadable, shared mode → permissive
        "fts_db_path",  # If unreadable, default path → permissive
        "prompt_caching",  # If unreadable, caching ON → permissive
        "max_subagent_spawns_per_session",  # If unreadable, default limit → permissive
        "blackboard_filtered_history_include_plans",  # If unreadable, no plans → permissive
    }
)
```

### Step 4.2: Create `read_flag()` helper

**Add to `src/fa/feature_flags.py`**:

```python
def read_flag(
    flags: FeatureFlags,
    name: str,
) -> Any:
    """Read a feature flag with fail-closed or fail-open semantics.

    Safety-critical flags (in FAIL_CLOSED_FLAGS) raise on read failure
    so the caller can apply the restrictive default. Convenience flags
    (in FAIL_OPEN_FLAGS) return the FeatureFlags dataclass default on
    read failure.
    """
    try:
        return getattr(flags, name)
    except AttributeError:
        if name in FAIL_CLOSED_FLAGS:
            raise  # Caller must handle with restrictive default
        # Fail-open: return the dataclass default
        for f in fields(FeatureFlags):
            if f.name == name:
                return f.default
        raise  # Unknown flag — should not happen
```

**Wait — simpler approach**: Since `FeatureFlags` is a frozen dataclass and `flags` is always a `FeatureFlags` instance (after Phase 3's typing), `getattr` will never fail with `AttributeError` on a valid field name. The real risk is:

1. `state.feature_flags` is `None` — the lazy initializer failed
2. The field name is wrong (typo) — but with `LogKind`-style Literal types, this is caught by Pylance

The actual fix is simpler: replace `getattr(flags, "field", default)` with direct `flags.field` access, and handle the `flags is None` case explicitly with the correct default for each flag.

### Step 4.3: Replace all `getattr(flags, "field", default)` with direct access

**Comprehensive list of 12 production sites**:

| # | File | Line | Current | New |
|---|------|------|---------|-----|
| 1 | `coder_loop.py` | ~632 | `getattr(state.feature_flags, "context_budget_enabled", True)` | `state.feature_flags.context_budget_enabled if state.feature_flags is not None else True` |
| 2 | `coder_loop.py` | ~661 | `getattr(state.feature_flags, "context_compaction_enabled", False)` | REMOVED (see F-10 Step 4.5) |
| 3 | `loop.py` | ~458 | `getattr(state.feature_flags, "tool_batching_enabled", True)` | `state.feature_flags.tool_batching_enabled if state.feature_flags is not None else True` |
| 4 | `spawn_subagent.py` | ~32 | `getattr(session.feature_flags, "subagent_spawning_enabled", False)` | `session.feature_flags.subagent_spawning_enabled if session.feature_flags is not None else False` |
| 5 | `state.py` | ~347 | `getattr(self.feature_flags, "blackboard_enabled", True)` | `self.feature_flags.blackboard_enabled if self.feature_flags is not None else True` |
| 6 | `state.py` | ~374 | `getattr(self.feature_flags, "telemetry_enabled", True)` | `self.feature_flags.telemetry_enabled if self.feature_flags is not None else True` |
| 7 | `state.py` | ~414 | `getattr(self.feature_flags, "pty_pool_max_size", 2)` | `self.feature_flags.pty_pool_max_size if self.feature_flags is not None else 2` |
| 8 | `state.py` | ~513 | `getattr(self.feature_flags, "offload_threshold", 8000)` | `self.feature_flags.offload_threshold if self.feature_flags is not None else 8000` |
| 9 | `profiles.py` | ~209 | `getattr(ff, "fts_db_path", ".fa/fts.db")` | `ff.fts_db_path` (ff is always a FeatureFlags instance from `load_feature_flags_from_path()`) |
| 10 | `tools/__init__.py` | ~157 | `getattr(ff, "fts_db_path", ".fa/fts.db")` | `ff.fts_db_path` (same reason) |
| 11 | `subagent_runner.py` | ~76 | `ff = getattr(session, "feature_flags", None)` | `ff = session.feature_flags` (Phase 3 already typed it) |
| 12 | `subagent_runner.py` | ~86 | `getattr(ff, "max_subagent_spawns_per_session", None)` | `ff.max_subagent_spawns_per_session if ff is not None else None` |

### Step 4.4: Fail-closed pattern for safety-critical flags

**For safety-critical flags**, the pattern is:

```python
# SAFETY-CRITICAL: fail CLOSED — if flags unavailable, assume restrictive
budget_enabled = True  # restrictive default = budget IS enabled
if state.feature_flags is not None:
    budget_enabled = state.feature_flags.context_budget_enabled
```

This replaces the try/except/pass pattern. The `if is not None` check is explicit and type-safe. The default is the restrictive setting.

Apply to:
- `context_budget_enabled` — restrictive default = `True` (budget enabled)
- `subagent_spawning_enabled` — restrictive default = `False` (spawning disabled)

### Step 4.5: F-10 — Remove `context_compaction_enabled` flag gate, derive from threshold

**The single source of truth**: `compaction_threshold is not None` means compaction is configured and enabled. The feature flag `context_compaction_enabled` is redundant.

**Current coder_loop.py** (compaction gate):
```python
compaction_enabled = False
try:
    if state.feature_flags is not None:
        compaction_enabled = getattr(state.feature_flags, "context_compaction_enabled", False)
except Exception:
    pass
```

**New**:
```python
# Compaction is enabled when the chain configures a compaction threshold.
# Single source of truth: ChainConfig.compaction_threshold (int | None).
# If threshold is None, no compaction was configured for this role.
compaction_enabled = compaction_threshold is not None
```

Note: `compaction_threshold` is already available in scope from the `budget = ContextBudget(limit_tokens=context_limit, configured_threshold=compaction_threshold)` line earlier in the function.

**Feature flag deprecation**: Keep `FeatureFlags.context_compaction_enabled` in the dataclass for backward compatibility, but mark it as deprecated with a comment:

```python
context_compaction_enabled: bool = False  # DEPRECATED: derive from ChainConfig.compaction_threshold instead
```

No consumer should read this flag anymore. The contract check will validate no production code references it.

**Update `check_log_kind_contract.py`** to flag any remaining usage of `context_compaction_enabled` in production code.

### Step 4.6: Verify Phase 4

```bash
python -m pytest --tb=short -q 2>&1 | tail -1
python scripts/check_log_kind_contract.py
python scripts/check_producer_consumer_contract.py
python scripts/check_no_mocked_dataclasses.py
```

All must pass. Commit.

---

## Phase 5: F-7 + F-8 + F-9 + NEW items — Coverage Gaps + Documentation + Small Fixes

**Goal**: Close remaining observability gaps, update documentation, fix small items.

### Step 5.1: F-7 — Add missing log kind parsers to `fa stats`

**File**: `src/fa/stats.py`

Add parsing for 12 currently-invisible log kinds. Add new dataclasses for ones that need structured representation:

```python
@dataclass(frozen=True)
class CompactionTiming:
    """Start-to-done timing for a compaction stage."""

    stage: int
    start_ts: str = ""
    done_ts: str = ""
    ok: bool = True
    tokens_before: int = 0
    tokens_after: int = 0
    error: str = ""


@dataclass(frozen=True)
class CircuitBreakerEvent:
    """Compaction circuit breaker trigger."""

    message: str = ""


@dataclass(frozen=True)
class RecoveryAction:
    """Recovery action taken by FailureClassifierObserver."""

    tool: str = ""
    error_type: str = ""
    action: str = ""


@dataclass(frozen=True)
class VerificationEvent:
    """Verifier result from VerifierObserver."""

    tool: str = ""
    verdict: str = ""
    detail: str = ""


@dataclass(frozen=True)
class CostObservation:
    """Cost tracking observation from CostGuardian."""

    cumulative_usd: float = 0.0
    budget_usd: float = 0.0
    pct: float = 0.0


@dataclass(frozen=True)
class ModelMessage:
    """Per-turn model I/O record."""

    turn: int
    in_tokens: int = 0
    out_tokens: int = 0
    finish_reason: str = ""
    text_preview: str = ""  # First 200 chars


@dataclass(frozen=True)
class UserMessage:
    """User message record."""

    text_preview: str = ""  # First 200 chars


@dataclass(frozen=True)
class AuditEvent:
    """Hook audit observation."""

    hook: str = ""
    decision: str = ""


@dataclass(frozen=True)
class TelemetryEvent:
    """Telemetry logging event."""

    tool_name: str = ""
    ok: bool = True
```

Add these fields to `SessionAnalytics`:
```python
compaction_timings: list[CompactionTiming] = field(default_factory=list)
circuit_breaker_events: list[CircuitBreakerEvent] = field(default_factory=list)
recovery_actions: list[RecoveryAction] = field(default_factory=list)
verification_events: list[VerificationEvent] = field(default_factory=list)
cost_observations: list[CostObservation] = field(default_factory=list)
model_messages: list[ModelMessage] = field(default_factory=list)
user_messages: list[UserMessage] = field(default_factory=list)
audit_events: list[AuditEvent] = field(default_factory=list)
telemetry_events: list[TelemetryEvent] = field(default_factory=list)
```

Add `elif` branches in `parse_session()` for each new kind.

Add rendering sections in `render_session()` for the new data.

### Step 5.2: F-8 — Update SKILL.md §5 + add I-TW-20 invariant

**Add to SKILL.md §5 (Type-honest fixtures)**:

```
I-TW-20: Never mock dataclass config objects (ChainConfig, ChainEntry,
CooldownRow, ChainAttemptRecord, RequestInfo, ResponseInfo, TransportResponse).
Use real instances via make_test_chain_config() / make_test_chain_entry().
Only mock objects with behavior (ProviderChain, Provider, Transport).
Guard: scripts/check_no_mocked_dataclasses.py
```

Update the "Prefer instead" table to generalize:
```
| dataclass config | Real instance via factory function | mock the behavior, not the data |
```

### Step 5.3: F-9 — Document the `output_bus` None window

**Add to `src/fa/inner_loop/state.py` docstring on `output_bus` field**:

```python
output_bus: EventBus | None = None  # Set by cli.py AFTER construction.
# There is a brief None window between SessionState() construction and
# the `state.output_bus = output_bus` assignment in cli.py (~L1925).
# During this window, emit calls in spawn_subagent.py gracefully skip
# (the getattr guard). This is acceptable: the window covers only the
# SessionState.__post_init__ lazy-initialization phase, which does not
# spawn subagents. If the bus MUST be available at construction time,
# pass it via the constructor parameter.
```

### Step 5.4: NEW-8 — Move `import sqlite3` to top of state.py

**Current**: `import sqlite3` inside `_initial_next_id()` method body.

**New**: Move to top-level imports. `sqlite3` is a stdlib module, always available. No reason for lazy import.

### Step 5.5: LOGIC-16 — Add `EventLog.count()` and `EventLog.tail(n)` methods

**Problem**: `read_all()` is O(n²) — called multiple times per session, each call reads ALL events from DB/JSONL.

**Solution**: Add efficient query methods:

```python
def count(self) -> int:
    """Return total event count without deserializing all rows."""
    if self.session_db is not None:
        try:
            return self.session_db.count_events()
        except Exception:
            pass
    # Fallback: count JSONL lines
    ...


def tail(self, n: int = 5) -> tuple[TraceEvent, ...]:
    """Return the last n events efficiently."""
    if self.session_db is not None:
        try:
            rows = self.session_db.read_event_rows_tail(n)
            return tuple(self._row_to_trace_event(row) for row in rows)
        except Exception:
            pass
    # Fallback: read all and slice
    events = self.read_all()
    return events[-n:] if n < len(events) else events
```

Add `count_events()` and `read_event_rows_tail(n)` to `SessionDatabase`.

Then replace the one known O(n²) call site in `loop.py` (the `state.log.read_all()[-5:]` scan for parallel AFTER_TOOL_EXEC stop signal) with `state.log.tail(5)`.

### Step 5.6: LOGIC-10 — Add actionable console guidance for `abnormal_stop`

**File**: `src/fa/inner_loop/coder_loop.py`

When `finish_reason` is abnormal (length, content_filter), add a hint:

```python
# LOGIC-10: actionable console guidance for abnormal stops
if response.finish_reason == "length":
    hint = "Output truncated (finish_reason=length). Consider increasing max_tokens or simplifying the task."
elif response.finish_reason == "content_filter":
    hint = "Output blocked by content filter (finish_reason=content_filter). Review the prompt for policy violations."
else:
    hint = f"Unexpected finish_reason: {response.finish_reason}"

state.log.append(
    actor="runtime",
    kind="run_stopped",
    content={
        "reason": f"abnormal_stop:{response.finish_reason}",
        "hint": hint,
    },
)
if output is not None:
    output.emit(
        OutputEvent(
            type="loop_warn",
            turn=turn,
            max_turns=max_turns,
            data={"detector": "abnormal_stop", "message": hint},
        ),
    )
```

### Step 5.7: Verify Phase 5

```bash
python -m pytest --tb=short -q 2>&1 | tail -1
python scripts/check_log_kind_contract.py
python scripts/check_producer_consumer_contract.py
python scripts/check_no_mocked_dataclasses.py
```

All must pass. Commit.

---

## Phase 6: Deep Failure-Mode Closure — Discriminated Union Events + Property-Typed State

**Goal**: Apply the "Parse, Don't Validate" + "Make Illegal States Unrepresentable" patterns to structurally prevent the F-2 and F-5 failure modes from recurring when AI agents add new features.

**See**: `knowledge/research/deep-research-failure-mode-closure-2026-07-19.md` for full research rationale and references.

This phase is **additive and non-breaking** — it introduces typed event schemas alongside the existing `kind: str` / `content: dict` system, then migrates consumers incrementally.

### Step 6.1: Create `src/fa/events.py` — Typed event payload classes

For each of the 30 LogKind values, define a typed payload class:

```python
"""Typed event schemas — discriminated union over log kinds.

Parse-Don't-Validate boundary: converts raw TraceEvent (kind: str, content: dict)
into typed variants where the payload shape is guaranteed by construction.

When an AI agent adds a new log kind, it MUST:
1. Define a new *Payload class with kind: Literal["new_kind"]
2. Add the class to KnownLogEvent union
3. Add the kind to LogKind in output.py
Pylance flags omissions in steps 2 and 3. The contract check validates
the full lifecycle (producer → consumer → test coverage).
"""

from __future__ import annotations
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field

# ── Session lifecycle ──────────────────────────────────────────────────


class RunStartedPayload(BaseModel):
    kind: Literal["run_started"]
    role: str
    max_turns: int
    temperature: float


class RunStoppedPayload(BaseModel):
    kind: Literal["run_stopped"]
    reason: str
    turns: int = 0
    detail: str = ""


class SessionSummaryPayload(BaseModel):
    kind: Literal["session_summary"]
    n_turns: int
    input_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    uncached_input_tokens: int = 0
    output_tokens: int = 0
    cache_hit_ratio: float = 0.0


# ── LLM I/O ────────────────────────────────────────────────────────────


class UserMsgPayload(BaseModel):
    kind: Literal["user_msg"]
    text: str = ""


class ModelMsgPayload(BaseModel):
    kind: Literal["model_msg"]
    text: str = ""
    tool_calls: list[dict[str, Any]] = []
    finish_reason: str = ""
    in_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    out_tokens: int = 0


class UsagePayload(BaseModel):
    kind: Literal["usage"]
    input_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    output_tokens: int = 0


class ProviderAttemptPayload(BaseModel):
    kind: Literal["provider_attempt"]
    provider: str = ""
    slug: str = ""
    status: int = 0
    ms: int = 0
    error: str | None = None
    logical_call_id: str = ""


# ── Tool I/O ───────────────────────────────────────────────────────────


class ToolCallPayload(BaseModel):
    kind: Literal["tool_call"]
    params: dict[str, Any] = {}


class ToolResultPayload(BaseModel):
    kind: Literal["tool_result"]
    summary: str = ""
    ok: bool = True
    error: dict[str, Any] | None = None


# ── Hooks / guards ─────────────────────────────────────────────────────


class HookDecisionPayload(BaseModel):
    kind: Literal["hook_decision"]
    middleware: str = ""
    point: str = ""
    decision: str = ""
    reason: str = ""


class LoopGuardWarnPayload(BaseModel):
    kind: Literal["loop_guard_warn"]
    detector: str = ""
    message: str = ""


class AuditPayload(BaseModel):
    kind: Literal["audit"]
    # Content varies by hook — keep flexible
    content: dict[str, Any] = {}


# ── Context budget ─────────────────────────────────────────────────────


class ContextBudgetWarnPayload(BaseModel):
    kind: Literal["context_budget_warn"]
    action: str = ""
    ratio: float = 0.0
    message: str = ""


class ContextBudgetHardStopPayload(BaseModel):
    kind: Literal["context_budget_hard_stop"]
    message: str = ""
    current_tokens: int = 0
    limit_tokens: int = 0
    threshold: int = 0


# ── Compaction ─────────────────────────────────────────────────────────


class CompactionWarningPayload(BaseModel):
    kind: Literal["compaction_warning"]
    message: str = ""


class CompactionCircuitBreakerPayload(BaseModel):
    kind: Literal["compaction_circuit_breaker"]
    message: str = ""


class CompactionStage2StartPayload(BaseModel):
    kind: Literal["compaction_stage2_start"]
    tokens_before: int = 0
    threshold: int = 0


class CompactionStage2DonePayload(BaseModel):
    kind: Literal["compaction_stage2_done"]
    tokens_before: int = 0
    tokens_after: int = 0


class CompactionStage2ErrorPayload(BaseModel):
    kind: Literal["compaction_stage2_error"]
    error: str = ""


class CompactionStage3StartPayload(BaseModel):
    kind: Literal["compaction_stage3_start"]
    tokens_before: int = 0
    threshold: int = 0


class CompactionStage3DonePayload(BaseModel):
    kind: Literal["compaction_stage3_done"]
    tokens_before: int = 0
    tokens_after: int = 0
    summary: str = ""


class CompactionStage3ErrorPayload(BaseModel):
    kind: Literal["compaction_stage3_error"]
    error: str = ""


# ── Subagent ───────────────────────────────────────────────────────────


class SubagentSpawnStartPayload(BaseModel):
    kind: Literal["subagent_spawn_start"]
    task_id: str = ""
    role: str = ""
    command_preview: str = ""
    workdir: str = ""
    env_keys: list[str] = []


class SubagentSpawnDonePayload(BaseModel):
    kind: Literal["subagent_spawn_done"]
    task_id: str = ""
    role: str = ""
    exit_code: int = 0
    duration_ms: int = 0
    verification: str = ""


class SubagentSpawnFailPayload(BaseModel):
    kind: Literal["subagent_spawn_fail"]
    task_id: str = ""
    role: str = ""
    error: str = ""


# ── Observability / recovery ──────────────────────────────────────────


class RecoveryActionPayload(BaseModel):
    kind: Literal["recovery_action"]
    # Content varies by recovery type
    content: dict[str, Any] = {}


class VerificationPayload(BaseModel):
    kind: Literal["verification"]
    content: dict[str, Any] = {}


class CostObservationPayload(BaseModel):
    kind: Literal["cost_observation"]
    content: dict[str, Any] = {}


class TelemetryPayload(BaseModel):
    kind: Literal["telemetry"]
    tool_name: str = ""
    ok: bool = True
    artifact_id: str = ""
    turn: int = 0


# ── Infrastructure ─────────────────────────────────────────────────────


class ServiceUnavailablePayload(BaseModel):
    kind: Literal["service_unavailable"]
    content: dict[str, Any] = {}


class TimeoutPayload(BaseModel):
    kind: Literal["timeout"]
    content: dict[str, Any] = {}


# ── Fallback for unknown/future kinds ─────────────────────────────────


class UnknownLogPayload(BaseModel):
    """Catch-all for kinds not yet in the typed schema."""

    kind: str  # unconstrained
    content: dict[str, Any] = {}


# ── The discriminated unions ──────────────────────────────────────────

KnownLogEvent = Annotated[
    Union[
        RunStartedPayload,
        RunStoppedPayload,
        SessionSummaryPayload,
        UserMsgPayload,
        ModelMsgPayload,
        UsagePayload,
        ProviderAttemptPayload,
        ToolCallPayload,
        ToolResultPayload,
        HookDecisionPayload,
        LoopGuardWarnPayload,
        AuditPayload,
        ContextBudgetWarnPayload,
        ContextBudgetHardStopPayload,
        CompactionWarningPayload,
        CompactionCircuitBreakerPayload,
        CompactionStage2StartPayload,
        CompactionStage2DonePayload,
        CompactionStage2ErrorPayload,
        CompactionStage3StartPayload,
        CompactionStage3DonePayload,
        CompactionStage3ErrorPayload,
        SubagentSpawnStartPayload,
        SubagentSpawnDonePayload,
        SubagentSpawnFailPayload,
        RecoveryActionPayload,
        VerificationPayload,
        CostObservationPayload,
        TelemetryPayload,
        ServiceUnavailablePayload,
        TimeoutPayload,
    ],
    Field(discriminator="kind"),
]

LogEvent = Annotated[
    Union[
        KnownLogEvent,
        UnknownLogPayload,
    ],
    Field(union_mode="left_to_right"),
]

# ── Console-mirror tag ────────────────────────────────────────────────

# Which kinds MUST also emit an OutputEvent. Defined here as a
# ClassVar on each payload class so the contract check can read
# it from the type definition — single source of truth.
CONSOLE_MIRROR_KINDS: frozenset[str] = frozenset(
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

### Step 6.2: Add `parse_trace_event()` boundary function

```python
# In src/fa/events.py

from fa.inner_loop.state import TraceEvent


def parse_trace_event(raw: TraceEvent) -> LogEvent:
    """Parse a raw TraceEvent into a typed LogEvent variant.

    This is the Parse-Don't-Validate boundary: converts untrusted
    (kind: str, content: dict) into typed variants where the payload
    shape is guaranteed by construction.

    Unknown kinds fall through to UnknownLogPayload — never crashes.
    Payload validation errors also fall through to UnknownLogPayload
    with a warning, so old event logs with changed schemas still parse.
    """
    content = dict(raw.content) if raw.content else {}
    content["kind"] = raw.kind  # inject kind for discriminator

    try:
        return TypeAdapter(KnownLogEvent).validate_python(content)
    except Exception:
        # Schema mismatch or unknown kind — degrade gracefully
        return UnknownLogPayload(kind=raw.kind, content=dict(raw.content or {}))
```

### Step 6.3: Migrate `fa stats` to use typed events

**Current** (30-site elif chain):
```python
if kind == "run_started":
    role = str(content.get("role", ""))
elif kind == "usage":
    ...
```

**New** (isinstance-based type narrowing):
```python
from fa.events import parse_trace_event, CompactionStage2DonePayload, ...

for event in events:
    typed = parse_trace_event(event)
    if isinstance(typed, CompactionStage2DonePayload):
        compaction_records.append(CompactionRecord(
            stage=2, ok=True,
            tokens_before=typed.tokens_before,
            tokens_after=typed.tokens_after,
        ))
    elif isinstance(typed, CompactionStage2ErrorPayload):
        compaction_records.append(CompactionRecord(
            stage=2, ok=False, error=typed.error,
        ))
    elif isinstance(typed, UnknownLogPayload):
        logger.debug("unparsed event kind in stats: %s", typed.kind)
    ...
```

Benefits:
- **No `content.get("field", default)`** — direct `typed.tokens_before` access, type-checked
- **Unknown kinds get a warning**, not silent skip
- **Payload type errors caught at parse time**, not at stats render time

### Step 6.4: Migrate SessionState to property-typed extensions

**Current**: `output_bus: EventBus | None = None` — consumers must do `getattr(session, "output_bus", None)`

**New**: Property returning non-Optional type with explicit RuntimeError on uninitialized access:

```python
@dataclass
class _SessionExtensions:
    """Internal holder — None until __post_init__ fills them."""

    feature_flags: FeatureFlags | None = None
    output_bus: EventBus | None = None
    transaction: Transaction | None = None
    blackboard: Blackboard | None = None
    telemetry: TelemetryLogger | None = None
    artifact_store: ArtifactStore | None = None
    pty_pool: Any | None = None  # PtyPool — optional module
    worktree_manager: WorktreeManager | None = None
    session_db: SessionDatabase | None = None


@dataclass
class SessionState:
    workspace_root: Path
    run_id: str = field(default_factory=lambda: f"run-{os.getpid()}")
    log: EventLog | None = None
    observations: list[str] = field(default_factory=list)
    turn: int = 0
    subagent_spawns: int = 0
    _ext: _SessionExtensions = field(default_factory=_SessionExtensions, init=False, repr=False)
    _subagent_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # ── Typed properties (non-Optional return types) ─────────────────

    @property
    def feature_flags(self) -> FeatureFlags:
        val = self._ext.feature_flags
        if val is None:
            raise RuntimeError("feature_flags not initialized — use make_session_state()")
        return val

    @feature_flags.setter
    def feature_flags(self, value: FeatureFlags) -> None:
        self._ext.feature_flags = value

    @property
    def output_bus(self) -> EventBus:
        val = self._ext.output_bus
        if val is None:
            raise RuntimeError("output_bus not initialized — set via state.output_bus = bus")
        return val

    @output_bus.setter
    def output_bus(self, value: EventBus) -> None:
        self._ext.output_bus = value

    # ... same pattern for all 9 fields ...
```

**Impact on consumer sites**:

| Before | After | Pylance sees |
|--------|-------|-------------|
| `getattr(session, "output_bus", None)` | `session.output_bus` | `EventBus` (non-Optional!) |
| `if state.feature_flags is not None: getattr(state.feature_flags, "context_budget_enabled", True)` | `state.feature_flags.context_budget_enabled` | `bool` |
| `ff = getattr(session, "feature_flags", None)` | `ff = session.feature_flags` | `FeatureFlags` |

The RuntimeError on uninitialized access is **explicit and actionable**: it tells the developer/agent exactly what's missing and how to fix it. This is the Parse-Don'tValidate pattern: the type carries the proof that initialization happened, so downstream code never needs defensive checks.

**Backward compatibility**: The `@property` + setter pattern means existing `state.output_bus = bus` assignments still work. The `_ext` backing store is private — no external code accesses it.

### Step 6.5: Migrate ConsoleRenderer to typed OutputEvent data

**Current**: `e.data.get("stage", "?")` — 14 handler methods all using dict access

**New**: Define typed `*Data` classes per EventType and use `isinstance` narrowing:

```python
class CompactionEndData(BaseModel):
    type: Literal["compaction_end"]
    stage: int
    ok: bool
    tokens_before: int = 0
    tokens_after: int = 0
    error: str = ""


# ... one per EventType ...


class ConsoleRenderer:
    def on_event(self, event: OutputEvent) -> None:
        handler = getattr(self, f"_handle_{event.type}", None)
        if handler:
            handler(event)

    def _handle_compaction_end(self, e: OutputEvent) -> None:
        # Still receives OutputEvent for backward compat,
        # but can parse the data dict into typed form:
        d = e.data
        stage = d.get("stage", "?")
        ok = d.get("ok", True)
        ...
```

Full migration to typed `*Data` classes on `OutputEvent` is a Phase 7 item (breaking change for all event producers). For Phase 6, we just add the schema definitions and the `parse_trace_event()` boundary function — consumers can migrate incrementally.

### Step 6.6: Update contract check to validate discriminated union completeness

**Enhance `scripts/check_log_kind_contract.py`**:

1. Parse `KnownLogEvent` union from `events.py`
2. Verify every variant's `kind` Literal is in `LogKind` from `output.py`
3. Verify every `LogKind` literal has a matching variant in `KnownLogEvent`
4. For each variant in `CONSOLE_MIRROR_KINDS`, verify OutputEvent producer exists
5. Verify each variant has at least one C1 test
6. Report:
   - Missing variants (LogKind without payload class)
   - Orphan variants (payload class without LogKind)
   - Missing console-mirror emit
   - Missing C1 test

### Step 6.7: Verify Phase 6

```bash
python -m pytest --tb=short -q 2>&1 | tail -1
python scripts/check_log_kind_contract.py
python scripts/check_producer_consumer_contract.py
python scripts/check_no_mocked_dataclasses.py
# New: verify events.py schema completeness
python -c "from fa.events import KnownLogEvent, LogKind; ..."
```

All must pass. Commit.

---

## Updated Phase Summary Table

| Phase | Finding(s) | Key Changes | Lines Changed (est.) | New Tests (est.) | Risk |
|-------|-----------|-------------|---------------------|-------------------|------|
| P1 | F-4, F-3 | Fix `or 150000`, type `compactor_chain` | ~15 | 3-5 | LOW |
| P2 | F-2, F-1 | LogKind Literal, console-mirror subset, contract check script | ~120 | 15-20 | MEDIUM |
| P3 | F-5 | Type 9 `Any \| None` fields | ~30 | 5-8 | MEDIUM |
| P4 | F-6, F-10, P1 | Fail-closed/open, compaction SSoT, remove getattr defaults | ~80 | 10-15 | MEDIUM |
| P5 | F-7, F-8, F-9, NEW-8, LOGIC-16, LOGIC-10 | Stats parsers, docs, sqlite3 import, EventLog methods, abnormal_stop hint | ~250 | 20-30 | LOW-MEDIUM |
| P6 | Deep closure | Discriminated union events.py, parse_trace_event(), property-typed SessionState, typed stats parsing | ~400 | 25-35 | MEDIUM |

**Total estimated**: ~895 lines changed, ~80-113 new tests across 6 phases.

---

## Dependency Graph

```
P1 (bug fixes) ──────── no dependencies, ships first
   │
P2 (LogKind + contract)── depends on P1 only for clean diff
   │
P3 (type 9 fields) ──── depends on P2 (LogKind used in append signature)
   │
P4 (fail-closed + SSoT)── depends on P3 (typed fields enable direct access)
   │
P5 (coverage + docs) ── depends on P4 (stats parsers need final kind set)
   │
P6 (deep closure) ───── depends on P2 (LogKind defines the schema)
                        depends on P5 (stats parsers migrated to typed form)
```

Each phase is independently shippable: tests green → merge → next phase.

---

## Risk Mitigation

1. **P2 LogKind**: If adding `LogKind` type to `append()` signature causes type errors in code we haven't seen, the contract check will flag them. Run `pyright src/fa/inner_loop/state.py` after the change.

2. **P3 typing**: The `from __future__ import annotations` import is already present in state.py, so forward references work. The risk is that some consumer site expects `Any` and breaks when it gets a specific type — but this is exactly the kind of breakage we WANT (type safety catching bugs).

3. **P4 F-10 compaction SSoT**: Removing the feature flag gate is the biggest semantic change. The key insight is that `compaction_threshold: int | None = None` already means "compaction is not configured" when None. The feature flag was a redundant boolean gate. Adding a deprecation comment and a contract check rule that flags any usage of `context_compaction_enabled` in production code prevents regressions.

4. **P5 EventLog.count()/tail()**: Must add `count_events()` and `read_event_rows_tail(n)` to `SessionDatabase` first. If the DB is unavailable, fall back to JSONL. The fallback is the same as current `read_all()` behavior, just limited to the tail.

5. **P6 discriminated union**: `parse_trace_event()` gracefully degrades — unknown kinds or payload mismatches become `UnknownLogPayload`, never crash. This means Phase 6 is safe to land even if some event kinds have changed their content schema between versions. The typed parsing is additive — existing `kind: str` + `content: dict` code still works. Migration to `isinstance` checks can happen incrementally per consumer.

6. **P6 property-typed SessionState**: The `@property` + setter pattern is backward-compatible. Existing `state.output_bus = bus` still works. The RuntimeError on uninitialized access is a *stricter* failure mode than the current silent None, but this is intentional — the Parse-Don't-Validate principle says: fail explicitly at the boundary, not silently downstream.

---

## Verification Checklist (Final, After All Phases)

- [ ] `python -m pytest --tb=short -q` — all tests pass
- [ ] `python scripts/check_producer_consumer_contract.py` — exit 0
- [ ] `python scripts/check_no_mocked_dataclasses.py` — exit 0
- [ ] `python scripts/check_log_kind_contract.py` — exit 0 (NEW)
- [ ] No `getattr(flags, "field", default)` with duplicated defaults in production code
- [ ] No `Any | None` on SessionState fields (except pty_pool)
- [ ] `compactor_chain` typed as `ProviderChain | None` everywhere
- [ ] No `or 150000` logic trap on context_limit
- [ ] All 30 log kinds parsed by `fa stats` (or explicitly documented as not parseable)
- [ ] SKILL.md updated with I-TW-17 (console-mirror) and I-TW-20 (no mocked dataclasses)
- [ ] `context_compaction_enabled` not referenced in production code (deprecated)
- [ ] Safety-critical flags fail CLOSED, convenience flags fail OPEN
- [ ] `src/fa/events.py` exists with discriminated union for all 30 log kinds
- [ ] `parse_trace_event()` converts TraceEvent → typed LogEvent variant
- [ ] Unknown log kinds degrade to `UnknownLogPayload`, never crash
- [ ] `fa stats` uses `isinstance(typed, ...)` narrowing (no raw `content.get()`)
- [ ] SessionState properties return non-Optional types
- [ ] Contract check validates union completeness (LogKind ↔ payload class ↔ C1 test)
