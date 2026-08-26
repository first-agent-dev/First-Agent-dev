# Report — whole-`src` mutation scan feasibility and baseline

- **Date:** 2026-07-29
- **Status:** report only, no config changed by this document
- **Requested:** operator, for later review
- **Related:** [`PLAN-cli-trace-S6.6-mutation-gap-closure.md`](../archive/PLAN-cli-trace-S6.6-mutation-gap-closure.md) §Q26, [`mutation-survivors-workplan.md`](./mutation-survivors-workplan.md)

## 0. Headline — my earlier estimate was wrong, in the operator's favour

In the Q26 analysis I argued whole-`src` was not schedulable: *"~26,600 mutants
… ~916 h … even 1 s/mutant exceeds the 6 h GitHub job cap."*

**That was an extrapolation, and it was wrong by ~5.6×.** It scaled mutant count
by AST-node ratio, which badly over-counts: most AST nodes are not mutable by
any configured operator. Counting the mutants exactly, with the real
`pytest-gremlins` operator classes:

| | Earlier estimate | **Measured** |
|---|---:|---:|
| whole-`src` mutants | ~26,600 | **4,713** |
| wall time at observed rate | ~916 h | **~1.1 h** |
| fits the 6 h job cap? | no | **yes** |

**Whole-`src` is feasible today.** The sharding design (Q26 option (d)) is not
needed. The recommendation in the S6.6 plan should be read as superseded by this
report.

## 1. Method

Mutant counts are **not** estimated. `scripts/count_mutants.py` walks every
`src/fa/**/*.py` AST and asks each configured operator
(`ComparisonOperator`, `ArithmeticOperator`, `BooleanOperator`,
`BoundaryOperator`, `ReturnOperator`) `can_mutate(node)` / `mutate(node)`,
exactly as the plugin does. Reproduce with:

```bash
python scripts/count_mutants.py --json /tmp/mutant_counts.json
```

**Predictor validated against five real runs** before any of it was trusted:

| Scope | Measured (real run) | Predicted | Delta |
|---|---:|---:|---:|
| `src/fa/session` | 120 | 127 | +7 |
| `state.py` | 94 | 96 | +2 |
| `subagent_envelope` + `subagent_runner` | 73 | 73 | **0** |
| `session_db.py` | 73 | 73 | **0** |
| `stats.py` | 164 | 164 | **0** |

Three exact, two within 6 % (the small over-count is nodes the plugin skips at
runtime). Good enough to plan capacity; the number to quote is "~4,700, slight
over-count".

## 2. Mutant inventory — whole `src/fa`

**4,713 mutants across 116 modules** (excluding `__init__.py`).

| Package | Mutants |
|---|---:|
| `src/fa/inner_loop` | 2,043 |
| `src/fa` (top-level modules) | 871 |
| `src/fa/providers` | 278 |
| `src/fa/hygiene` | 243 |
| `src/fa/sandbox` | 242 |
| `src/fa/authoring_rules` | 149 |
| `src/fa/session` | 127 |
| `src/fa/memory` | 109 |
| `src/fa/chunker` | 104 |
| `src/fa/runtime` | 96 |
| `src/fa/observability` | 84 |
| `src/fa/workspace` | 67 |
| `src/fa/skills` | 61 |
| `src/fa/egress_proxy` | 52 |
| `src/fa/telemetry` | 51 |
| `src/fa/blackboard` | 49 |
| others (`tools`, `verifier`, `orchestration`) | 87 |

Top modules by count: `cli.py` 475, `bash_intent.py` 277, `stats.py` 164,
`pr_intent.py` 153, `coder_loop.py` 136, `session/manager.py` 127,
`authoring_rules/tests.py` 119, `loop.py` 100, `state.py` 96.

## 3. Throughput — measured, not assumed

| Run | Mutants | Wall | s/mutant |
|---|---:|---:|---:|
| `src/fa/session` | 120 | 40 s | 0.34 |
| `subagent` pair | 73 | 294 s | 4.02 |
| `state.py` | 94 | 302 s | 3.22 |
| **full configured scope** | **517** | **424 s** | **0.82** |
| `session_db.py` | 73 | 292 s | 4.00 |
| `stats.py` | 164 | 335 s | 2.04 |
| `bash_intent.py` | 269 | 319 s | 1.19 |

Per-mutant cost **falls sharply as scope grows** — 4.0 s/mutant for a single
small module, 0.82 s/mutant at 517. Two reasons: a fixed baseline-collection
cost is amortised, and coverage-guided selection runs only the tests that touch
each mutated line. Small-scope runs are dominated by the fixed cost, so
**extrapolating from a single-module run overestimates badly.**

