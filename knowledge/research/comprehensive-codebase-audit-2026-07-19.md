# Comprehensive Codebase Audit — Bad Practices, Logic Errors, and Standardization Gaps

**Date**: 2026-07-19
**Scope**: Full codebase audit for bad universal practices, logic errors, and
high-ROI standardization opportunities. Includes questions that require
architectural decisions from the project owner.
**Status**: AUDIT FOR REVIEW — quiz questions marked with ❓

---

## Audit Methodology

Scanned 99 production Python files, 30+ test files, SKILL.md, ADR-9, ADR-10,
and all 30 log.append(kind=) sites + 13 OutputEvent(type=) sites + 80+
getattr() call sites in production code. Classified findings by bug class,
not by severity.

---

## FINDING-1: Two disjoint event systems — the dual-write invariant is a myth

**Bug class: Architectural gap (not a typo, a design disconnect)**

The SKILL.md invariant I-TW-17 says:

> **Dual-write: EventLog and EventBus both written on every code path.**

But the two systems are **essentially disjoint**:

| System | Channel | Unique strings | Total |
|--------|---------|---------------|-------|
| EventLog | `log.append(kind=...)` | 30 unique kinds | 30 |
| EventBus | `output.emit(OutputEvent(type=...))` | 13 unique types | 13 |
| **Overlap** | Both | `tool_call` | **1** |

**29 out of 30 log kinds have NO corresponding OutputEvent.** 12 out of 13
OutputEvent types have NO corresponding log.append.

The dual-write invariant as written is **vacuously true** — it only applies to
the 1 overlapping event (`tool_call`). For 97% of events, dual-write never
holds because the two systems were designed for different purposes:

- **EventLog** = structured audit trail (session.db + JSONL), machine-readable,
  covers compaction stages, budget thresholds, recovery actions, hook decisions,
  subagent lifecycle, cost observations, verifications, telemetry, etc.
- **EventBus** = real-time console rendering, human-facing, covers session
  lifecycle (start/end/turn), compaction start/end, context warnings, hook
  denies, API retries, tool calls, subagent start/end.

The SKILL.md invariant is **misleading** — it implies that every log.append
should have a matching output.emit, but the systems were never designed to
be 1:1 mirrors. The invariant should either:

(a) Define which events ARE dual-write (the 13 OutputEvent types) and make
    dual-write a hard gate only for those, OR
(b) Rename the invariant to "EventBus coverage" and enumerate which log kinds
    SHOULD have an OutputEvent mirror (the ones operators need to see in real-time).

**Impact**: The contract check script (`check_producer_consumer_contract.py`)
only checks the OutputEvent system. It does NOT check log.append kinds. A new
log kind can be added with zero C1 test coverage and the contract check still
passes.

### ❓ Question 1: Should we define a "console-mirror" subset of log kinds
that MUST also have OutputEvent emissions? Or accept the two systems as
intentionally different and update the invariant to reflect reality?

---

## FINDING-2: 30 log.append(kind=) strings with no type safety — typo = silent bug

**Bug class: String-typed identifiers (same class as the "not wired" bugs)**

All 30 log.append kinds and 13 OutputEvent types are bare strings. There is
no enum, no Literal type, no central registry for log kinds. If someone
typoes `kind="compaction_stage2_dne"` instead of `kind="compaction_stage2_done"`,
the event is silently emitted and never parsed — identical to the "not wired"
bug class that the contract check was built to prevent.

The OutputEvent system has `EventType = Literal[...]` in output.py, which the
contract check script uses. But the log.append system has no equivalent.

**Impact**: Currently 5 log kinds are emitted but NOT parsed by `fa stats`:

- `compaction_circuit_breaker` — critical operational signal, invisible in stats
- `compaction_stage2_start` — timing gap between start and done is invisible
- `compaction_stage3_start` — same
- `model_msg` — model input/output tracking, invisible
- `user_msg` — user message tracking, invisible

Plus `subagent_spawn_start` is emitted but only `subagent_spawn_done`/`fail`
are parsed — start→end timing is lost.

### ❓ Question 2: Should we create a `LogKind = Literal[...]` type in
output.py (or a new module) that enumerates all valid log kinds, and wire
it into a second contract check? This would be the structural fix for the
same "not wired" bug class but on the log.append side.

---

## FINDING-3: `getattr(flags, "field", default)` duplicates dataclass defaults — 12 sites

**Bug class: Default divergence (same class as MagicMock(spec=ChainConfig))**

