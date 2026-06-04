INTENT: FIX
INVARIANT: ADR-7 §5 input validation contract; ADR-11-I7 protected-path governance

# fix: jsonschema→fastjsonschema cleanup + ADR-11 security/test gaps

## Summary

One PR covering (1) stale-comment cleanup and contract-preserving
validation-error reconstruction for the `jsonschema`→`fastjsonschema`
swap, (2) ADR-7 amendment with performance rationale and re-evaluation
trigger, (3) registry validation failure tests, (4) ADR-11 symlink-bypass
fix in `check_protected_paths.py`, (5) stdlib-only AST import test +
symlink-to-directory test for `authoring_tcb.py`, and (6) trailing-newline
consistency.

## What changed

### 1. Stale comments — removed `jsonschema` from dependency lists
- `pyproject.toml:171` — dropped `jsonschema` from the pylint comment list.
- `.github/workflows/pylint.yml:24` — same.

### 2. Validation error format — reconstruct old `message at path` contract
`src/fa/inner_loop/registry.py:163-169`

`fastjsonschema.JsonSchemaValueException` exposes `.message` (human
description with dotted path), `.path` (list path), and `.name` (dotted
path string). Reconstruct the old `jsonschema.ValidationError` output shape:

```python
path = "/".join(str(part) for part in exc.path) or "<root>"
return ToolResult.fail(
    "invalid_params",
    f"{exc.message} at {path}",
    retryable=True,
)
```

This preserves the downstream contract (tests assert `"text" in
error.message`) and keeps the `at <path>` suffix that any prompt or audit
consumer may rely on.

### 3. Registry validation failure tests
Added to `tests/test_inner_loop_registry.py`:
- `test_register_rejects_malformed_schema` — `ValueError("invalid
  input_schema")` on schema `{"type": "strin"}`.
- `test_validate_returns_invalid_params_on_type_mismatch` — dispatch with
  wrong type produces `error.code == "invalid_params"` and `"text" in
  error.message`.

### 4. ADR-7 §5 amendment
- Replaced `"jsonschema"` with `"fastjsonschema"`.
- Added performance rationale (~10× faster, compiles schema to Python
  function, zero transitive deps).
- Added re-evaluation trigger: "if fastjsonschema drops Draft 2020-12
  support, or the compiled-validator ABI changes incompatibly, re-evaluate
  the dependency choice."
- Updated error-message description: "`error.message` carries the
  library-generated description with the failing JSON path."
- Fixed stale dependency name in §Consequences (`jsonschema` →
  `fastjsonschema`).

### 5. Symlink-to-prefix bypass fix in `check_protected_paths.py`
**Bug:** `is_protected` compared `candidate_real == os.path.realpath(target)`
only for exact paths in `_TCB_PATHS`. A symlink to a file under a protected
prefix (e.g. `authoring_rules/exports.py`) bypassed because `exports.py` is
not in `_TCB_PATHS`.

**Fix:** After the exact-path loop, added prefix realpath check:

```python
for prefix in _TCB_PREFIXES:
    prefix_real = os.path.realpath(repo_root / prefix)
    sep = os.sep
    if candidate_real == prefix_real or candidate_real.startswith(prefix_real + sep):
        return True
```

### 6. Regression test for symlink-to-prefix bypass
Added `test_is_protected_catches_symlink_to_prefix` to
`tests/test_authoring_check_cli.py`. Gracefully skips on Windows without
admin symlink privileges.

### 7. Stdlib-only import test for `authoring_tcb.py`
Added `test_authoring_tcb_imports_only_stdlib` to
`tests/test_authoring_tcb.py` — uses `ast` + `sys.stdlib_module_names` to
verify every top-level import is stdlib-only (ADR-11-I1).

### 8. Symlink-to-directory test for `_walk_files`
Added `test_enumerate_paths_skips_symlink_to_directory` to
`tests/test_authoring_tcb.py` — verifies `enumerate_paths` does not include
`link_dir/file.py` when `link_dir` is a symlink to `real_dir`.

### 9. Trailing newlines
- `src/fa/authoring_rules/README.md` — added terminating newline.
- `.github/workflows/authoring-guardrails.yml` — added terminating newline.

### 10. Review fixes ( Issues A–D )
- Removed unused `import os` from `test_authoring_check_cli.py`.
- Stripped trailing whitespace from blank lines in test files.
- Fixed import ordering (`import sys` grouped with stdlib imports).

## Verification

```bash
python -m pytest tests/test_inner_loop_registry.py tests/test_inner_loop_validation.py -v
python -m pytest tests/test_authoring_tcb.py tests/test_authoring_check_cli.py -v
python scripts/check_protected_paths.py --repo-root . --base origin/main
```

## Scope notes
- **Single intent (FIX).** The PR fixes real bugs (stale-comment drift,
  validation-error contract break, symlink bypass) and fills security/test
  gaps identified in review.
- **No breaking changes.** The validation-error format change is a
  contract-preserving reconstruction, not a new shape.
- **Windows compatibility.** Symlink tests gracefully skip when privileges
  are unavailable.

## AI-session trailer
