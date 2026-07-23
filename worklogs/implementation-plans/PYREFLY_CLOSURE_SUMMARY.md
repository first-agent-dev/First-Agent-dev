# Pyrefly Closure & Logging Standard Improvements

## Executive Summary

Successfully closed all 38 pyrefly errors (down to 0) and improved error logging standards across the codebase. The changes maintain backward compatibility while providing better observability and type safety.

## Changes Overview

### 1. Pyrefly Configuration (pyproject.toml)

**Problem**: Pyrefly couldn't resolve imports for `tests.*` and `scripts.*` modules because they weren't in the configured search paths.

**Solution**: Added `search-path = ["src", "."]` to include the repository root in pyrefly's import resolution.

**Impact**: Eliminated 28 missing-import errors without adding suppressions.

### 2. Type Safety Fixes

#### 2.1 write_file.py: `expected_root` Initialization

**Problem**: `expected_root` was defined inside a try block but used in the except block, causing pyrefly to flag it as potentially unbound.

**Solution**: Moved initialization before the try block and simplified redundant `.resolve()` calls.

**Code Pattern**:
```python
# Before: expected_root could be unbound in except block
try:
    expected_root = root.resolve()
    if not bb_root.is_relative_to(expected_root):
        ...
except Exception:
    if bb_root != (expected_root / ".fa" / "blackboard"):  # pyrefly error!
        ...

# After: expected_root always initialized
expected_root = root.resolve()
try:
    if not bb_root.is_relative_to(expected_root):
        ...
except Exception:
    if bb_root != (expected_root / ".fa" / "blackboard"):  # ✓ safe
        ...
```

#### 2.2 pty_pool.py: Pane Narrowing

**Problem**: `self.pane` is typed as `Any | None`, but pyrefly couldn't verify it's non-None before calling methods.

**Solution**: Added explicit narrowing with a local variable and None check.

**Code Pattern**:
```python
# Narrow local before dereference
pane = self.pane
if pane is None:
    raise RuntimeError("tmux pane not available after session setup")
pane.send_keys(setup_cmd, suppress_history=True)
```

**Why this works**: The explicit None check narrows the type from `Any | None` to `Any` (non-None), satisfying pyrefly while preserving runtime behavior.

#### 2.3 server.py: Optional Dependency Boundary