Already identified in the previous audit. Adding one critical nuance:

The **compaction/compactor.py** double-getattr:

```python
model_slug = getattr(getattr(self.compactor_chain, "config", None), "model", "compactor")
```

This is a chain of TWO getattr calls:
1. `getattr(self.compactor_chain, "config", None)` — defensive, because
   `compactor_chain` is typed as `Any | None`
2. `getattr(..., "model", "compactor")` — fallback "compactor" is NOT the
   ChainConfig default (which is empty string `""`), it's a DIFFERENT default

If `compactor_chain.config.model` is `""` (empty string, the ChainConfig default),
this code returns `""`, NOT `"compactor"`. The fallback only fires if `config`
is None. So the "compactor" fallback is unreachable in normal operation — it
only fires if `config` itself is None (which would mean the ProviderChain was
constructed without a config, which shouldn't happen).

**Logic error**: The fallback "compactor" is dead code. The real behavior is
that `model_slug` will be `""` (empty string) when the default ChainConfig is
used, which then gets passed to `RequestInfo(model_slug=str(model_slug))` as
an empty string — a model request to `""` which will fail at the provider.

### ❓ Question 3: Should `compactor_chain` be typed as `ProviderChain`
(not `Any | None`) so the double-getattr can be replaced with
`self.compactor_chain.config.model`? This would surface the empty-string
model slug as a config validation error at construction time rather than
a silent runtime failure.

---

## FINDING-4: `context_limit = getattr(..., 150000) or 150000` — the `or` swallows zero

**Bug class: Logic error — `or` conflates 0/None/empty with "missing"**

Line 409 of coder_loop.py:
```python
context_limit = getattr(provider_chain.config, "context_limit", 150000) or 150000
```

ChainConfig already has `context_limit: int = 150000` as a default. So the
getattr fallback `150000` is dead code (ChainConfig always has the field).

But the `or 150000` is WORSE than dead code — it's a **logic trap**:

- `context_limit=0` → `getattr` returns `0` → `0 or 150000` = `150000`
  → **silently swallows zero**
- `context_limit=None` → `getattr` returns `None` → `None or 150000` = `150000`
  → silently coerces None to 150000

If a user ever sets `context_limit: 0` in models.yaml to disable the budget,
this line silently ignores it. ContextBudget handles `limit_tokens=0` correctly
(returns ratio=0.0, never triggers budget gates). But this `or` prevents that
value from ever reaching ContextBudget.

**Fix**: Replace with `provider_chain.config.context_limit`. The ChainConfig
default is already 150000, and the dataclass constructor validates the field
(as of the `chain_from_mapping` fix in this session).

---

## FINDING-5: SessionState has 9 `Any | None` fields — no type safety at boundaries

**Bug class: Type erasure (same class as MagicMock(spec=ChainConfig))**

56% of SessionState fields are typed `Any | None`:

| Field | Actual type | Typed as |
|-------|-----------|---------|
| `transaction` | `Transaction` | `Any | None` |
| `blackboard` | `Blackboard` | `Any | None` |
| `telemetry` | `TelemetryLogger` | `Any | None` |
| `feature_flags` | `FeatureFlags` | `Any | None` |
| `artifact_store` | `ArtifactStore` | `Any | None` |
| `pty_pool` | `PtyPool` | `Any | None` |
| `worktree_manager` | `WorktreeManagerFactory | SharedDirWorktreeManager` | `Any | None` |
| `session_db` | `SessionDatabase` | `Any | None` |
| `output_bus` | `EventBus` | `Any | None` |

This means:
- Every consumer must use `getattr(obj, "field", None)` or `isinstance` checks
- Static type checkers (Pylance, pyright) cannot catch attribute errors
- The 19 `getattr(session, "X", None)` call sites in tools/spawn_subagent.py,
  tools/run_bash.py, tools/edit_file.py, tools/write_file.py, etc. are ALL
  working around the `Any | None` type — if the type were `EventBus | None`,
  Pylance would enforce the None check and the getattr wouldn't be needed.

**Why this matters for future providers**: Adding a new provider may require
new fields on SessionState (e.g. `conversation_id` for the Mistral
Conversations API). If the field is `Any | None`, every consumer will need
`getattr(session, "conversation_id", None)` instead of a typed access with
proper None handling.

### ❓ Question 4: Should we type-annotate all 9 `Any | None` fields with
their actual types? This is a significant change because SessionState is
mutable and the fields are lazily initialized — we'd need either:

(a) `from __future__ import annotations` + proper types, accepting that
    construction sets them to None and lazy init fills them in, OR
(b) A `TypedDict`-style approach where required fields are separated from
    optional ones, OR
(c) Leave as `Any | None` but add `assert`/`isinstance` guards at the
    consumer sites so type checkers can narrow the type.

Option (a) is the simplest but requires fixing all consumer sites.
Option (c) is the incremental path — add guards, let Pylance narrow.

---

## FINDING-6: "Fail open" pattern — bare `except: pass` swallows flag errors

**Bug class: Silent failure (related to the "not wired" bug class)**

4 sites in coder_loop.py use this pattern:

```python
budget_enabled = True  # default: fail OPEN
try:
    if state.feature_flags is not None:
        budget_enabled = getattr(state.feature_flags, "context_budget_enabled", True)
except Exception:  # noqa: BLE001, S110 # graceful degradation
    pass
```

If `feature_flags` raises ANY exception (AttributeError, TypeError, even
KeyError from a misconfigured dict), the code silently falls back to the
hardcoded default. The user's config is silently ignored.

This is the "fail open" pattern — the system continues with defaults rather
than surfacing the error. For a BUDGET gate, failing open means the budget
is always "enabled" even if the user explicitly disabled it.

The correct pattern for a **safety gate** (budget, compaction, security) is
**fail closed**: if the flag can't be read, assume the most restrictive
setting. The correct pattern for a **convenience feature** (telemetry,
worktree) is fail open.

### ❓ Question 5: Should budget/compaction flags fail CLOSED (if flag read
fails, budget is ENABLED and compaction is DISABLED — the restrictive
defaults)? And should telemetry/convenience flags fail OPEN (if flag read
fails, feature is enabled)? This would require auditing each flag usage
and deciding which is safety-critical vs convenience.

