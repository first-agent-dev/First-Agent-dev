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

## 3. The remaining defect is in the staged layout, not in our scripts

With both fixes in place, an explicit run still reports a large `no_tests` count.
Measured on the already-configured sandbox scope (unchanged by this work):

```
total=689 killed=139 type_invalid=24 no_tests=526 survived=0
```

Diagnosis, verified step by step in the stage directory:

1. `mutmut.setup_source_paths()` inserts `Path("mutants")/p` for
   `p in (".", "src", "source")` **if that path exists**
   (`mutmut/__main__.py:253–259`).
2. At the moment mutmut's own process starts, `mutants/` does not exist yet — it
   is created after the baseline run.
3. `sys.path.insert(0, "mutants/src")` therefore inserts a **non-directory**, and
   Python silently ignores it. Probe in the stage:
   `sys.path[:2] == ['mutants/src', '']`, `os.path.isdir('mutants/src') == False`,
   and `import fa` resolves to the **repository** checkout, not the stage.
4. Mutant trampolines are then never imported, so mutants are reported "no tests"
   rather than killed or survived.

This is why the same sandbox scope shows 526 `no_tests` even though its 95 tests
pass and its 139 killable mutants are killed. It is not caused by this change; it
predates it and it affects the weekly advisory job identically.

## 4. What this means for every claim we have made

- A green mutation result in this repository currently means "the covered subset
  stayed green", not "changed-path mutants were checked". The `no_tests` bucket is
  the unexamined remainder and MUST be read as unknown, never as clean.
- The targeted gate's `nothing to do` and its `no_tests` share the same failure
  mode: **absence of evidence presented as evidence of absence**.
- Any future W1/W2 closeout that cites mutation coverage must quote
  `killed / (total - type_invalid - no_tests)`, not `survived == 0`.

## 5. Not done here, and why

The layout fix is not a one-line change: `also_copy = ["src/fa", "scripts"]` copies
the package to `mutants/src/fa` while mutmut looks for importable roots under
`mutants/`; the working shape needs either `also_copy` to land where mutmut inserts
it, or `source_paths` to be expressed in mutmut's own root convention. Both move
files the weekly job depends on, and both need the full-scope run to validate —
which takes ~2 h on this runner and cannot be shortened without narrowing the
scope again. This is an operator decision (Q139), not a silent edit.

## 6. Cost measured, for the record

- Sandbox-only scope: 689 mutants, 462 s wall on this runner, 139 killed.
- `execution/` adds 99 760 AST nodes against sandbox's 3 137 and session's
  6 672 — roughly 15× the entire previous scope. A single 17 k-line module
  (`journal.py`) alone produced ~100 mutants in 17 s including clean-test and
  forced-fail runs, so the weekly job grows from ~8 min to hours, not minutes.
- `run_slice_mutmut --timeout-seconds` default (18 000 s in CI) is the only thing
  that currently bounds it.