Projection for 4,713 mutants:

| Rate assumption | Wall | 6 h cap |
|---|---:|---|
| 0.82 s/mutant (observed at scale) | **1.07 h** | fits |
| 1.64 s/mutant (2× pessimistic) | **2.15 h** | fits |
| 4.0 s/mutant (worst single-module rate) | 5.24 h | fits, no margin |

Even the deliberately pessimistic case fits. Caveat: this sandbox has **2
cores**; a GitHub runner is comparable, and `--gremlin-parallel` was **not**
used in any of these runs, so there is unused headroom.

## 4. Kill-rate baseline — everything scanned so far is clean

| Scope | Mutants | Zapped | Survived |
|---|---:|---:|---:|
| `src/fa/session` | 120 | 119 | 0 (1 error) |
| `subagent_envelope` + `subagent_runner` | 73 | 73 | 0 |
| `state.py` | 94 | 94 | 0 |
| configured substrate scope | 517 | 517 | 0 |
| `session_db.py` | 73 | 73 | 0 |
| `stats.py` | 164 | 164 | 0 |
| `bash_intent.py` | 269 | 269 | 0 |

Every run verified against `2213 passed` — see the false-score warning in §6.

**Do not read this as "the suite is complete."** It says the suite is strong
against the *expression* mutation class. It says nothing about statement
deletion — see §5, which is the whole reason S6.6 exists.

## 5. The critical caveat: two mutation classes, not one

`pytest-gremlins` ships **five operators**, all expression-level: flip a
comparison, negate a boolean, shift a boundary, alter arithmetic, change a
return. Introspecting the plugin confirms there is **no statement-deletion
operator**.

`scripts/mutation_sweep.py` deletes whole guard statements. On
`session/manager.py` the two tools disagree completely:

| Tool | Mutation class | Result on `manager.py` |
|---|---|---|
| pytest-gremlins | expression | 119/120 zapped, **0 survived** |
| `mutation_sweep.py` | statement deletion | **8 of 9 survived** |

Same file, same suite, opposite verdicts — and the sweep's 8 survivors were live
security guards (path escape, identity binding, canonical DB path) that could be
deleted with the whole suite green.

**Consequence for a whole-`src` run:** a 100 % gremlins score across 4,713
mutants would be a genuine result about one class of defect and **no evidence
at all** about the class that actually bit us. If whole-`src` scanning is
adopted, the deletion-class sweep must stay a separate, complementary gate.

## 6. Operational warnings

* **A gremlins run that fails to COLLECT still prints a kill percentage.**
  Observed here: `Zapped: 120 gremlins (100%)` with **zero tests executed**,
  because the editable install pointed at a deleted tempdir. **Always confirm
  the `N passed` line before believing a score.** Any CI gate on this tool must
  assert the test count, not just parse the percentage.
* **`--cov` interferes** with coverage-guided selection; the plugin warns
  (`gremlins issue #113`). Run mutation without the coverage flags — relevant
  because `just test` adds `--cov`.
* **Artifacts:** the HTML report lands in `coverage/gremlins/` (now gitignored)
  and the cache in `.gremlins_cache/results.db`, which **is tracked** — a run
  dirties the tree. Worth deciding whether that file should be ignored.
* **1 persistent error mutant** in `src/fa/session` across runs; not yet
  triaged. Errors are not survivors, but they are not kills either.

## 7. Options for the operator

* **(A) Whole `src/fa` in the weekly job.** ~1–2 h, fits the cap. Simplest, and
  now supported by measurement. Adds ~4,200 mutants beyond the current scope to
  the survivor tracker if any survive — on current evidence, few will.
* **(B) Whole `src/fa` advisory + substrate blocking.** Keeps the strict gate
  narrow while getting full visibility. Most conservative.
* **(C) Keep the current substrate scope.** Cheapest run; leaves ~4,200 mutants
  unexamined, including `cli.py` (475) and `bash_intent.py` (277).
* **(D) Sharding.** Was my Q26 recommendation for reaching whole-`src`. **No
  longer justified** — the measurement removes the constraint that motivated it.

**Recommendation: (A), with §5's caveat written into the workplan** — whole-`src`
gremlins coverage plus a separately-tracked statement-deletion sweep, because
the second is where every defect this workstream found actually lived.

Not implemented in this session; recorded for the operator's judgement.