---

## FINDING-7: `fa stats` has 5+ unparseable log kinds — operator blind spots

**Bug class: Silent data loss (consumer gap)**

Already identified in the handoff as NEW-5/NEW-6, but the full scope is:

| log kind | Emitted? | Parsed by stats? | Impact |
|----------|----------|-------------------|--------|
| `compaction_circuit_breaker` | ✅ | ❌ | Circuit breaker invisible to operator |
| `compaction_stage2_start` | ✅ | ❌ | Stage2 timing invisible |
| `compaction_stage3_start` | ✅ | ❌ | Stage3 timing invisible |
| `subagent_spawn_start` | ✅ | ❌ | Spawn timing invisible |
| `model_msg` | ✅ | ❌ | Model I/O invisible |
| `user_msg` | ✅ | ❌ | User messages invisible |
| `compaction_warning` | ✅ | ❌ | Foundation compaction warning invisible |
| `recovery_action` | ✅ | ❌ | Recovery decisions invisible |
| `verification` | ✅ | ❌ | Verifier results invisible |
| `cost_observation` | ✅ | ❌ | Cost tracking invisible |
| `audit` | ✅ | ❌ | Hook audit invisible |
| `telemetry` | ✅ | ❌ | Telemetry events invisible |

**12 of 30 log kinds are invisible in `fa stats`.** The operator has no
console visibility into circuit breakers, compaction timing, recovery
actions, verifications, or cost observations.

This is not a bug in the stats parser — it's a **coverage gap** that should
be tracked alongside the OutputEvent contract check.

---

## FINDING-8: SKILL.md §5 contradicts the new "no mocked dataclasses" rule

**Bug class: Documentation drift**

The skill's "Type-honest fixtures" table (§5) says:

```
| provider_chain | MagicMock(spec=ProviderChain) — mock I/O only | mock the root |
```

This is correct for ProviderChain (it has behavior). But the skill doesn't
distinguish between "mock the chain" and "mock the chain's config". The
worked example in §14 uses `make_mock_chain(context_limit=100000)` without
specifying that the config should be a real `ChainConfig`.

After our fix, `make_mock_chain()` now creates a real `ChainConfig` — but
the skill doesn't document this principle. A future developer reading only
the skill could reasonably write `MagicMock(spec=ChainConfig)` again.

The "Prefer instead" table says `hooks=HookRegistry()` instead of
`MagicMock` for wiring — but it doesn't generalize this to ALL data objects.

---

## FINDING-9: The `output_bus` None window — 3 getattr sites in spawn_subagent.py

**Bug class: Partial observability (producer gap on conditional path)**

These 3 sites use `getattr(session, "output_bus", None)` and then
conditionally emit:

