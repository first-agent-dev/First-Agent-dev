# Universal Pattern Audit — Proposals for Review

**Date**: 2026-07-19
**Scope**: Identify bad universal practices in test/production code with high ROI for refactoring
**Status**: PROPOSALS FOR REVIEW — do not implement without confirmation

---

## Methodology

I systematically scanned:
- All 47 `MagicMock` calls in the test suite
- All `getattr()` calls on frozen dataclasses in production code
- All `SessionState`/`EventLog` construction sites (67 direct, 3 via factory)
- All magic numbers in tests (77 occurrences of 150000/100000/80000/64000)
- The tests-writing skill (SKILL.md §5 "Type-honest fixtures")
- Production code patterns in coder_loop.py, state.py, loop.py, prompt_composer.py

I found **5 patterns** that cause the same class of latent regression bugs.
Each is scored on **impact × reach × future-proofing**.

---

## P1. `getattr(flags, "field", default)` on frozen dataclasses — duplicated defaults

**Severity: HIGH — same bug class as `MagicMock(spec=ChainConfig)`**

### The problem

Production code uses `getattr(state.feature_flags, "field", default)` to access
FeatureFlags fields. But FeatureFlags is a **frozen dataclass where every field
has a default**. The `getattr` fallback is therefore redundant — and it
**duplicates the default in a second location**.

```python
# Current (BUG CLASS: duplicated defaults)
budget_enabled = getattr(state.feature_flags, "context_budget_enabled", True)  # ← True duplicated
compaction_enabled = getattr(state.feature_flags, "context_compaction_enabled", False)  # ← False duplicated

# What happens when FeatureFlags changes a default:
#   1. Developer updates FeatureFlags context_compaction_enabled = True
#   2. But the getattr fallback still says False
#   3. If state.feature_flags is somehow None or missing the attr,
#      the OLD default silently applies — production behavior diverges from config
```

10 sites in production code:
- `coder_loop.py`: `context_budget_enabled`, `context_compaction_enabled`
- `loop.py`: `tool_batching_enabled`
- `state.py`: `blackboard_enabled`, `telemetry_enabled`, `pty_pool_max_size`, `offload_threshold`
- `subagent_runner.py`: `getattr(session, "feature_flags", None)` (different — session may not have it)
- `spawn_subagent.py`: `subagent_spawning_enabled`
- `prompt_composer.py`: `getattr(session, "feature_flags", None)` (different)

### Why this is the same bug class

When someone adds a new flag to `FeatureFlags` with a default, and another
developer writes `getattr(flags, "new_flag", True)` in production code, the
default is now in **two places**: the dataclass and the getattr call. If the
dataclass default changes later, the getattr fallback silently retains the old
value.

This is structurally identical to `MagicMock(spec=ChainConfig)` not inheriting
new fields — both create **divergence between the declared schema and the
runtime behavior**.

### Proposal

**Replace `getattr(flags, "field", default)` with direct attribute access.**

```python
# Before:
budget_enabled = getattr(state.feature_flags, "context_budget_enabled", True)

# After:
budget_enabled = state.feature_flags.context_budget_enabled
```

**Guard the `None` case differently**: If `state.feature_flags` can be `None`,
add a single normalization point instead of scattering `getattr` everywhere:

```python
# In SessionState.__init__ or at the entry point:
if self.feature_flags is None:
    from fa.feature_flags import FeatureFlags
    self.feature_flags = FeatureFlags()  # defaults = single source of truth
```

This already exists in `state.py` L304-318 as a lazy initializer. The problem
is that other files still use `getattr` defensively even though `state.feature_flags`
is guaranteed to be a `FeatureFlags` after initialization.

**Impact**: 10 production code sites. One-time fix. Prevents silent default divergence
when FeatureFlags defaults change.

**Risk**: Very low — the lazy initializer in `state.py` already guarantees
`feature_flags` is not None. The `getattr` fallbacks are purely defensive code
that duplicates dataclass defaults.

---

## P2. `MagicMock()` without `spec=` — no structural contract

**Severity: MEDIUM — undetected signature drift**

### The problem

12 sites use `MagicMock()` without `spec=ProviderChain`. This means if
`ProviderChain.request()` changes its return type, these tests still pass
with the old mock shape.

```python
# test_compaction_sota.py L204
mock_chain = MagicMock()  # ← no spec!
mock_response = MagicMock()  # ← no spec!
mock_response.text = "some text"  # ← manually setting attributes
mock_chain.request.return_value = (mock_response, "call-123", [])
```

Compare with the correct pattern used everywhere else:
```python
mock_chain = MagicMock(spec=ProviderChain)  # ← spec enforces the interface
mock_chain.config = make_test_chain_config()  # ← real dataclass
mock_chain.request.return_value = mock_success_response("text")  # ← real ResponseInfo
```

### Proposal

**Replace `MagicMock()` with `MagicMock(spec=ProviderChain)` + real return values.**

The compaction tests should use the same factory:
```python
mock_chain = MagicMock(spec=ProviderChain)
mock_chain.config = make_test_chain_config(model="compactor-model")
mock_chain.request.return_value = mock_success_response("compacted summary")
```

And `mock_response = MagicMock()` should be replaced with real `ResponseInfo`:
```python
# Before:
mock_response = MagicMock()
mock_response.text = "summary text"

# After:
resp = ResponseInfo(text="summary text", in_tokens=100, out_tokens=10, finish_reason="stop")
mock_chain.request.return_value = (resp, "call-123", [])
```

**Impact**: 12 sites in 4 test files. Low risk.

---

## P3. 67 direct `SessionState()` / `EventLog()` constructions — latent field regression

