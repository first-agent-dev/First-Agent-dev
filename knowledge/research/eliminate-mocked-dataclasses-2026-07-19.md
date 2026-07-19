# Eliminate Mocked Dataclasses — Design Decision

**Date**: 2026-07-19
**Scope**: Close the "new field on dataclass breaks mocks" regression pattern

## Problem

When a new field is added to a frozen dataclass like `ChainConfig`, every test
that creates `MagicMock(spec=ChainConfig)` and manually sets fields on it breaks
at runtime with `AttributeError`. This happened when `extras` was added — 33+
test methods across 10+ files failed.

The root cause is fundamental: **`MagicMock(spec=ChainConfig)` is the wrong
pattern for dataclasses.** ChainConfig is a frozen dataclass — pure data, no
behavior. Mocking is for objects with side effects, not value objects.

## Why MagicMock(spec=Dataclass) is wrong

| Property | MagicMock(spec=ChainConfig) | Real ChainConfig() |
|----------|---------------------------|-------------------|
| New field with default | Breaks every test | **Just works** |
| New required field | Breaks every test | **Breaks at import time** (TypeError) |
| Removed field | Silently passes (field still on mock!) | **Breaks at import time** |
| Renamed field | Silently passes (old name works!) | **Breaks at import time** |
| Structural drift | Hidden until runtime | **Surfaced immediately** |

Mocking a dataclass hides structural drift. Real instances surface it.

## Solution

**Rule: Never mock pure data objects. Only mock objects with behavior.**

- ✅ Mock: `ProviderChain` (has `request()` method with side effects)
- ✅ Mock: `Transport` (has `post()` method with network side effects)
- ❌ Never mock: `ChainConfig` (frozen dataclass, no methods)
- ❌ Never mock: `RequestInfo` (frozen dataclass, no methods)
- ❌ Never mock: `ResponseInfo` (frozen dataclass, no methods)

### Implementation

1. **`make_test_chain_config()`** — Factory that creates real `ChainConfig`
   instances with sensible test defaults. New fields with defaults are
   inherited automatically.

2. **`make_test_chain_entry()`** — Factory for real `ChainEntry` instances.

3. **`make_mock_chain()`** — Updated to use real `ChainConfig` instead of
   `MagicMock(spec=ChainConfig)`. The chain itself is still mocked (we
   need to control `request()` returns), but the config is a real value.

4. **36 `MagicMock(spec=ChainConfig)` sites replaced** across 9 test files
   with `make_test_chain_config()` calls.

5. **Guard script** (`scripts/check_no_mocked_dataclasses.py`) — AST-based
   check that detects `MagicMock(spec=<ProtectedDataclass>)` in tests.
   Wired into `just check` and `Makefile check` as a hard gate.

### Protected Dataclasses

The guard watches for mocking of these frozen dataclasses:

- `ChainConfig`, `ChainEntry`, `CooldownRow`, `ChainAttemptRecord`
- `RequestInfo`, `ResponseInfo`, `TransportResponse`

### Future-proofing for new providers

When you add a new provider (e.g. `cohere`, `gemini_native`), you might add
a field to `ChainConfig`. With real instances:

- Fields with defaults (like `extras: Mapping = {}`) just work — zero test changes
- Required fields break at import time with a clear TypeError, not at runtime

The guard script ensures no one accidentally reintroduces `MagicMock(spec=ChainConfig)`.

## Files Changed

| File | Change |
|------|--------|
| `tests/fixtures/session_wiring.py` | Added `make_test_chain_config()`, `make_test_chain_entry()`; updated `make_mock_chain()` to use real ChainConfig |
| `tests/test_pr1_wiring.py` | Replaced MagicMock config → make_test_chain_config() |
| `tests/test_pr2_wiring.py` | Same |
| `tests/test_pr3_wiring.py` | Same |
| `tests/test_pr4_wiring.py` | Same |
| `tests/test_pr5_wiring.py` | Same (10 sites including compactor chains) |
| `tests/test_slice5_6_7_wiring.py` | Same (7 sites) |
| `tests/test_subagent_termination_wiring.py` | Same |
| `tests/test_list_tasks_wiring.py` | Same |
| `tests/test_global_history_export.py` | Same |
| `scripts/check_no_mocked_dataclasses.py` | NEW: AST guard |
| `justfile` | Added `no-mocked-dataclasses` recipe, wired into `check` |
| `Makefile` | Same |
