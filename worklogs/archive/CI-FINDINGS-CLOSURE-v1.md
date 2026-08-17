
## 31. STATE ASSESSMENT UPDATE

After the latest coverage batch and test-fixture typing correction:

```text
full mypy: PASS — 270 source files
full pytest: 1805 passed, 13 skipped, 0 failures
coverage: 77.96% < 86% gate
Ruff: 321 repository findings remain
Deptry: 9 issues remain
```

The new coverage test module was brought into the full strict typing contract;
no test-tree type errors remain.

## 32. EXECUTION UPDATE — S3 OPTIONAL DEPENDENCY POLICY CLOSED

Implemented the deferred runtime dependency policy:

- added `[project.optional-dependencies].runtime` for `pymupdf`,
  `pdfminer.six`, `pypdf`, `fastapi`, `pydantic`, and `requests`;
- kept the extra out of default core/dev installation;
- updated `uv.lock` and verified `uv lock --locked`;
- extended `.fa/dependency_contract.toml` with
  `[packages.optional.runtime]`;
- extended the contract checker to include optional runtime packages;
- configured deptry package/module mappings for `pymupdf → fitz` and
  `pdfminer.six → pdfminer`;
- added optional-extra contract tests.

Verification:

```text
uv lock --locked: PASS
uv run deptry src/: PASS
uv run just dependency-contract-check: PASS
focused dependency/runtime/tool tests: 27 passed
```

S3 is now closed. Deferred functionality remains opt-in; the core environment
does not silently acquire FastAPI/PDF dependencies.