**Severity: MEDIUM — same bug class as ChainConfig mock**

### The problem

21 test files construct `EventLog(path, run_id=...)` + `SessionState(...)` directly
instead of using `make_session_state()`. If `SessionState.__init__` gains a new
required parameter or changes defaults, these 67 sites will break in the same
cascade pattern as the ChainConfig `extras` regression.

### Why the factory exists but isn't used

`make_session_state()` exists in `session_wiring.py` and handles the common
pattern (create EventLog, create SessionState with FeatureFlags). But 85% of
test files don't use it because:

1. Some tests need `log=None` (testing the None path), which the factory
   doesn't support.
2. Some tests need specific `log_path` or `run_id` values.
3. The factory was created late — many tests predate it.

### Proposal

**Extend `make_session_state()` to cover the common variations, then replace
direct constructions.**

```python
def make_session_state(
    tmp_path: Path,
    run_id: str = "test",
    feature_flags: FeatureFlags | None = None,
    log_path: Path | None = None,
    log: EventLog | None = ...,  # sentinel: default = create one
) -> SessionState:
```

Add a `log=None` opt-out for tests that need it. Then replace 67 direct
constructions across 21 files.

**Impact**: 67 sites across 21 files. Medium effort but same future-proofing
as the ChainConfig fix. When `SessionState` gets a new field with a default,
zero test changes needed.

---

## P4. Magic numbers — hardcoded thresholds in tests

**Severity: LOW — readability and maintenance issue, not a regression bug**

### The problem

77 occurrences of hardcoded numbers (150000, 100000, 80000, 64000) in tests.
The skill says "thresholds from source" but the practice is inconsistent.

- `150000` = `ChainConfig.context_limit` default — duplicated in test params
- `100000` = test-specific context limit — not from source, but intentional
- `80000` = test-specific compaction threshold — intentional
- `64000` = `DEFAULT_MAX_TOKENS` for Anthropic — duplicated

### Proposal

**Add named constants to `session_wiring.py` for the most common test values:**

```python
# In tests/fixtures/session_wiring.py
DEFAULT_TEST_CONTEXT_LIMIT = 150000  # matches ChainConfig default
SMALL_TEST_CONTEXT_LIMIT = 100000   # for budget/compaction tests
SMALL_TEST_COMPACTION_THRESHOLD = 80000  # 80% of SMALL_TEST_CONTEXT_LIMIT
```

Then replace magic numbers in test params. This is a "nice to have" — the
current numbers are at least test-specific and not tied to production defaults
that might change. LOW priority.

---

## P5. SKILL.md §5 still references `MagicMock(spec=ProviderChain)` for config

**Severity: HIGH — the skill teaches the pattern that causes regressions**

### The problem

The skill's "Type-honest fixtures" table (§5) says:

```
| provider_chain | MagicMock(spec=ProviderChain) — mock I/O only | mock the root |
```

This is **correct for the ProviderChain itself** (it has behavior — `request()`).
But the skill doesn't say what to do about `provider_chain.config`. The worked
example in §14 uses `make_mock_chain()` without specifying that the config
should be a real `ChainConfig`.

### Proposal

**Update SKILL.md §5 to add the "data vs behavior" rule:**

```
| provider_chain | MagicMock(spec=ProviderChain) — mock I/O only | mock the root |
| provider_chain.config | real ChainConfig via make_test_chain_config() | MagicMock(spec=ChainConfig) |
```

Add a new rule to the "Prefer instead" table:

```
| Real dataclass for config/value objects | MagicMock(spec=<dataclass>) |
```

Add a new invariant:

```
I-TW-20: Never mock frozen dataclasses (ChainConfig, RequestInfo, ResponseInfo,
          TransportResponse, FeatureFlags). Use real instances. Mock objects
          with behavior (ProviderChain, Transport), not objects with only data.
```

---

## Summary table

| ID | Pattern | Sites | Bug class | ROI | Risk | Proposal |
|---|---|---|---|---|---|---|
| P1 | `getattr(flags, "field", default)` duplicates dataclass defaults | 10 prod | Default divergence | HIGH | LOW | Direct attr access + normalize None once |
| P2 | `MagicMock()` without `spec=` | 12 test | Signature drift | MEDIUM | LOW | Add spec + real return values |
| P3 | Direct `SessionState()` construction (not via factory) | 67 test | New-field cascade | MEDIUM | LOW | Extend factory + replace |
| P4 | Hardcoded magic numbers | 77 test | Readability | LOW | NONE | Named constants |
| P5 | SKILL.md teaches `MagicMock(spec=ChainConfig)` pattern | 1 doc | Perpetuates P1-P3 | HIGH | NONE | Update §5 + add I-TW-20 |

### Recommended order

1. **P5 first** — update the skill so all future tests follow the right pattern
2. **P1 next** — fix production code `getattr` pattern (10 sites, low risk)
3. **P2** — fix un-specced mocks (12 sites, low risk)
4. **P3** — extend factory + replace direct constructions (67 sites, medium effort)
5. **P4** — last, if desired (cosmetic, LOW priority)

### What this does for future providers

When you add a new provider:

- **P1**: New feature flags work via the dataclass — no `getattr` fallback to forget
- **P2**: Mock chains enforce the ProviderChain interface — signature changes caught
- **P3**: `make_session_state()` inherits new SessionState fields — zero breakage
- **P5**: The skill teaches the right pattern — future tests don't reintroduce the bug

The ChainConfig regression that cost 33+ test fixes would have been **zero fixes**
if P5 had been in place from the start. P1-P5 together close the entire class.
