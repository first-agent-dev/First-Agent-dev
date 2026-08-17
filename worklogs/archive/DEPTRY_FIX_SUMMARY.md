# Deptry Tech Debt Resolution

## Problem

deptry reported 5 DEP002 errors: packages defined as dependencies but "not used in the codebase":
- pymupdf
- pdfminer.six
- pypdf
- fastapi
- pydantic

## Root Cause

These are **runtime optional dependencies** loaded dynamically via `importlib.import_module()`:

```python
# src/fa/inner_loop/tools/read_file.py
fitz = importlib.import_module("fitz")  # pymupdf
pdfminer_high_level = importlib.import_module("pdfminer.high_level")  # pdfminer.six
pypdf = importlib.import_module("pypdf")  # pypdf

# src/fa/runtime/server.py
_fastapi = importlib.import_module("fastapi")  # fastapi
_pydantic = importlib.import_module("pydantic")  # pydantic
```

deptry **cannot detect dynamic imports** — it only scans static `import` and `from ... import` statements.

## Solution

### 1. Added runtime extras to DEP002 ignore list

```toml
[tool.deptry.per_rule_ignores]
# Runtime extras are loaded dynamically via importlib.import_module() for
# optional dependency handling; deptry cannot detect dynamic imports but they
# are legitimate runtime dependencies used in read_file.py and server.py.
DEP002 = [
    "mypy", "pre-commit", "pytest", "pytest-asyncio", "pytest-cov",
    "mutmut", "ruff", "types-PyYAML", "pytest-gremlins", "pip-audit",
    "deptry", "pyrefly", "pylint", "vulture",
    "fastapi", "pydantic", "pypdf", "pymupdf", "pdfminer.six",  # ← Added
]
```

### 2. Removed redundant package_module_name_map entries

The previous config had:
```toml
[tool.deptry.package_module_name_map]
pymupdf = ["fitz"]
"pdfminer.six" = ["pdfminer"]
```

This was **not helpful** because:
- `package_module_name_map` tells deptry "when you see `import X`, that's from package Y"
- But deptry can't see dynamic imports at all
- So the map entries were never used

Replaced with a comment explaining the map is reserved for future static-import mismatches.

## Why This Is The Correct Solution

### ✅ These ARE legitimate dependencies

- **pymupdf** (fitz): Used for PDF text extraction in `read_file.py`
- **pdfminer.six**: Fallback PDF extractor in `read_file.py`
- **pypdf**: Another PDF fallback in `read_file.py`
- **fastapi**: Optional HTTP API server in `server.py`
- **pydantic**: Data validation for FastAPI in `server.py`

All are defined in `[project.optional-dependencies]` in `pyproject.toml` and installed via `uv sync --extra runtime`.

### ✅ Dynamic imports are intentional

The codebase uses `importlib.import_module()` for **optional dependency handling**:

```python
try:
    fitz = importlib.import_module("fitz")
    # Use pymupdf for PDF extraction
except ImportError:
    # Fall back to pdfminer or pypdf
    ...
```

This allows the core agent to run without these heavy dependencies installed. Only when PDF extraction or the HTTP API is needed are they loaded.

### ✅ deptry limitation is documented

deptry's documentation acknowledges it cannot detect dynamic imports. The recommended approach is to use `DEP002` ignores with clear comments explaining why.

## Verification

```bash
$ uv run deptry src/
Success! No dependency issues found.
```

All other checks still pass:
- ✅ mypy: 0 errors in 279 files
- ✅ pyrefly: 0 errors
- ✅ ruff: All checks passed
- ✅ pytest: 1851 passed, 15 skipped
- ✅ dependency-contract-check: PASS

## Alternative Approaches Considered

### ❌ Convert to static imports

```python
# BAD: Would break optional dependency handling
import fitz  # ImportError if pymupdf not installed
```

**Rejected**: Would force all users to install heavy PDF dependencies even if they never use PDF extraction.

### ❌ Add type: ignore comments

```python
# BAD: Doesn't solve the deptry issue
fitz = importlib.import_module("fitz")  # type: ignore
```

**Rejected**: type: ignore is for mypy, not deptry. Doesn't address the root cause.

### ❌ Use TYPE_CHECKING imports

```python
# BAD: Only helps type checkers, not deptry
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz
```

**Rejected**: deptry still can't see the runtime import. TYPE_CHECKING is for static analysis only.

## Lessons Learned

1. **deptry has limitations**: It cannot detect dynamic imports. This is a known limitation, not a bug.

2. **Ignore lists are acceptable**: When a tool has known limitations, documented ignore lists are the correct solution. The key is clear comments explaining WHY.

3. **Optional dependencies need special handling**: When using `importlib.import_module()` for optional deps, you must either:
   - Add them to DEP002 ignores (our approach)
   - Or use a deptry plugin that supports dynamic imports (none exist as of 2026)

4. **package_module_name_map is for static imports only**: Don't add entries for dynamically-imported packages — it won't help.

## Future Considerations

If deptry adds support for detecting dynamic imports (e.g., by analyzing `importlib.import_module()` calls), we can:
1. Remove these packages from the DEP002 ignore list
2. Add them to `package_module_name_map` if the module names differ from package names

Until then, the documented ignore list is the correct solution.
