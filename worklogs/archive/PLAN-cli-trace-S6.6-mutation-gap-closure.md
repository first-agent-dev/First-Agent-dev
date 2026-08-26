> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN — S6.6: mutation-gap closure for the S1–S6 substrate

- **Status:** S6.6a–S6.6d COMPLETE (2026-07-29). Whole-`src` scope is a separate
  operator decision — see [`REPORT-full-src-mutation-scan-2026-07-29.md`](./REPORT-full-src-mutation-scan-2026-07-29.md).
- **Date:** 2026-07-29
- **Parent:** [`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md)
- **Predecessor:** [`PLAN-cli-trace-S6-observability-contracts.md`](./PLAN-cli-trace-S6-observability-contracts.md) §S6 mutation sweep

## 1. Why this slice exists

The S6 audit found test theater by accident. That prompted a mutation sweep of
S6, which found four survivors — three of which survived the **entire** suite.
This slice extends that sweep to S1–S6 and closes what it found.

**The root enabler, measured:** `pyproject.toml` `[tool.mutmut] source_paths =
["src/fa/sandbox"]`. Mutation testing has only ever run against the sandbox
modules. The CLI-trace substrate — session manager, session DB authority,
EventLog, coder_loop, subagent runner, output bus — has **never** been mutation
tested. "The suite is green" was therefore not evidence for any of it, and the
`mutation-survivors-workplan.md` table (which reads `total 37 remaining`)
describes only the sandbox.

## 2. Method

`scripts/mutation_sweep.py` — a small, auditable harness, deliberately not a
second mutation framework. It applies one textual mutation, installs the mutant
as the editable package, asserts the resolved import root is inside the mutant
copy, runs the suite, and classifies the outcome.

Two harness bugs were burned during the S6 sweep and are now guarded, because
each produced a **confidently wrong** result in a different direction:

| Bug | Wrong answer it gave | Guard now in place |
|---|---|---|
| `PYTHONPATH=<copy>/src` resolved `fa` but hid installed third-party deps | every mutant "survived" via a silent collection error | mutant is `pip install -e`'d; import root asserted inside the copy; `N error` is its own outcome, never "survived" |
| substring match on the summary line | `1 xfailed` read as a failure → caught mutant reported as caught when it wasn't | counts parsed with `(\d+) failed`; `xfailed` cannot match |

A pattern that is absent, or a mutation that leaves the file byte-identical, is
reported `SKIP`. Counting those as "survived" is how a sweep talks itself into
false confidence. The harness is self-validated before each use against a
known-caught control and a known-absent pattern.

## 3. Findings

16 mutations across S1–S6, each neutralising a guard a plan or ADR claims is
enforced. Full suite as the oracle (2196 tests).

| Slice | Caught | Survived |
|---|---:|---:|
| S1–S4 (`session/manager.py`) | 1 | **8** |
| S5–S6 (authority, blackboard, output, runner) | 6 | **1** |

**S5/S6 are in good shape.** `BEGIN IMMEDIATE`, blackboard self-conflict
suppression, `kind_counts` commit ordering, the S6.5 fail-closed mask, the S6.2
stop scope, and multi-listener delivery all have tests that bite.

**S1's session manager is the concentration of risk.** An AST inventory of
every `SessionManagerError(...)` raise site:

```text
total codes=24   named in no test=16
```

Reachability was verified rather than assumed — each guard was driven by
tampering a real manifest through the public API:

| Tamper | Guard that fired |
|---|---|
| `session_id` → another session | `manifest_identity_mismatch` |
| `schema_version` → 999 | `manifest_unsupported` |
| `status` → `archived` | `session_not_active` |
| `session_db_path` → `/tmp/evil.db` | `path_escape` |
| `workspace_path` → `/tmp/evil-ws` | `path_escape` |
| `session_db_path` → non-canonical, in-root | `manifest_path_mismatch` |

So these are **live guards with no test**, not dead defensive code. Every one
can be deleted today and the suite stays green.

### 3.1 The two shapes, and why they differ

**Shape A — the untested layer of a defended pair.** `workspace_escape` is
raised at `manager.py:182` *and* `:248`. `test_session_lifecycle.py` asserts the
code, so the pair looks covered — but the assertion is satisfied by `:248`
alone. Deleting `:182` is invisible; deleting **both** fails the test. The test
pins *the outcome*, and one layer silently suffices.

This matches the failure mode the defense-in-depth literature warns about:
*"If the layers of defense are not independent, one failure can cascade through
everything and defeat the entire point."* Untested redundancy is not
redundancy — it is one working control plus one that may already be broken.
FAR.AI's STACK work on layered AI defenses makes the same point empirically:
layers must be attacked **individually**, or the stack's strength is assumed
rather than measured.

**Shape B — the never-exercised error path.** `manifest_identity_mismatch`,
`manifest_path_mismatch`, `session_not_active`, `manifest_unsupported`,
`invalid_session_id`, `invalid_run_id`: raised in production, named nowhere.
The industry framing is blunt — *"the happy path gets tested; the error paths,
the ones that matter most when things go wrong in production, often have zero
effective coverage despite what the metrics say."* Coverage agrees: these lines
**are executed** by happy-path tests that never reach the raise, so line
coverage counts them as covered.

### 3.2 Contradicted claim

`cli-trace-S2-verification-report.md` §6 records
`| workspace mismatch/path escape | PASS C3 |` and
`| corrupt/missing manifest | PASS C3 |`. Both are true only for the *outer*
layer and the JSON-decode case. Manifest **tampering** — identity, schema,
status, canonical DB path — is unverified. The report is not wrong about what
it ran; it is over-broad about what that proves. S6.6 corrects the record.

## 4. Sub-slices

### S6.6a — session-manager guard independence *(implemented in this session)*

**Contract/gap IDs:** S1 Q10 manifest contract; S2 report §6 rows
"workspace mismatch/path escape", "corrupt/missing manifest"; sweep IDs
S1-M1, M2, M3, M4, M6, M7, M8, M9.

**Files allowed to change:** `tests/test_session_manifest_guards.py` (new),
`scripts/mutation_sweep.py` (new), `scripts/sweep_specs/*.json` (new),
this plan. **No production file changes** — every guard already behaves
correctly; only the proof is missing.

**Tests-writing class:** C3 (adversarial, security boundary), with one C0
inventory guard.

**Mechanism.** Drive the **public** API (`create_or_attach_session`) against a
tampered on-disk manifest, one field per test, asserting the specific
`SessionManagerError.code`. Plus a registry test that fails when a new error
code is added without a test — so this gap cannot silently reopen.

**Failure behavior.** Each guard must raise before any mutation of state; the
tests assert the error code, not just that something raised.

**DoD / negative proof.** Each of the 8 surviving mutations flips to CAUGHT.
Recorded below with actual output.

### S6.6b — extend mutation scope to the substrate *(RESOLVED and implemented 2026-07-29)*

**Operator answered Q26: substrate scope now** (option (c)). Implemented in
`pyproject.toml` for **both** tools:

```toml
source_paths = ["src/fa/sandbox", "src/fa/session",
                "src/fa/inner_loop/state.py",
                "src/fa/inner_loop/subagent_envelope.py",
                "src/fa/inner_loop/subagent_runner.py"]
```

`pytest_add_cli_args_test_selection` gained the substrate's own suites —
without them a mutant in `state.py` would run against sandbox-only tests and
"survive" vacuously, which is the failure mode this whole slice exists to stop.

**pytest-gremlins was run, as requested.** Measured against the real suite
(`2213 passed` verified on every run):

| Module | Gremlins | Zapped | Survived |
| :--- | ---: | ---: | ---: |
| `src/fa/session` | 120 | 119 | 0 (1 error) |
| `subagent_envelope.py` + `subagent_runner.py` | 73 | 73 | 0 |
| `state.py` | 94 | 94 | 0 |
| **full configured scope** | **517** | **517** | **0** |

**The two tools are complementary, and the difference matters.** gremlins
mutates *expressions*; introspection of the plugin confirms it has **no
statement-deletion operator**. `mutation_sweep.py` deletes whole guards. That
is why gremlins finds 0 survivors in the same `manager.py` where the sweep
found 8 — a clean gremlins run is **not** evidence about guard deletion, and
vice versa. Recorded in both configs so a future reader cannot conclude one
retires the other.

**Whole-`src` remains out of reach as a single job** (Q26 measurement below);
option (d), sharding, is the path if that is wanted.

#### Harness defect found and fixed while running gremlins

The first gremlins invocation printed **`Zapped: 120 gremlins (100%)`** — and
was entirely false: the tests had failed to *collect*, so zero tests ran.

Root cause was in my own sweep harness. `pip install -e` on a mutant rewrites
the interpreter-wide `_editable_impl_first_agent.pth`; when the tempdir was
deleted, the host environment was left importing a path that no longer existed.
Every later command in the session got `ModuleNotFoundError: No module named
'fa'`, and gremlins summarised that collection error as a 100 % kill rate.

Fixed by `_restore_host_install()` in a `finally`, so the host install is
repaired after **every** mutant including SKIP and error paths. Verified: the
`.pth` points at `/home/user/repo/src` after a sweep. This is the third bug of
the same family (a broken harness reporting success), which is why the
"confirm `N passed` before believing a score" rule is now written into
`pyproject.toml` next to the gremlins config.

### S6.6b-original — extend mutmut scope beyond `src/fa/sandbox` *(superseded by the above)*

The sweep harness is for reviewing a delta; it is not a substitute for the real
tool. `[tool.mutmut] source_paths` should grow to include
`src/fa/session` and `src/fa/inner_loop/state.py` at minimum.

**Not done in-session, and the reason is a policy choice → Q26.** mutmut runs
weekly and non-blocking (`tests.yml`, `continue-on-error: true`), gated on the
survivor table reaching zero. Widening the scope injects a new survivor
population into a tracker whose *deletion* is the trigger to make the gate
blocking. That trade — slower path to a blocking gate vs. real coverage of the
substrate — is the operator's call, not mine.

### S6.6c — layer-independence for multi-site guards *(DONE 2026-07-29)*

The original note said the "annotate every redundant guard" option was
"ceremony without a measured second instance of the problem." **The second
instance was then found**, so the question was settled by measurement rather
than preference.

**Method.** An AST sweep enumerated every error code raised at **2+ sites** —
that is the shape-A risk, because an assertion on the *code* can be satisfied
by one layer while another is silently deletable:

| File | Multi-site codes |
|---|---|
| `session_db.py` | `session_db_identity_mismatch` ×5, `session_db_schema_unsupported` ×4 |
| `session/manager.py` | `manifest_corrupt` ×3, `workspace_invalid` ×3, `workspace_escape` ×2, `run_id_reused` ×2 |
| `cli.py` | `StatsSourceError("manifest_corrupt")` ×3 |
| `hooks/base.py` | `hook_double_mutation` ×2 |
| `runtime/pty_pool.py` | `tmux server unavailable` ×2 |

**Measured result** (`scripts/sweep_specs/s6_6c_layer_independence.json`):

* **L1 — `session_db.py:281`, the open-time identity guard: SURVIVED.** All
  2213 tests green with it deleted.
* L2 — the schema-version guard: CAUGHT.

L1 matters. The other four `session_db_identity_mismatch` sites guard *writes*
and compare a row's `session_id` to the instance. This one guards the **open**:
it compares the DB's persisted marker against the id the caller claims, and it
is the only thing stopping `open_existing` from attaching to another session's
authority. Six production call sites depend on it (`cli.py:137,2507`,
`manager.py:322,374,390`, `stats.py:289`). Verified live before writing the
test: a DB stamped `session-A` opened as `session-B` raises correctly.

**Closed** by two tests in `test_session_manifest_guards.py` — the rejection
case and a happy-path control, because a guard test that only asserts rejection
is satisfied by a guard that rejects everything. Negative proof: L1 flips
`SURVIVED → CAUGHT`, L2 stays CAUGHT.

**Conclusion on the original fork:** the per-layer-test option is the right one
and needs no annotation mechanism. The reusable artefact is the *probe* — the
multi-site enumeration plus a one-layer-at-a-time spec — kept in
`scripts/sweep_specs/` so the next slice can re-run it rather than rediscover
the technique.

### S6.6d — correct the S2 verification report *(DONE 2026-07-29, doc-only)*

`cli-trace-S2-verification-report.md` §6 carried
`| workspace mismatch/path escape | PASS C3 |` and
`| corrupt/missing manifest | PASS C3 |`. Both were accurate about what was
*run* and over-broad about what it *proved*. Amended with a footnote recording
that the first covered only the outer `workspace_escape` layer and the second
only unreadable JSON (not manifest tampering), and pointing at
`test_session_manifest_guards.py` and this plan. The rows are not deleted — the
original claim stays visible next to its correction.

## 5. Open question

### Q26 — RESOLVED (operator, 2026-07-29): option (c), substrate scope now.

Implemented in S6.6b above for both `mutmut` and `pytest-gremlins`, with
substrate survivors tracked in their own section of
`mutation-survivors-workplan.md` so the BACKLOG I-23 sandbox trigger keeps its
meaning. Whole-`src` (the operator's longer-term goal) stays open as option (d)
— sharding — because the measurement below shows it cannot run as one job. The
original analysis is kept for the record.

### Q26 — original analysis: mutmut scope vs. the blocking-gate trigger

Widening `source_paths` beyond `src/fa/sandbox` is the durable fix for the root
cause. Two constraints interact, and the operator asked specifically about
widening to the whole `src` tree, so both are measured below.

**Constraint 1 — the blocking-gate trigger.**
`mutation-survivors-workplan.md` is deleted when its table hits zero, and that
deletion flips `tests.yml` to blocking (BACKLOG I-23). Adding the substrate now
adds survivors to that table and delays the trigger.

**Constraint 2 — runtime, measured.** Mutation cost scales with mutant count ×
suite time. Current state: 633 mutants for `src/fa/sandbox` (6 files); whole
`src/fa` is 139 files and ~42× the AST nodes, so ~26,600 mutants. Full suite is
**124 s** wall.

| Strategy | Est. wall time | Fits a weekly job? |
|---|---:|---|
| whole `src`, full suite per mutant | ~916 h (38 days) | no |
| whole `src`, coverage-selected subset (~5 %) | ~46 h | no (6 h job cap) |
| whole `src`, optimistic 1 s/mutant | ~7 h | still over the cap |
| substrate slice only (`session`, `state.py`, `subagent_*`) | ~1–3 h | yes |

`tests.yml` sets no `timeout-minutes`, so the GitHub default **6 h** job cap
applies. Whole-`src` in a single weekly job is therefore not viable as-is,
independent of the I-23 question. This matches the guidance in the field: start
with modules carrying real business rules — validators, permission checks,
parsers — because "thin framework glue and generated models usually produce
noisy mutants."

**Options.**

* **(a) Widen to the whole `src` now.** Maximum coverage; does not fit the job
  cap, and floods the tracker.
* **(b) Keep mutmut on sandbox; close I-23 first, widen after.** Protects the
  existing plan; the substrate stays unmutated in CI meanwhile.
* **(c) Widen to a *substrate* scope with a separate survivor section.** Adds
  `src/fa/session`, `src/fa/inner_loop/state.py`, `subagent_envelope.py`,
  `subagent_runner.py` — the guard-dense, security-adjacent modules this sweep
  found gaps in — while leaving the sandbox trigger untouched.
* **(d) Whole `src`, but sharded across weeks** (a rotating slice per run) with
  a combined stats file. Reaches full coverage eventually; needs shard
  bookkeeping and makes any single run's result partial.

**Recommendation: (c) now, (d) as the path to the operator's whole-`src` goal.**
(c) is the only option that both fits the job cap and targets where the measured
defects actually were — every survivor in this sweep was a *guard*, not glue.
(d) then extends coverage without pretending a 26,600-mutant run fits in one
job. (a) is the stated goal but cannot be scheduled today; if it is required,
the honest form of it is (d).

**Note on precedent.** `pyproject.toml` already configures `pytest-gremlins`
with the same `src/fa/sandbox` scope. It advertises coverage-driven test
selection and parallel execution, which is exactly the mechanism (d) needs; if
whole-`src` is the goal, benchmarking gremlins against mutmut on one substrate
module is the cheapest next experiment.

## 6. Execution record — S6.6a (2026-07-29)

**Shipped.** `tests/test_session_manifest_guards.py` (16 tests),
`scripts/mutation_sweep.py`, `scripts/sweep_specs/{s1_s4,s5_s6}_substrate.json`,
this plan. **Zero production changes** — `git diff --stat -- src/` is empty. The
guards were always correct; only the proof was missing, and inventing a
production change to "fix" a test gap would have been the wrong move.

**Negative proof — the whole point of the slice.**

```text
before:  caught=1 survived=8 skipped=0 harness-fail=0
after:   caught=9 survived=0 skipped=0 harness-fail=0
```

Every mutation that previously survived the full suite now fails it. The
forcing function was kill-checked separately: injecting a brand-new
`SessionManagerError("brand_new_untested_code", ...)` fails
`test_every_error_code_is_named_in_some_test` (`1 failed, 15 passed`), so the
gap cannot silently reopen.

**Gate.** pytest **2212 passed** / 15 skipped / 1 xfailed (was 2197 — **+15,
zero regressions**) · coverage **81.27%** ≥ `fail_under = 80` · bare
`python -m mypy` clean (311 files) · `pyrefly check` 0 errors · `ruff check` +
`format --check` clean · `pylint src/fa` **10.00/10** · `deptry` clean · all 9
`scripts/check_*.py` PASS · `fa authoring-check` 0 diagnostics.

**Three findings during implementation, each caught by a different gate:**

* **`pyrefly` caught a real typing defect that `mypy` did not** —
  `tests=tuple(str(t) for t in tests)` iterating `object`. Fixed per AGENTS.md
  by validating at the boundary rather than annotating around it: a malformed
  `tests` value now raises, and an **empty** one raises too. That second check
  matters more than it looks — a spec with no tests would have run zero tests
  and reported `SURVIVED`, i.e. the harness would have manufactured false
  findings. Same class of bug as the two already burned.
* **`S603` on `subprocess.run` — fixed, not waived (corrected on review).**
  The first pass added `# noqa: S603` with a rationale. That was the wrong
  call: AGENTS.md says a judgment finding "signals a design problem — fix the
  design that caused the finding", and a waiver is only for a pattern that is
  genuinely intentional.

  Probing ruff pinned down what it objects to: an all-literal argv passes, and
  **any** variable splatted into argv is flagged — the rule cannot see caller
  validation, so decorating the call could never clear it honestly. The data
  flow itself had to go.

  Removing it was also a subtraction win. The per-mutation `tests` field was
  **unused generality**: all 16 shipped mutations passed `["tests/"]`. Worse, it
  was a footgun — a mis-specified subset would silently narrow the oracle and
  manufacture a false `SURVIVED`, the same class of bug as the two harness
  failures already burned. Whole-suite is the semantically correct oracle for
  "would *any* test notice?".

  Result: the field, the `Mutation.tests` attribute, and its boundary
  validation are all deleted; the argv is a fixed literal; **the file contains
  zero `noqa` directives** and ruff passes clean. Re-running
  `s5_s6_substrate.json` reproduced the verdicts exactly (`caught=6
  survived=1`), and the three self-validation controls (known-caught,
  absent-pattern, no-op) all behave correctly — so the refactor changed the
  design, not the findings.

  **Function-preservation audit** (asked at review: does the tool still do its
  job after the reduction?). Every documented capability was exercised
  post-change, not assumed:

  | Capability | After | Evidence |
  |---|---|---|
  | detect CAUGHT | kept | `F1` → CAUGHT (9 failed) |
  | detect SURVIVED | kept | live sweep `S5-M1` SURVIVED |
  | SKIP: pattern not found | kept | `F2` |
  | SKIP: no-op mutation | kept | `F3` |
  | SKIP: file not found | kept | `F4` |
  | HARNESS-FAIL on collection error | kept | classifier untouched |
  | import-root escape guard | kept | untouched |
  | `--only` selector | kept | ran exactly 1 |
  | `--keep` | kept | untouched |
  | exit 2 on unknown `--only` | kept | `exit=2` |
  | exit 1 on survivors / harness-fail | kept | untouched |
  | malformed spec rejected | **improved** | `ValueError` on missing key |
  | per-mutation test subset | **removed** | unused; all 16 specs sent `["tests/"]` |

  One capability removed, and it was dead generality whose only live effect was
  a false-`SURVIVED` footgun.
* **A comment beginning `# noqa justification…` was parsed as a directive**
  (`PGH004` + `RUF100`). Reworded. Worth recording: prose explaining a waiver
  must not start with the token it explains.

**Scope note.** S6.6a proves the guards are independently live. It does **not**
put the substrate under weekly mutation testing — that is S6.6b and needs Q26
answered. The sweep harness is a review tool for a slice delta, not a
replacement for mutmut.
