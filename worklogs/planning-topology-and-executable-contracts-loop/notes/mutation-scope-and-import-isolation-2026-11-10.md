# Mutation gate: why "0 survivors" was not evidence (2026-11-10)

Raised while acting on the operator decision "extend `source_paths` to
`execution/` — let's try". The extension is committed (`f7da7e0`), but measuring
it exposed a defect in the gate itself that changes what any mutation result in
this repository can be taken to mean.

## 1. The gate was structurally blind to `execution/`

`scripts/run_targeted_mutmut.py::_scope_to_changed` keeps only changed files under
`[tool.mutmut].source_paths`. `src/fa/execution` was not listed, so every managed-
execution change was filtered out and the script printed
`changed files are outside configured production mutation scope; nothing to do`
and returned **0**. That is a green-looking result for an area it never examined.

Fixed by adding `src/fa/execution` to `source_paths` (`pyproject.toml`).

## 2. A second defect: an explicit run lost its package copy

`run_slice_mutmut.request_from_configured_scope` took `also_copy` from config, but
`_request_from_args` in explicit mode passed `also_copy = cli_copies` — and
`run_targeted_mutmut` passed none. So a targeted staged run contained
`source_paths` and `tests/` but **no `src/fa` package copy**, and imported `fa`
from the editable checkout. Observed directly: a run reported

```
Stopping early, because we could not find any test case for any mutant.
```

for every mutant, i.e. a targeted run could never fail on a real survivor.

Fixed: `request_from_configured_scope` gained `also_copy_override`, and
`run_targeted_mutmut` now supplies `_configured_copies()` read from config. The
narrowing of *what is mutated* must not narrow *what the stage can import*.

## 3. What `no_tests` actually is (an earlier diagnosis here was wrong)

An earlier revision of this note claimed the staged layout was at fault:
`mutmut.setup_source_paths()` inserts `mutants/src` only if it exists, `mutants/`
did not exist at that moment, so the insert was a no-op and `import fa` resolved
to the repository checkout. **That claim is false, and it is recorded here so it
is not repeated.** `mutmut/__main__.py::_run` does
`makedirs(mutants)` → `copy_src_dir` → `copy_also_copy_files` → `setup_source_paths()`
(`:1016–1021`), i.e. the copy lands *before* the path setup. Probed directly in a
stage directory with `mutants/src` present: `sys.path[0]` is
`/tmp/q139/mutants/src` and `fa` resolves to
`/tmp/q139/mutants/src/fa/__init__.py` — the staged copy, not the checkout.

The real meaning of `no_tests` is the pytest **exit code 5** ("no tests ran"), via
`status_by_exit_code` (`:77–91`: `1→killed`, `0→survived`, `5→no tests`,
`33→no tests`, `36→timeout`). In the probe that produced `no_tests=526`, one test
file was configured against six mutated modules, so most mutants genuinely had no
test to run. That is a property of the *selection*, not of the layout.

## 3a. The real defect this exposed: the selector never listed execution tests

Reading the config against that finding found something worse than the layout
theory, and it is squarely in the `execution/` scope added by `f7da7e0`:
`pytest_add_cli_args_test_selection` listed **no** `tests/test_execution_*` suite.
A mutant under `src/fa/execution` would therefore have run against sandbox tests
that cannot even import it, and "survived" vacuously — a full-scope green that
means nothing, which is the same "absence of evidence" failure in a new place.
`type_check_command` and `[tool.pytest-gremlins].paths` had drifted from
`source_paths` too, so T19's positional invariant was red.

Fixed together (`8cf42cd`): the 22 execution/s3p3 suites are selected, and both
mirror lists now track `source_paths`. `tests/test_slice_mutmut.py`: 21 passed.

## 4. What this means for every claim we have made

- A green mutation result means "the mutants that had a test stayed green". The
  `no_tests` bucket is the unexamined remainder and MUST be read as unknown, never
  as clean — and it is now known to arise from **test selection**, not from a
  broken stage.
- The targeted gate's `nothing to do` and its `no_tests` share the same failure
  mode: **absence of evidence presented as evidence of absence**.
- Any future W1/W2 closeout that cites mutation coverage must quote
  `killed / (total - type_invalid - no_tests)`, not `survived == 0`, and must name
  the test selection that produced the denominator.

## 5. Not done here, and why

The scope is now *correct*; it is not yet *measured*. A configured-scope run over
the widened scope was attempted on 2026-11-11 and died with `mutmut run returned
-9` (SIGKILL) before producing counts — the runner's memory bound, not a config
error. `mutants/scope-baseline.json` records that run honestly as
`"verdict": "infrastructure_failure"`, `"completed": false`.

So the denominator for `execution/` is still unknown, and no closeout may claim
coverage for it. What is claimed is narrower and verifiable: the scope, the
selector and both mirror lists agree, and T19 pins that they keep agreeing.

## 6. Cost measured, for the record

- Sandbox-only scope: 689 mutants, 462 s wall on this runner, 139 killed.
- `execution/` adds 99 760 AST nodes against sandbox's 3 137 and session's
  6 672 — roughly 15× the entire previous scope. A single 17 k-line module
  (`journal.py`) alone produced ~100 mutants in 17 s including clean-test and
  forced-fail runs, so the weekly job grows from ~8 min to hours, not minutes.
- `run_slice_mutmut --timeout-seconds` default (18 000 s in CI) is the only thing
  that currently bounds it.