**Problem**: FastAPI is an optional dependency. When absent, `HTTPException = Exception` makes pyrefly think `HTTPException(status_code=...)` is invalid (Exception doesn't accept those kwargs).

**Solution**: Used a local `Any`-typed reference inside the `if HAS_FASTAPI:` block.

**Code Pattern**:
```python
if HAS_FASTAPI:
    # Local reference for type checker - the module-level HTTPException may be
    # narrowed to Exception by the fallback branch above
    _HTTPException: Any = HTTPException
    
    @app.post("/execute")
    def execute(req):
        try:
            ...
        except Exception as e:
            logger.error("/execute error: %s", e, exc_info=True)
            raise _HTTPException(status_code=500, detail=str(e)) from e
```

**Why this works**: Inside the `if HAS_FASTAPI:` block, `_HTTPException` is typed as `Any`, so pyrefly accepts any method call. At runtime, it's the real FastAPI HTTPException class.

#### 2.4 Override Decorators

Added `@override` decorators to methods that override parent class methods:
- `test_event_type_c1_producers.py`: `_DenyGuard.handle`
- `test_inner_loop_loop_guard.py`: `DenyAllBeforeToolExec.handle`
- `check_no_mocked_dataclasses.py`: `MagicMockDataclassVisitor.visit_Call`

**Why this matters**: The `@override` decorator (Python 3.12+) makes the override relationship explicit and catches errors when parent method signatures change.

#### 2.5 Type Annotations in Scripts

Fixed missing type parameters in `check_dependency_contract.py`:
```python
# Before
def extract_contract_packages(contract: dict) -> set[str]:

# After  
def extract_contract_packages(contract: dict[str, Any]) -> set[str]:
```

#### 2.6 Test Fixture Type Honesty

Fixed `test_coverage_tools_batch.py` to use a type that supports both dict and scalar payloads:
```python
# Before: inferred as dict[str, dict[str, str]]
board = {"id": "plan-1", "payload": {"goal": "coverage"}}
board["payload"] = "plain coverage value"  # type error!

# After: explicit dict[str, object]
board: dict[str, object] = {"id": "plan-1", "payload": {"goal": "coverage"}}
board["payload"] = "plain coverage value"  # ✓ valid
```

### 3. Error Logging Standard Improvements

**Problem**: Some exception handlers used `print(..., file=sys.stderr)` instead of the project-standard `logging` module, reducing observability and consistency.

**Solution**: Replaced `print()` with `logger.error()` in exception handlers:

#### 3.1 output.py: EventBus Exception Handling

**Before**:
```python
except Exception as exc:
    print(f"[output] {type(listener).__name__} raised: {exc}", file=sys.stderr)
```

**After**:
```python
except Exception as exc:
    logger.error(
        "Output listener %s raised: %s",
        type(listener).__name__,
        exc,
        exc_info=True,
    )
```

**Benefits**:
- Consistent with project logging standard
- `exc_info=True` includes full traceback in logs
- Structured log format (easier to parse/search)
- Respects log level configuration

#### 3.2 cli.py: Stats Command Error

**Before**:
```python
except Exception as exc:
    print(f"fa stats: failed to read global history: {exc}", file=sys.stderr)
    return 1
```

**After**:
```python
except Exception as exc:
    logger.error("fa stats: failed to read global history: %s", exc, exc_info=True)
    print(f"fa stats: failed to read global history: {exc}", file=sys.stderr)
    return 1
```

**Benefits**:
- Error is now logged (not just printed to stderr)
- Full traceback available in logs for debugging
- User still sees the error message on stderr (CLI UX preserved)

## Critical Analysis: Why Not Change All 219 `# noqa: BLE001`?

The codebase has 219 `except Exception: # noqa: BLE001` occurrences. After analysis:

- **131 (60%) already have proper logging** — no change needed
- **88 (40%) are silent or unclear** — candidates for future improvement
- **1 re-raises** — already preserves exception chain correctly

**Why the "loud logging" pattern doesn't apply broadly:**

1. **Most places intentionally DON'T re-raise** — they're observer boundaries and graceful degradation paths. Re-raising would crash the system.

2. **Exception chain preservation (`from e`) only matters when re-raising** — the other 218 places return fallback values or pass silently.

3. **Some are security boundaries** — e.g., `egress_proxy/server.py` intentionally doesn't log exception details to avoid leaking sensitive information.

**The correct pattern for most cases is:**
- Loud logging WITHOUT chain preservation
- `logger.warning("context: %s", exc, exc_info=True)` for observability
- Keep the `# noqa: BLE001` because the broad catch is intentional

## Test Coverage

Added 27 new tests across 5 test files:

1. **test_runtime_server_open_stand.py** (5 tests) — verifies "open stand" error handling
2. **test_pty_pool_narrowing.py** (6 tests) — verifies pane narrowing and fallback
3. **test_write_file_expected_root.py** (5 tests) — verifies expected_root initialization
4. **test_pyrefly_import_topology.py** (5 tests) — verifies import resolution
5. **test_pyrefly_override_and_fixture_closure.py** (6 tests) — verifies overrides and types

All tests verify:
- The fix works correctly
- The fix doesn't break existing behavior
- Kill-checks: removing the fix makes the test fail

## Verification Results

```
✅ pyrefly check: 0 errors (down from 38)
✅ mypy strict: 0 errors in 279 files
✅ ruff check: All checks passed
✅ pytest: 1851 passed, 15 skipped, 0 failed
✅ coverage: 80% (pre-existing, unchanged)
```

## Lessons Learned

1. **Type narrowing is more powerful than type annotations** — explicit None checks let pyrefly understand control flow better than complex type annotations.

2. **Optional dependencies need careful boundary design** — using local `Any`-typed references inside conditional blocks is cleaner than complex Union types.

3. **Observability matters** — `print()` to stderr is not enough; use the logging module for consistent, structured, configurable error reporting.

4. **Don't mechanically apply patterns** — the "loud logging + exception chain preservation" pattern is great for HTTP endpoints, but most `# noqa: BLE001` places are observer boundaries that shouldn't re-raise.

5. **Tests are documentation** — the 27 new tests document the expected behavior and prevent regressions.

## Future Work

1. **Improve the 88 silent `# noqa: BLE001` occurrences** — add `logger.warning()` calls for better observability.

2. **Consider adding `@override` to more methods** — Python 3.12+ feature that makes override relationships explicit.

3. **Expand pyrefly coverage** — currently advisory only; consider promoting to blocking after stabilization.

## Files Modified

- `pyproject.toml` — added search-path for pyrefly
- `src/fa/inner_loop/tools/write_file.py` — fixed expected_root initialization
- `src/fa/runtime/pty_pool.py` — added pane narrowing
- `src/fa/runtime/server.py` — improved optional dependency boundary
- `src/fa/output.py` — replaced print() with logger.error()
- `src/fa/cli.py` — added logger.error() alongside print()
- `scripts/check_dependency_contract.py` — added type parameters
- `scripts/check_no_mocked_dataclasses.py` — added @override
- `tests/test_event_type_c1_producers.py` — added @override
- `tests/test_inner_loop_loop_guard.py` — added @override
- `tests/test_coverage_tools_batch.py` — fixed fixture type
- `worklogs/pr-notes/PR_NOTE_QUALITY_GUARDRAILS_CLOSURE.md` — fixed broken link
- Added 5 new test files (27 tests total)