```python
output_bus = getattr(session, "output_bus", None)
if output_bus is not None:
    output_bus.emit(OutputEvent(type="subagent_start", ...))
```

If `output_bus` is None (which happens during session construction, before
`state.output_bus = output_bus` is called in cli.py L1925), the emit is
silently skipped. The subagent start/end events are lost.

This was the FIX-3 from the observability work — the emit IS there, it just
gracefully degrades when the bus isn't wired. The question is: should there
be a log.append fallback so the event is at least in the EventLog even when
the bus isn't wired?

Currently: emit on bus only → if bus is None, event disappears entirely.
The EventLog has `subagent_spawn_start`/`subagent_spawn_fail` kinds, but
the OutputEvent has `subagent_start`/`subagent_end` — different names,
different systems. An operator watching the console would see nothing during
the None window.

---

## FINDING-10: `compaction_enabled` default mismatch across code paths

**Bug class: Semantic ambiguity**

In coder_loop.py, `compaction_enabled` is determined by:
```python
compaction_enabled = getattr(state.feature_flags, "context_compaction_enabled", False)
```

Default is `False` — compaction is OFF by default.

But `ChainConfig` has a `compaction_threshold` field that defaults to `None`.
When `compaction_threshold is None`, the ContextBudget also treats compaction
as disabled.

Two different mechanisms control the same concept:
1. `FeatureFlags.context_compaction_enabled` (bool, default=False)
2. `ChainConfig.compaction_threshold` (int|None, default=None)

If someone sets `compaction_threshold: 80000` in models.yaml but forgets
`context_compaction_enabled: true` in config.yaml, compaction is STILL
disabled because the feature flag overrides the threshold.

Conversely, if `context_compaction_enabled: true` but
`compaction_threshold: null`, the code enters the compaction branch but
ContextBudget has no threshold → behavior is undefined.

### ❓ Question 6: Should there be a single source of truth for "is
compaction enabled"? Currently the feature flag is a boolean gate and the
threshold is a numeric gate. They can contradict. Should we:
(a) Remove the feature flag and derive "enabled" from threshold is not None,
(b) Keep both but add a validation warning when they contradict, or
(c) Keep both as-is with clear documentation that the flag overrides threshold?

---

## Summary table

| ID | Bug class | Sites | Question needed? | ROI |
|---|---|---|---|---|
| F-1 | Two disjoint event systems, dual-write invariant is myth | 30+13 kinds | ❓ Yes | HIGH |
| F-2 | String-typed log kinds — no type safety | 30 kinds | ❓ Yes | HIGH |
| F-3 | Double-getattr on compactor_chain, dead fallback | 1 site | ❓ Yes | MEDIUM |
| F-4 | `or 150000` swallows zero on context_limit | 1 site | No — logic error | HIGH |
| F-5 | 9 `Any | None` fields on SessionState | 9 fields, 19 consumers | ❓ Yes | HIGH |
| F-6 | Fail-open `except: pass` on safety-critical flags | 4 sites | ❓ Yes | HIGH |
| F-7 | 12/30 log kinds invisible in `fa stats` | 12 kinds | No — coverage gap | MEDIUM |
| F-8 | SKILL.md contradicts no-mocked-dataclasses rule | 1 doc | No — doc update | HIGH |
| F-9 | output_bus None window loses events | 3 sites | No — known gap | LOW |
| F-10 | compaction_enabled double-gate (flag vs threshold) | 2 mechanisms | ❓ Yes | MEDIUM |

### Findings that are FIXABLE without architectural decisions

| ID | Fix | Effort |
|---|---|---|
| F-4 | Replace `getattr(..., 150000) or 150000` with `provider_chain.config.context_limit` | 1 line |
| F-8 | Update SKILL.md §5 + add I-TW-20 invariant | ~10 lines |
| F-7 | Add 5 parsers to stats.py for the missing kinds | ~30 lines |

### Findings that need YOUR decision before proceeding

| ID | Decision needed |
|---|---|
| F-1 | Define "console-mirror" subset of log kinds? Or accept disjoint systems? |
| F-2 | Create `LogKind = Literal[...]` + second contract check? |
| F-3 | Type `compactor_chain` as `ProviderChain` instead of `Any | None`? |
| F-5 | Type-annotate 9 `Any | None` fields? (a) proper types, (b) TypedDict, or (c) isinstance guards? |
| F-6 | Should budget/compaction fail CLOSED? Which flags are safety-critical? |
| F-10 | Single source of truth for compaction enabled? Flag vs threshold? |
