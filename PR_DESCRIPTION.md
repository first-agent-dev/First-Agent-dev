INTENT: CHORE
INVARIANT: n/a

# chore: harden lint + coverage gates; dedupe provider/tool helpers

## Summary

Makes the Pylint CI job pass and turns the quality toolchain into real,
enforced gates — without changing any runtime behavior. Root cause of the
original red Pylint job: the workflow only installed `pylint`, never the
project, so every third-party import surfaced as a spurious `E0401`
(`pytest`, `markdown_it`, `jsonschema`, `yaml`, `bashlex`). Fixed by
installing `.[dev]` before linting, then configuring Pylint to enforce the
checks that matter for an LLM-assisted codebase and silence the cosmetic
ones.

All gates green: ruff ✅ · mypy --strict ✅ (116 files) · pytest **881 passed
@ 90.70% coverage** ✅ · pylint **src 9.99/10**, **tests 10.00/10**.

## What changed

### CI / quality gates
- `.github/workflows/pylint.yml` — install `.[dev]` (kills all `E0401`);
  two-pass lint: `src/` strict (with `duplicate-code` **ON** — the #1
  LLM-agent smell), `tests/` relaxed via `.pylintrc-tests`.
- `.github/workflows/ci.yml` — single test+coverage source of truth
  (`make check`); uploads `coverage.xml` for GitHub Code coverage analysis.
- `.github/workflows/tests.yml` — mutation testing (`mutmut`), manual +
  weekly, advisory (not a PR gate).
- `pyproject.toml` — `[tool.pylint.*]` (cosmetic checks off, `fail-under`),
  `[tool.coverage.*]` (branch coverage + `fail_under = 90`), `[tool.mutmut]`,
  dev deps `pytest-cov` + `mutmut`.
- `.pylintrc-tests` — tests-only profile (pytest idioms + `C1803` silenced;
  `duplicate-code` off for tests only).
- `.gitignore` — coverage / mutation artifacts.

### Test coverage gap closed
- `tests/test_hygiene_hooks_install.py` — 9 tests for the previously
  **0%-covered** `fa/hygiene/hooks/install.py` (happy path, idempotent
  re-install, `FileExistsError` guard, `--force`, non-workspace + missing-dir
  + missing-script error paths). Branch coverage flagged this gap.

### Behavior-preserving source cleanups (no functional change)
- `inner_loop/hooks/blockers.py` — replaced 3 `__init__` overrides with class
  attributes. NOTE: Pylint's `useless-parent-delegation` was *partly* wrong
  here — the overrides injected category-specific defaults (30s / 5s / 0s),
  so they were not actually useless; the class-attribute form preserves those
  exact defaults (verified) while removing the warning legitimately.
- `providers/base.py` + `anthropic.py` + `openai_compat.py` — extracted the
  byte-identical HTTP status→exception mapping into
  `base.parse_transport_response(response, normalize_success)`; both adapters
  now delegate. Removes the largest real duplicate-code block.
- `inner_loop/tools/base.py` + `prepare_pr.py` — `prepare_pr` now imports
  `require_string` / `optional_string` from `tools.base` (added
  `optional_string`; widened param types `dict` → `Mapping`) instead of
  redefining them.
- `chunker/markdown.py` — `line_end = max(line_end, line_start)` (R1731).
- 5× `except Exception` annotated `# pylint: disable=broad-exception-caught`
  with rationale — all are intentional "never crash the resilience boundary"
  guards (one is the ADR-7 §10 tool-handler audit contract); narrowing them
  would be incorrect, so they are documented, not changed.

### Docs
- `knowledge/llms.txt` — new §Hygiene and §Tooling & CI index entries;
  added the new test + `docs/C1803-fix-plan.md`.
- `docs/C1803-fix-plan.md` — decision matrix for the `== ()` test assertions
  (kept as type-pinning; rule silenced for tests only).

## Why these knobs, for LLM-written code
- `duplicate-code` stays **ON for src/** because agents copy-paste-and-tweak
  instead of extracting helpers ("fix one copy, the other keeps the bug").
- Branch coverage + a 90% `fail_under` is the primary "is it actually tested"
  gate; it already caught the untested `install.py`.
- Mutation testing is the guard against tests that pass but assert nothing.

## Verification
```
make check                                            # ruff + mypy + pytest (90% gate)
pylint $(git ls-files 'src/*.py' 'verifiers/*.py')    # 9.99/10, exit 0
pylint --rcfile=.pylintrc-tests $(git ls-files 'tests/*.py')   # 10.00/10, exit 0
```

## Scope notes
- **No runtime behavior change.** Pure tooling + behavior-preserving
  refactors + new tests. Single intent (CHORE) per the "No mixed PRs" rule.
- 4 `duplicate-code` blocks intentionally left: the two `__all__` re-export
  lists (benign idiom) and the `bash_intent`↔`classifier` command lists
  (documented as deliberately-separate security boundaries).

## AI-session trailer
Co-authored-by: Arena.ai Agent Mode
