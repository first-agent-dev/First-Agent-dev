# PLAN: S9 — verify stats and derived projections (and harden the guards)

Plan-ID: `PLAN-cli-trace-S9-stats-projections`
Status: **COMPLETE (2026-07-31)** — all 7 steps executed. Gate green:
2272 passed, mypy 315 files clean, pylint 10.00/10, authoring-check 0,
mutation 6/6 + 164/164. Execution record in §11.
Previously: **READY** — Q36 resolved by the operator (option **c**).
Depth: **P1** — one contained capability area (stats + the derived
projection). No new subsystem, no migration, no cross-service change. The one
production edit (`_parse_since` validation) is a single function.
Revision: **v1 (reviewed)** · Changed-since-last: preflight-only v0 → full
plan, then a **self-review pass** that found three defects in this plan:
**(A)** **F4 withdrawn** — it was manufactured by a broken preflight regex
(`[a-z_]+`, no digits) that hid six `compaction_stage2/3_*` kinds and made
`LogKind` look like 27 members instead of **33**;
**(B)** S9.2's "guard both call sites" replaced with **one pre-dispatch
guard** — the `--global-history` filter sits inside a broad `try/except` that
returns 1, which is the wrong home for a usage check;
**(C)** **Q39 raised** — the draft silently decided that an invalid `--since`
is ignored when `--run-id` is set.
· Then a **second review pass** (code-reading, v1-reviewed) found three more:
**(D)** **CT3's equality assertion was wrong and would fail on day one** —
measured: only `cli.py` imports `global_history`; `stats.py` references it
zero times and a module cannot import itself. Changed to a **subset**
assertion plus two liveness controls;
**(E)** the plan named five C2 tests against `_cmd_stats` but **never
specified its Namespace** — AST-extracted the exact seven attributes and
mandated a shared `_stats_args` helper;
**(F)** the new guard must use `getattr(args, "since", None)` — the two
existing call sites disagree (`:2689` getattr vs `:2730` bare attribute).
Upstream context: parent
[`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md)
§Step S9 (line 1796); depends on **S5** and **S8**, both COMPLETE.
Operator decision 2026-07-31: **Q36 = option (c)**.

> **Tests-writing authority.** Every test named here MUST be written under
> [`knowledge/skills/tests-writing/SKILL.md`](../../knowledge/skills/tests-writing/SKILL.md)
> — class declared in the docstring (C0/C0p/C1/C2/C3), ranked oracle named,
> producer kill-check named, honest fixtures, existence pre-check, no
> `TEST-EDITS` weakening of an existing assertion, and **no C0-consumer test
> left unpaired** (skill §10). This is DoD item, not advice.

---

## Preflight log (§2 — run 2026-07-31, measured not assumed)

### Environment

Sandbox had reset: `pip install -e .` + tooling re-installed. Working tree
clean; the 16-file `scripts/`+`hooks/` diff was the known **file-mode**
artifact (**0 content lines**, `git diff --numstat`) and was restored.
Base: `df5d1c0` (S8 COMPLETE).

### 1. Composition roots located

| Root | Site | Note |
|---|---|---|
| `fa stats` CLI | `cli.py:2653` `_cmd_stats` | dispatches `--global-history` first, then session analytics |
| source discovery | `cli.py:2575` `_discover_stats_sources` | validates manifest identity; **never** instantiates `SessionManager` (a read command must not create state) |
| authority parser | `stats.py:277` `parse_session_db` | the production path |
| legacy parser | `stats.py:261` `parse_session` | **no production caller** (grep-verified); docstring says so |
| shared core | `stats.py:303` `_parse_events` | both parsers converge here |
| row→event adapter | `state.py:114` `TraceEvent.from_row` | one constructor shared by `EventLog.read_all` and stats |
| derived projection | `global_history.py:220` `GlobalHistoryStore.read_all` | `SELECT *` ordered by `updated_at` |
| since-parser | `cli.py:2797` `_parse_since` | pure helper, two call sites |

### 2. Greps run → findings

| Pattern | Finding |
|---|---|
| `parse_session(` in `src/` | **zero production callers** |
| `parse_session_db` in `src/` | `cli.py:2753` only |
| `LogKind` literal | **33** members (`output.py`) — via `typing.get_args`, **not** a regex; see the v1-review correction below |
| `kind == "…"` in `stats.py` | **23** dispatched (all exact equality; there is **no** `startswith` dispatch) |
| `UNPARSED_KINDS` | `stats.py:65`, **10** members, each with a written reason |
| `global_history` importers (**AST**, not grep) | `cli.py:1845`, `:2279`, `:2670` — **only** `cli.py`. A string grep also hits `output.py`, which is a *docstring mention* (my own S8.4 text). **This is why the F2 fix must be AST-based.** |
| `_parse_since` in `tests/` | **zero** — untested pure parser |
| `stats.py` in `pyproject.toml` mutation scope | **absent** — 887 lines never mutation tested |

### 3. Gold patterns to mirror

- `tests/test_s19_stats_parsers.py:152` — `test_unparsed_kinds_complete`, the
  contract-completeness shape to **extend, not duplicate**.
- `tests/test_global_history_export.py:345` — `test_global_history_is_projection_only`,
  the real Do#4 check being hardened.
- `scripts/check_log_kind_contract.py:172` — `SRC_FA.rglob("*.py")`, the
  **whole-tree scan** prior art F2 should follow instead of a fixed list.
- `tests/test_stats.py:363`, `:388` — the two DB-path tests.
- **Fixture honesty (run side):** `_run_args` (`test_s7_cli_run_paths.py:47`)
  is the correct full `fa run` namespace, and it is importable cross-module
  (`from tests.test_s7_cli_run_paths import _run_args`; the same file already
  does `from tests.test_cli import …`, so the precedent exists). **`_make_run_args`
  alone is insufficient** — it predates the session selector, so a run built
  from it takes the legacy path and creates no `sessions/<id>/manifest.json`.
  Measured during preflight (my first probe failed on exactly this).
  End-to-end verified during the v1 review: `_run_args` → `_cmd_run` → 1
  manifest → `parse_session_db` → analytics `turns=1 in=1 out=1` matching the
  `global_history` row, all non-zero.

- **Fixture honesty (stats side) — `_stats_args`, NEW, mandated.** `_cmd_stats`
  reads exactly **seven** attributes, extracted by AST during the v1 review:

  ```text
  dead_zones · global_history · output · run_id · session_id · since · workspace
  ```

  The v1 draft named five C2 tests against `_cmd_stats` **without specifying
  the Namespace**, which would have left the executor reverse-engineering it
  from two inconsistent existing examples (`test_cli.py:1039` sets
  `session_id`; `test_stats_global_wiring.py:62` omits it). S9.2 must add one
  `_stats_args(**overrides)` helper in the new test module that sets all seven
  with sane defaults, so every S9 C2 test builds the same shape and a future
  attribute addition breaks in one place.

### 4. Conflicts / invariants

- Parent §Do-not (binding): **no typed event-union migration** just to remove
  `dict.get()` calls; **do not** silently change old-session compatibility
  while changing authority.
- `_discover_stats_sources` deliberately raises `legacy_trace_unsupported`
  rather than silently reading legacy JSONL. Old-session compatibility is
  already an explicit, tested decision — S9 must not soften it.
- BACKLOG `I-36`/`I-37`/`I-39` remain deferred by operator decision.
- S8.4's stdout contract: payload on stdout, human/progress on stderr.

### 5. As-is liveness per parent Do-item (§4 scale)

| Parent Do | Liveness | Evidence |
|---|---|---|
| **#1** discovery uses intended authority/compat path | **L3** | `_discover_stats_sources` validates `session_id`, `session_db_path` vs expected, manifest `status`, run binding; legacy raises a coded error; `open_existing` has no bootstrap side effect |
| **#2** complete / incomplete / malformed / DB-only | **L3** | `test_stats.py` nonexistent + corrupt-lines + DB-only (`:363`, `:388`); errors map to `StatsSourceError` |
| **#3** kinds parsed or explicitly unsupported | **L3** | `UNPARSED_KINDS` + two enforcing tests; **23/23** parsed kinds also have a behavioural test (measured) |
| **#4** global-history derived, not hot-path | **L2** | guard exists but is a hardcoded 7-file denylist; **132 of 139** modules unguarded |
| **#5** workflow aggregate measured, not hardcoded | **L3** | **S8 already closed this** — `duration_ms` (S8.2), `stop_reason` (S8.7), `role`/`turns` asserted |
| **#6** read-all complexity | **n/a** | parent gates this on "correctness policy stable"; deferred, see §7 Q38 |

### 6. Measured — exit criteria probed directly, not inferred

**Exit criterion 1 — "derived consumers agree with authority rows on a fresh
trace."** Ran the real `_cmd_run`, then compared `stats.parse_session_db`
against the `global_history` row for the same run:

```text
AUTHORITY (stats.parse_session_db) vs DERIVED (global_history):
  turns=1/1   input_tokens=1/1   output_tokens=1/1   AGREE? True
```

**`_parse_since` behaviour table** (pure function, twelve inputs):

```text
'7d'→604800  '24h'→86400  '30m'→1800  '  7D  '→604800  '7.5d'→648000
'7'→None  'abc'→None  ''→None  'd'→None  '0d'→0.0
'-5d'→-432000.0   ← NEGATIVE     '1e3h'→3600000.0   ← scientific notation
```

**`aggregate_sessions([])`** degrades cleanly to a zeroed dict (no crash).

### 7. Findings — the S9 scope

Ordered by value. **F6 is the only production defect**; the rest are guards
that cannot fail, and one missing mutation scope.

**F6 — `--since` accepts a negative duration and silently returns nothing.**
`_parse_since("-5d")` → `-432000.0`. Both call sites compute
`cutoff = time.time() - since_seconds`, so a negative pushes the cutoff **into
the future** and every session is excluded. The operator sees
`fa stats: no matching sessions found` — indistinguishable from "you have no
sessions". Measured. `1e3h` is likewise accepted (scientific notation via
`float()`), which is not a defect but is undocumented. Severity **P2**: wrong
answer, silent, on an operator-facing filter.

**F2 — the projection-only guard is a hardcoded 7-file denylist.**
`test_global_history_is_projection_only` names 7 hot-path files. All 7 still
exist, but `src/fa` has **139** modules, so **132 are unguarded** — a new
hot-path module importing `global_history` is invisible to CI. Must be fixed
with an **AST** scan, not a string scan: `output.py` contains the literal
`global_history` in a docstring and would be a false positive.

**F3 — `test_stats_global_history_projection_only` is tautological.**
`tests/test_stats_global_wiring.py:92`. Despite its name it asserts
`"global_history" in cli.py` — a *presence* check that cannot detect a
hot-path import, and it passes for 17 unrelated reasons (measured: the string
occurs 17× in `cli.py`). Its own comment concedes it defers to the real check.
Same class as the S7.C3 contradictory predicate and S8's ceremonial consumer:
**a check that cannot fail.**

**F7 — `stats.py` (887 lines) is in no mutation scope.**
Neither `[tool.mutmut] source_paths` nor `[tool.pytest-gremlins] paths`
includes it. It is the single largest un-mutated module in the trace
substrate, and it is pure parse/aggregate logic — the ideal target. S6.6 found
8 deletable guards in `session/manager.py` the first time that scope was
extended; the same argument applies here.

**F1 — `test_unparsed_kinds_complete` hardcodes the parsed set. (P3, downgraded
after probing.)** The test lists 23 kind literals by hand rather than deriving
them from `stats.py`.

> **Correction — I tested my own claim and it was overstated.** I removed the
> real `model_msg` parser branch and re-ran: `test_unparsed_kinds_complete`
> stayed green exactly as predicted, but `test_model_user_msg_counted`
> **failed**, so the deletion *was* caught. Following up, **23 of 23** parsed
> kinds appear in a behavioural test. The residual risk is therefore **drift
> of a duplicated list**, not loss of a parser — a real smell, not the
> coverage hole the first draft implied. Recorded rather than quietly fixed:
> an overstated preflight finding is how a slice acquires invented scope.

**F5 — `export_run` overwrites `created_at` on re-export. (P3, latent.)**
`INSERT OR REPLACE` writes every column; probed at store level `2020` →
`2030`. **Not live**: the real path recomputes `created_at` from the first
event in the session DB, which persists — a genuine re-run preserved it. Worth
one regression test pinning the real-path behaviour, not a rewrite.

**F4 — WITHDRAWN. It was an artifact of my own broken measurement.**

The preflight claimed `stats.py` dispatches on a `compaction_stage` *prefix*
matching a kind nothing emits. **Both halves were false.** The v1 review
re-measured with `typing.get_args(LogKind)` instead of a regex and found:

- `LogKind` has **33** members, not 27. My preflight regex was `"([a-z_]+)"` —
  **no digits** — so it silently dropped all six `compaction_stage2_*` /
  `compaction_stage3_*` kinds.
- `stats.py` contains **no** `startswith` dispatch at all. The six kinds are
  matched by ordinary `kind == "compaction_stage2_done"` equality
  (`stats.py:417`, `:426`, `:434`, …). The phantom "prefix" was the truncated
  stem my regex left behind.

**Nothing to document and nothing to change.** Recorded rather than deleted
because the *method* failure matters more than the finding: a character-class
regex over source is not a measurement, and it produced a confident,
plausible, entirely fictional finding. `typing.get_args` was available the
whole time. This is the fourth instrument-error in this workstream (after
S8.6's `trace` probe) — **prefer the runtime object over a regex over source.**

---

## 0. Executive intent (§3)

**IDEA.** Prove that `fa stats` and the `global_history` projection tell the
truth about a real trace, and replace three checks that *cannot fail* with
checks that can.

**PROJECT MEANING.** `stats.py` + `global_history` are the read side of
everything S5–S8 built. S8 corrected the *value* the projection stores
(`stop_reason`); S9 verifies the *consumers* of that value and hardens the
guards that keep the projection derived rather than authoritative.

**GOALS**

- **G1** — `--since` rejects invalid input instead of silently returning an
  empty result. (F6)
- **G2** — the projection-only invariant is enforced across **all** `src/fa`
  modules by AST, not a 7-name list. (F2, F3)
- **G3** — the parsed-kind contract derives from source, so the test and the
  parser cannot drift. (F1)
- **G4** — `stats.py` enters mutation scope and its survivors are cleared or
  justified. (F7)
- **G5** — authority↔projection agreement is asserted by a test, not only by a
  one-off preflight probe. (parent exit criterion 1)

**NON-GOALS** — §1.

**INTENT.** Code should ensure that *a derived read never silently
misreports*: bad input is rejected loudly, and the projection can never become
an input to hot-path correctness.

**MECHANISM SKETCH.** `_parse_since` validates → `_cmd_stats` reports a coded
error → AST guard asserts only allowlisted modules import `global_history` →
parsed-kind set derived from `stats.py` → mutation scope extended.

**PROOF SKETCH.** Roots `_cmd_stats` and `parse_session_db` observe exit codes
and DB/row fields; kill-checks remove the validation, the guard, and the
derivation.

**SIZE.** S/M.

---

## 1. Non-goals & minimal-mechanism check (§5)

1. **No typed event-union migration** (parent §Do-not). `dict.get()` stays.
2. **No change to old-session compatibility.** `legacy_trace_unsupported`
   keeps its exact code and message.
3. **No `read_all` pagination / complexity work** — parent Do#6 gates it on a
   stable correctness policy; promoted to **Q38** with a default of *defer*.
4. **No rewrite of `export_run`'s `INSERT OR REPLACE`** (F5) — pin the real
   behaviour with a test instead.
5. **No change to the `compaction_stage` prefix match** (F4) — document only.
6. **No exit-code semantics change** — that is Q35b, and it belongs to whoever
   owns the CLI contract next (§7).
7. **I-36 / I-37 / I-39 untouched** — operator-deferred.

**Minimal-mechanism check (P1 — brief):** G1 could be "document the footgun"
instead of validating; rejected, because the failure mode is a *wrong answer
that looks like a legitimate empty result*. G2 could keep a denylist and just
add names; rejected, because that is the same unbounded-maintenance shape that
already left 132 modules unguarded.

---

## 2. Current state → Target state (§4)

**AS-IS** — see §5 of the preflight log. Summary: Do#1/2/3/5 are L3; Do#4 is
L2; `--since` is unvalidated; `stats.py` is un-mutated.

**TO-BE** (machine-checkable)

- `_parse_since` returns `None` for a **negative or non-finite** duration;
  `_cmd_stats` treats `None`-from-a-provided-`--since` as a **usage error**
  (exit 2 with a coded message), not as "no filter".
- `test_global_history_is_projection_only` becomes an **AST allowlist** scan
  over `src/fa/**/*.py`.
- `test_stats_global_history_projection_only` (the tautology) is **deleted**;
  its intent is served by the strengthened check.
- `test_unparsed_kinds_complete` derives its parsed set from `stats.py`.
- `pyproject.toml` mutation scope includes `src/fa/stats.py`.
- Target liveness: G1 L0→L3, G2 L2→L3, G3 L2→L3, G4 L0→L3, G5 L2→L3.

**STATE transitions**

- `STATE: fa stats --since <bad>` — AS-IS: exit 1 "no matching sessions" →
  TO-BE: exit 2 `invalid_since`.
- `STATE: a new module importing global_history` — AS-IS: silently allowed →
  TO-BE: CI fails.

---

## 3. Contracts (§6)

### CT1 — `_parse_since` (function contract, §6.1)

- **PRE:** `value` is the raw `--since` string.
- **POST:** returns a **strictly positive finite** float of seconds, or `None`
  when the input is not a valid duration.
- **IN:** `str`. **OUT:** `float | None`. **ERRORS:** none — never raises.
- **PURE?** yes. **SIDE EFFECTS:** none.
- Accepts `d`/`h`/`m` suffixes, case-insensitive, surrounding whitespace
  tolerated. Rejects: no suffix, unknown suffix, empty, non-numeric,
  **negative**, **zero**, `inf`/`nan`.
- **Zero note:** `0d` currently returns `0.0`, which selects nothing but is not
  *wrong* the way a negative is. Treated as invalid for consistency — a
  zero-width window is never what an operator meant. Recorded as a decision,
  not an accident.

### CT2 — invalid `--since` is a usage error (signal contract, §6.2)

- **PRODUCER:** `_cmd_stats` (`cli.py:2730`) and the `--global-history` branch
  (`cli.py:2690`) — **both** call sites, per path-sensitivity.
- **CONSUMER:** the operator / any script reading the exit code.
- **Contract:** `--since` provided **and** unparseable ⇒ print
  `fa stats: invalid --since value …` to **stderr** and return **2**. Exit 2 is
  the code `_cmd_stats` already uses for source errors
  (`StatsSourceError` → 2), so this is consistent, not novel.
- **KILL-CHECK:** remove the validation → `test_s9_since_rejects_negative`
  fails (exit becomes 1 with "no matching sessions").

### CT3 — projection-only invariant (invariant, §6.4)

- **CT3:** No module under `src/fa` other than the allowlist may **import**
  `global_history`. Enforced by an **AST** scan over `src/fa/**/*.py`;
  verified by `test_s9_projection_only_is_ast_enforced`.
- **Assertion shape: SUBSET, not equality.** `importers ⊆ {cli.py, stats.py}`.
  > **v1-review correction.** The first draft mandated
  > `importers == {cli.py, stats.py, global_history.py}` — which **fails on
  > day one**, measured. Two reasons: `stats.py` does not reference
  > `global_history` at all (grep count: 0 — the *CLI* is the consumer, not
  > the stats module), and `global_history.py` cannot import itself. An
  > equality assertion here would have sent the executor debugging a
  > correct codebase against a wrong plan.
- **Liveness control (mandatory):** assert the scan saw **> 100 modules** and
  that `cli.py` **is** in the importer set. A subset assertion is trivially
  satisfied by an empty set, so without these two controls the test passes if
  the glob silently matches nothing or the AST walk is broken. *(S7.C4's
  positive-control lesson, applied to a static check.)*
- **Why AST:** a string scan false-positives on `output.py`'s docstring
  (measured). A guard that reports a file which does not import the module
  would be trained-to-ignore within one sprint.
- **KILL-CHECK:** add `from fa.inner_loop.global_history import …` to
  `state.py` in a scratch edit → the test fails.

### CT4 — parsed-kind completeness (data contract, §6.3)

- Every `LogKind` is either dispatched by `_parse_events` **or** listed in
  `UNPARSED_KINDS`; the *dispatched* set is **derived from `stats.py`**, never
  restated.
- **KILL-CHECK:** delete a dispatch branch → the derived set shrinks and the
  completeness assertion fails (today it would not).

### CT5 — authority ↔ projection agreement (data contract, §6.3)

- For one run, `stats.parse_session_db(...).total_in / .total_out / .turns`
  equal the `global_history.runs` row's `input_tokens` / `output_tokens` /
  `turns`.
- **KILL-CHECK:** remove `export_session_to_global_history` → no row, test
  fails on its existence pre-check.

**Security contract (§6.5):** N/A — S9 adds no boundary. `--since` validation
is input hygiene, not a trust boundary; noted rather than dressed up as one.

---

## 4. Path & flag matrix (§7)

### 7.1 Path inventory

| P# | Trigger | Site | Covering S# |
|---|---|---|---|
| P1 | `fa stats` default (session analytics) | `cli.py:2730+` | S9.5 (CT5) |
| P2 | `fa stats --global-history` | `cli.py:2668` | S9.2 (CT2 second call site) |
| P3 | `--since` valid | both call sites | S9.2 |
| P4 | `--since` invalid (negative / junk) | both call sites | **S9.2** |
| P5 | `--run-id` set (suppresses `--since`) | `cli.py:2730` | S9.2 (asserted as unchanged) |
| P6 | legacy tree present, no sessions | `cli.py:2612` | **covered L3** — `test_cli.py:1066` (exit 2) |
| P7 | no sessions at all | `cli.py:2746` | **covered L3** |
| P8 | hot-path module imports projection | any `src/fa` module | S9.3 (CT3) |
| P9 | new `LogKind` with no parser | `stats.py` | **covered L3**, strengthened by S9.4 |
| P10 | parser branch deleted | `stats.py` | **S9.4** (uncovered today) |

**Coverage gate:** P6/P7/P9 already L3 and explicitly **not** re-tested.
P1–P5, P8, P10 each have a covering step.

### 7.2 Flag matrix

| ID | Flags | Proves | Covering S# |
|---|---|---|---|
| A | defaults | operator-facing default path | S9.5 |
| B | `--global-history` | the derived-read branch | S9.2 |
| C | `--since` valid / invalid × both branches | input hygiene on every path | S9.2 |
| D | `--run-id` + `--since` together | precedence unchanged | S9.2 |
| P-x | provider family | **N/A** — stats is provider-agnostic; it reads persisted rows | N/A |

---

## 5. Step-by-step implementation (§8)

> **Per-step protocol (operator-mandated).** Before editing: state
> source-verified behavior, contract + gap IDs, exact files allowed to change,
> stop on unresolved blockers. For each edit: idea / intent / current→target /
> mechanism / best practice / failure behavior / DoD + negative proof / test
> class / kill-check target. After each edit: targeted tests, static checks on
> changed files, `git diff` inspection, **report actual output**, never mark
> complete from "no exception". After the big chunk: targeted mutation testing.

### Step S9.0 — Re-verify preflight anchors (staleness rule)

Traces-to: all. Depends-on: none. **Files allowed to change: none.**

Do:

1. Re-resolve by **symbol**, not line number: `_cmd_stats`,
   `_discover_stats_sources`, `_parse_since`, `parse_session_db`,
   `UNPARSED_KINDS`. (S8 taught this — my own edits shifted `cli.py` lines
   mid-slice and the plan's numbers went stale.)
2. Re-run the AST importer scan; confirm **only `cli.py`**.
3. Re-run the `_parse_since` behaviour table; confirm `-5d` is still negative.

Exit criteria:

- [ ] all five symbols resolve
- [ ] AST scan reproduces `cli.py`-only
- [ ] `-5d` still returns a negative (else F6 was fixed elsewhere — amend plan)

---

### Step S9.1 — Pin authority↔projection agreement (CT5, G5)

Traces-to: G5, CT5. Depends-on: S9.0. Parallelizable-with: S9.3, S9.4.

**Current source-verified behavior.** Agreement holds — measured in preflight
(`turns/in/out = 1/1/1`). **No test asserts it**; the parent's first exit
criterion rests on a one-off probe.

**Files allowed to change:** `tests/test_s9_stats_projection.py` (NEW).
**No production change.**

Do:

1. Drive the real `_cmd_run` with `_run_args` (**not** `_make_run_args` — see
   §3 fixture honesty), producing a genuine session + `global_history` row.
2. Assert `parse_session_db(...).total_in == row["input_tokens"]`, same for
   `total_out` and `turns`.
3. Include an existence pre-check on the row so a missing export fails loudly
   rather than comparing two absent values.

Do-not: do not assert on rendered text; §9's ranking puts prose last.

**Test class: C2.** **Oracle:** DB row fields vs parsed analytics.
**Kill-check target:** remove `export_session_to_global_history` (`cli.py:2281`)
→ existence pre-check fails.

**Negative proof:** comparing two zeroes would pass vacuously — assert the
values are **non-zero** as a liveness witness before comparing them.

---

### Step S9.2 — Reject invalid `--since` (F6, G1, CT1+CT2)

Traces-to: G1, CT1, CT2. Depends-on: S9.0.

**Current source-verified behavior.** `_parse_since` (`cli.py:2797`) returns
`float(value[:-1]) * unit` with no sign check, so `-5d` → `-432000.0`. Both
call sites do `cutoff = time.time() - since_seconds`, pushing the cutoff into
the future and excluding everything; the operator sees "no matching sessions"
(exit 1). Measured.

**Files allowed to change:** `src/fa/cli.py`,
`tests/test_s9_stats_projection.py`.

**Prerequisite:** add the `_stats_args(**overrides)` helper described in
§Preflight 3 (all seven attributes, sane defaults) before writing the C2
tests. Every S9 C2 test uses it; none hand-rolls a Namespace.

Edit:

- path: `src/fa/cli.py` · symbol: `_parse_since` · change: reject
  non-positive and non-finite results; return `None`.
- path: `src/fa/cli.py` · symbol: `_cmd_stats` · change: **one** guard placed
  immediately after the local imports and **before** the
  `if getattr(args, "global_history", False):` dispatch — if `args.since` was
  provided and parsing returned `None`, print a coded error to stderr and
  `return 2`.

  > **v1-review correction.** The first draft said "at both call sites". That
  > is worse in two ways. (a) The `--global-history` since-filter lives
  > *inside* a broad `try:` whose `except Exception` returns **1**; a `return`
  > is not swallowed by an `except` (verified), so it would have worked — but
  > it puts a usage check inside an error-recovery block, where a later edit
  > could easily convert it into a caught exception. (b) Two guards is two
  > places to drift. A single pre-dispatch guard covers **both** paths (P2 and
  > P4) with one edit and rejects bad input *before* any DB work.

Do:

1. Add `math.isfinite(seconds) and seconds > 0` as the acceptance condition.
2. Distinguish *not provided* from *provided-but-invalid* — only the latter is
   an error. `--run-id` continues to suppress `--since` (P5) unchanged, so the
   guard must reproduce that precedence: validate only when `--since` is set
   **and** `--run-id` is not.
3. Use the existing message shape: `fa stats: invalid --since value {v!r} …`.
4. Read the flag with **`getattr(args, "since", None)`**, not `args.since`.
   The two existing call sites disagree — `cli.py:2689` uses `getattr`,
   `cli.py:2730` uses a bare attribute — and the new guard runs *before* both,
   so it must tolerate the loosest Namespace any caller builds. Every current
   test Namespace happens to set `since`, so a bare attribute would work
   today; that is latent coupling, not safety.

Do-not:

- Do not raise; `_parse_since` stays total (CT1: never raises).
- Do not change `--run-id` precedence.
- Do not "fix" scientific notation — `1e3h` is valid input, merely exotic.

**Idea now implemented:** a filter that cannot silently lie. **Intent:** an
empty result must mean *no data*, never *bad flag*. **Mechanism:** one guard
in a pure function plus a usage-error branch at each call site.
**Best practice:** fail fast and loudly on operator input; reserve silent
degradation for best-effort *background* work (the projection export), never
for the operator's own query. **Failure behavior:** exit 2, stderr, no
traceback.

Exit criteria:

- [ ] `_parse_since("-5d") is None`, `("0d") is None`, `("7d") == 604800.0`
- [ ] `fa stats --since -5d` → exit **2**, stderr contains `invalid --since`
- [ ] `fa stats --global-history --since -5d` → exit **2** (second call site)
- [ ] `fa stats --since 7d` unchanged; `--run-id` + `--since` unchanged
- [ ] `mypy` + `ruff` + `pylint src/fa` clean

**Test class: C0p** for the parser (many inputs — the twelve-case table),
**C2** for both CLI call sites. Per skill §10 the C0p is **paired** with the
C2s, never standalone.
**Oracle:** return value; exit code + stderr substring.
**Kill-check target:** remove the `> 0` guard → `test_s9_since_rejects_negative`
fails.

**Negative proof:** asserting only "exit != 0" is weak — exit 1 already
happens today for the wrong reason. Assert **exactly 2** and the coded
message, so the test distinguishes *rejected* from *found nothing*.

---

### Step S9.3 — AST-enforced projection-only guard (F2 + F3, G2, CT3)

Traces-to: G2, CT3. Depends-on: S9.0. Parallelizable-with: S9.1, S9.4.

**Current source-verified behavior.**
`test_global_history_is_projection_only` (`test_global_history_export.py:345`)
checks 7 hardcoded paths; `src/fa` has **139** modules. Separately
`test_stats_global_history_projection_only`
(`test_stats_global_wiring.py:92`) asserts `"global_history" in cli.py` — a
presence check that passes for 17 unrelated reasons and cannot detect a
hot-path import.

**Files allowed to change:** `tests/test_global_history_export.py`,
`tests/test_stats_global_wiring.py`.
**No production change.**

Do:

1. Rewrite the guard as an **AST** scan over `src/fa/**/*.py`, collecting
   `ast.Import` / `ast.ImportFrom` nodes whose module mentions
   `global_history`.
2. Assert `importers <= {"cli.py", "stats.py"}` (**subset** — see CT3's
   correction; equality fails today because only `cli.py` imports it), plus
   the two liveness controls: module count `> 100` and `"cli.py" in importers`.
3. **Delete** `test_stats_global_history_projection_only`, recording why in
   the commit: it cannot fail, and the strengthened check subsumes its intent.

Do-not:

- Do **not** use a string scan — `output.py` mentions `global_history` in a
  docstring (my S8.4 text) and would false-positive. Measured.
- Do not add the allowlist to production code; this is a test-side invariant.

**Idea now implemented:** an unbounded guard replaces an enumerated one.
**Intent:** the invariant must hold for modules that do not exist yet.
**Mechanism:** `ast.walk` over `rglob("*.py")`, mirroring
`check_log_kind_contract.py:172`. **Best practice:** allowlist over denylist
for closed invariants — a denylist silently exempts everything nobody thought
of. **Failure behavior:** test failure naming the offending file:line.

Exit criteria:

- [ ] scan covers **139** modules (assert `> 100`, so the test fails if the
      glob silently matches nothing)
- [ ] `"cli.py" in importers` — proves the scan detects a real import
- [ ] `output.py` is **not** reported (AST, not string) — measured: a string
      scan reports it, an AST scan does not
- [ ] adding an import to `state.py` in a scratch edit fails the test
- [ ] the tautological test is gone

**Test class: C1** (source-topology invariant).
**Oracle:** the AST importer set.
**Kill-check target:** insert `from fa.inner_loop.global_history import
GlobalHistoryStore` into `state.py` → the test must fail. **Execute this**, do
not assume it.

**Negative proof:** a scan that silently matched zero files would pass. The
`> 100` module-count assertion is the liveness witness — the same
positive-control pattern S7.C4 needed.

---

### Step S9.4 — Derive the parsed-kind set from source (F1, G3, CT4)

Traces-to: G3, CT4. Depends-on: S9.0. Parallelizable-with: S9.1, S9.3.

**Current source-verified behavior.** `test_unparsed_kinds_complete`
(`test_s19_stats_parsers.py:152`) restates 23 kind literals. Measured: it
matches source exactly today, and removing a real parser branch does **not**
fail it (verified by deleting `model_msg` — a *different* test caught that).

**Files allowed to change:** `src/fa/stats.py`,
`tests/test_s19_stats_parsers.py`.

Edit:

- path: `src/fa/stats.py` · symbol: `PARSED_KINDS` (**NEW** module-level
  `frozenset`) · change: single source of truth for dispatched kinds, added to
  `__all__`.
- path: `tests/test_s19_stats_parsers.py` · symbol:
  `test_unparsed_kinds_complete` · change: use `PARSED_KINDS` instead of a
  literal set.

Do:

1. Define `PARSED_KINDS` next to `UNPARSED_KINDS` so the two are read
   together, and reference it in the completeness test.
2. Add `test_s9_parsed_kinds_matches_dispatch`: parse `stats.py` with `ast`
   and assert `PARSED_KINDS` equals the kinds actually compared in
   `_parse_events`. **This is the test that makes deletion detectable.**
3. Derive with `typing.get_args(LogKind)` and an AST walk of `_parse_events`
   — **never a regex over source**. The v1 review's F4 withdrawal is the
   reason: a `[a-z_]+` character class silently dropped six digit-bearing
   kinds and manufactured a fictional finding. The derivation must see all
   **33** LogKinds and all **23** dispatched kinds.

Do-not:

- Do not make the dispatch itself data-driven — that is a refactor of a
  887-line parser and is not in the intent (parent §Do-not: no union
  migration; minimal mechanism).
- Do not delete the behavioural per-kind tests; they are the reason F1 is P3.

**Idea now implemented:** one fact, one place. **Intent:** the contract test
must fail when the parser changes, in *both* directions.
**Mechanism:** module-level frozenset + an AST cross-check.
**Best practice:** a test that restates a fact duplicates it; derive it.
**Failure behavior:** test failure naming the drifted kinds.

Exit criteria:

- [ ] `PARSED_KINDS` in `__all__`; `authoring-check` 0 diagnostics
- [ ] `PARSED_KINDS | UNPARSED_KINDS == set(get_args(LogKind))` — currently
      **23 + 10 = 33**, verified by runtime introspection during the review
- [ ] deleting a dispatch branch fails `test_s9_parsed_kinds_matches_dispatch`
- [ ] no literal kind list remains in `test_unparsed_kinds_complete`

**Test class: C1.** **Oracle:** set equality against an AST-derived set.
**Kill-check target:** remove an `elif kind == "…"` branch → the new test
fails. **Execute it.**

**Negative proof:** if the AST derivation returned an empty set, equality
against an empty `PARSED_KINDS` would pass — assert `len(PARSED_KINDS) == 23`
and `len(get_args(LogKind)) == 33`. Exact counts, not `>= 20`: the review
proved a loose bound is exactly how the six digit-bearing kinds went unnoticed.

---

### Step S9.5 — Pin the F5 real-path invariant (documentation + regression)

Traces-to: CT5. Depends-on: S9.1.

**Current source-verified behavior.** `export_run`'s `INSERT OR REPLACE`
rewrites `created_at` (probed `2020`→`2030`), but the production path
recomputes it from the first event, so a genuine re-run preserved
`2026-07-31T04:56:14Z`. Latent, not live.

**Files allowed to change:** `src/fa/inner_loop/global_history.py` (docstring
only), `tests/test_s9_stats_projection.py`.

Do:

1. Add one test: run the same `run_id` twice through `_cmd_run`; assert
   `created_at` is preserved and `turns` increases.
2. Add a docstring note on `export_run` stating the invariant and *why* it
   holds (derived from the first persisted event), so a future caller passing
   `created_at` from elsewhere knows what they would break.

Do-not: do not change `INSERT OR REPLACE`; idempotence via `run_id` PK is a
tested, deliberate property (`test_global_history_export_idempotent`).

**Test class: C2.** **Oracle:** the row's `created_at` across two runs.
**Kill-check target:** make `build_export_row` stamp `_now_iso_z()`
unconditionally → the test fails.

---

### Step S9.6 — Mutation scope + targeted sweep (F7, G4)

Traces-to: G4. Depends-on: S9.1–S9.5.

Do:

1. Add `src/fa/stats.py` to **both** `[tool.mutmut] source_paths` and
   `[tool.pytest-gremlins] paths`.
2. Run gremlins over `stats.py` with the stats test suites.
3. Write `scripts/sweep_specs/s9_stats_projections.json` — statement-deletion
   mutations for the guards S9 adds (`> 0` check, the exit-2 branches, the AST
   allowlist). gremlins has **no statement-deletion operator**, so the two
   tools are complementary, not redundant.
4. **Confirm the `N passed` line** before believing any kill percentage — a
   collection failure still prints 100%.

Exit criteria:

- [ ] both tool scopes updated
- [ ] gremlins: 0 survivors on `stats.py`, `N passed` confirmed, or each
      survivor justified in writing
- [ ] sweep: every mutation caught, or justified

---

## 6. Verification plan (§9)

New tests land in **`tests/test_s9_stats_projection.py`** unless stated.

| CT# | Test | Class | Oracle | Kill-check target | Paths |
|---|---|---|---|---|---|
| CT5 | `test_s9_authority_and_projection_agree` | C2 | analytics vs row fields | `export_session_to_global_history` | P1 |
| CT1 | `test_s9_parse_since_table` | C0p | return value over 12 inputs | the `> 0` guard | P3, P4 |
| CT2 | `test_s9_since_rejects_negative` | C2 | exit **2** + coded stderr | validation branch in `_cmd_stats` | P4 |
| CT2 | `test_s9_global_history_since_rejects_negative` | C2 | exit **2** | second call site | P2, P4 |
| CT2 | `test_s9_valid_since_still_filters` | C2 | exit 0, sessions returned | same | P3 |
| CT2 | `test_s9_run_id_precedence_unchanged` | C2 | `--since` ignored with `--run-id` | same | P5 |
| CT3 | `test_s9_projection_only_is_ast_enforced` *(in `test_global_history_export.py`)* | C1 | AST importer set == allowlist | any hot-path import | P8 |
| CT4 | `test_s9_parsed_kinds_matches_dispatch` *(in `test_s19_stats_parsers.py`)* | C1 | AST-derived set == `PARSED_KINDS` | an `elif` dispatch branch | P10 |
| CT5 | `test_s9_created_at_preserved_across_reexport` | C2 | row `created_at` across two runs | `build_export_row` timestamp | P1 |

**LIVE-PATH PROOF**

```text
root:        _cmd_stats (src/fa/cli.py) + _cmd_run for trace creation
matrix:      A (defaults) + B (--global-history) + C (--since valid/invalid)
test:        tests/test_s9_stats_projection.py::test_s9_authority_and_projection_agree
oracle:      global_history row fields vs parse_session_db analytics
kill-check:  removing the export call fails it
producer:    cli.py export_session_to_global_history
consumer:    fa.stats.parse_session_db / GlobalHistoryStore.read_all
paths-covered: 7/10 by new tests; 3/10 (P6, P7, P9) already L3
contract-check: PASS required (`just check`)
pyramid:     A
```

**CI authority:** `just check` — `lock-check`, `dependency-contract-check`,
`lint` (ruff + deptry + `pylint src/fa`), `typecheck` (bare `python -m mypy`),
`authoring-check`, `contract-check`, `log-kind-check`, `no-mocked-dataclasses`,
`test` (`pytest --cov`, `fail_under = 80`). **Not** the Makefile.

---

## 7. Risks, rollback, open questions (§10)

### Risks

| RK# | Risk | Mitigation | Detected by |
|---|---|---|---|
| RK1 | Rejecting `0d` breaks a script that passes it today | `0d` selects nothing now, so no working script depends on it; called out in the PR note | C2 test + review |
| RK2 | AST guard false-negatives on a dynamic import (`importlib`) | Documented limit: the guard covers static imports, which is how every current importer works | Comment in the test |
| RK3 | `PARSED_KINDS` drifts from the dispatch it documents | That is exactly what `test_s9_parsed_kinds_matches_dispatch` asserts | C1 test |
| RK4 | Adding `stats.py` to mutation scope lengthens CI | Sweep is targeted and run on demand, not in `just check` | Sweep runtime |
| RK5 | Exit-code change (1 → 2) surprises a caller | Only for input that was **already** producing a wrong answer; PR note calls it out | Review |

### Rollback

All changes are additive or test-side except the `_parse_since` guard and two
usage-error branches; `git revert` of the S9.2 commit restores prior behaviour
exactly. No data migration — no schema touched.

### Open questions

**Q35b — carried from S8. NON-BLOCKING, default recorded.**
Should a `BLOCKED` workflow verdict exit non-zero? S8 deferred it here because
`stop_reason` is now honest, leaving the exit code as the last inconsistent
signal. **Default for S9: no change.** S9's scope is the *read* side; changing
`fa workflow`'s exit code is a write-side CLI contract change and belongs with
S10/S11 or an explicit operator decision. Flag in handoff so it is not lost a
second time.

**Q37 — `fa stats --global-history` stream discipline. NON-BLOCKING, resolved
as verified.** It prints JSON to stdout and console rendering to stderr, which
already matches S8.4's contract. **Default: no change**; record as verified.

**Q39 — should an invalid `--since` error even when `--run-id` overrides it?
NON-BLOCKING, default recorded. (Raised by the v1 review.)**

Both call sites guard on `args.since and not args.run_id`, so
`fa stats --run-id X --since -5d` parses nothing, reports nothing, and returns
run X. The typo is silently ignored.

That is arguably the *same class* of defect as F6 — a flag the operator typed
having no effect and no diagnostic. But erroring on it is a broader behaviour
change than F6 (it would reject command lines that "work" today), and
`--run-id` overriding `--since` is documented precedence, not a bug.

**Default for S9: preserve today's precedence — validate only when `--since`
is actually consulted.** `test_s9_run_id_precedence_unchanged` pins it, so the
behaviour is deliberate and visible rather than incidental. Revisit only if an
operator reports confusion. Recorded because the v1 draft decided this
silently by writing the guard condition, which is exactly the kind of quiet
policy choice the stop rule exists to catch.

**Q38 — `read_all` complexity (parent Do#6). NON-BLOCKING, default: defer.**
`read_all` is an unpaginated `SELECT *`. The parent gates this on "correctness
policy stable", which S9 establishes. **Default: measure in S11** rather than
optimise now — there is no evidence of a large table yet, and premature
pagination would change the `fa stats` output contract.

---

## 8. Research-note disposition (§11a)

| RN# | Item | Verdict | Why | Anchor |
|---|---|---|---|---|
| RN1 | Parent Do#1 (discovery authority) | **Reject — already L3** | `_discover_stats_sources` validates identity, path, status, binding; legacy explicitly coded | §Preflight 5 |
| RN2 | Parent Do#2 (malformed/partial) | **Reject — already L3** | nonexistent + corrupt + DB-only covered | §Preflight 5 |
| RN3 | Parent Do#3 (kinds explicit) | **Accept in part** | registry is L3; the *test* restates it → G3 | S9.4 |
| RN4 | Parent Do#4 (derived not hot-path) | **Accept** | holds today, guard is enumerated → G2 | S9.3 |
| RN5 | Parent Do#5 (aggregate measured) | **Reject — closed by S8** | `duration_ms` S8.2, `stop_reason` S8.7 | §Preflight 5 |
| RN6 | Parent Do#6 (read-all complexity) | **Defer** | parent gates it on stable correctness policy | Q38 |
| RN7 | *(preflight)* `--since` negative | **Accept** | only production defect found | S9.2 / F6 |
| RN8 | *(preflight)* tautological wiring test | **Accept — delete** | cannot fail; 17 incidental matches | S9.3 / F3 |
| RN9 | *(preflight)* `stats.py` un-mutated | **Accept** | 887 lines, largest un-mutated substrate module | S9.6 / F7 |
| RN10 | *(preflight)* F1 severity | **Rewrite — downgraded to P3** | probed: parser deletion **is** caught by a behavioural test; 23/23 covered | S9.4 |
| RN11 | *(preflight)* F5 `created_at` | **Rewrite — pin, don't fix** | latent only; real path recomputes from first event | S9.5 |
| RN12 | *(preflight)* F4 prefix match | **Defer — document** | branch is reachable and correct | S9.4 note |

---

## 9. Definition of Done (§11.3)

**STATE — before → after, and how to observe**

| | Before | After | Observed by |
|---|---|---|---|
| `--since -5d` | exit 1, "no matching sessions" | exit **2**, `invalid --since` | C2 tests |
| projection-only guard | 7 hardcoded files (132 unguarded) | AST allowlist over all 139 | C1 test |
| wiring tautology | present | deleted | grep |
| parsed-kind contract | 23 literals restated | derived from `stats.py` | C1 test |
| `stats.py` mutation | out of scope | in both tools, survivors cleared | S9.6 output |
| authority ↔ projection | probe only | asserted | C2 test |

**ARTIFACTS**

- Created: `tests/test_s9_stats_projection.py`,
  `scripts/sweep_specs/s9_stats_projections.json`.
- Modified: `src/fa/cli.py`, `src/fa/stats.py`,
  `src/fa/inner_loop/global_history.py` (docstring),
  `tests/test_global_history_export.py`, `tests/test_stats_global_wiring.py`,
  `tests/test_s19_stats_parsers.py`, `pyproject.toml`, this plan,
  `worklogs/HANDOFF.md`.
- **No other file may change.**

**CONTRACTS:** CT1–CT5 each PLANNED → IMPLEMENTED → **VERIFIED**.

**S9 is DONE only when:**

- [ ] G1–G5 reach **L3**, each with an executed producer kill-check.
- [ ] **Every test written under the tests-writing skill** — class in the
      docstring, ranked oracle, kill-check target named, honest fixtures
      (`_run_args`, not `_make_run_args`), no `TEST-EDITS` weakening, no
      unpaired C0/C0p.
- [ ] `just check` green — bare `python -m mypy`, `pylint src/fa` 10.00/10,
      coverage ≥ 80.
- [ ] `fa authoring-check` 0 diagnostics (new `PARSED_KINDS` export).
- [ ] **Zero new `noqa`.**
- [ ] Mutation: `stats.py` survivors cleared or justified in writing; sweep
      mutations all caught; **`N passed` confirmed** on every run.
- [ ] Non-goals respected — no union migration, no compatibility change, no
      `read_all` rework, no I-36/37/39 work.
- [ ] **Every mechanism in this plan was proven executable during review, not
      assumed**: the S9.4 AST derivation was run (23 dispatched + 10 unparsed
      = 33 LogKinds, exact); the S9.3 importer scan was run (139 modules,
      `{cli.py}`); the S9.1 fixture chain was run end-to-end (`_run_args` →
      `_cmd_run` → manifest → analytics == row, all non-zero); exit code 2 was
      confirmed as argparse's own usage-error convention. An executor hitting
      a surprise here should suspect drift since `cd34e98`, not a wrong plan.
- [ ] All RN# dispositioned; Q35b/Q37/Q38/**Q39** defaults recorded in the handoff.

**Negative proof (plan-level).** This plan is invalid if any G# is marked done
on "the suite is green" without the corresponding deletion having been *run
and observed to fail*. Four checks in this workstream have already been caught
passing vacuously — S7.C3's contradictory predicate, S7.C4's control-free
absence, S7.C7's silent `find`, and S9's own F3 tautology. Assume the same
failure mode is present here until each kill-check is executed.

---

## 10. Anti-theater + READY gate (§11.2, §11.4)

### 11.2 Anti-theater checklist

- [x] Every referenced symbol verified in preflight (file:line) or marked NEW
- [x] Every G# maps to ≥1 CT#, ≥1 S#, ≥1 verification — G1→CT1/CT2/S9.2,
      G2→CT3/S9.3, G3→CT4/S9.4, G4→S9.6, G5→CT5/S9.1
- [x] Every signal CT# has producer and consumer (CT2's consumer is the exit
      code; CT3's is CI)
- [x] Every kill-check targets the PRODUCER
- [x] Path inventory has no uncovered path without an explicit non-goal
      (P6/P7/P9 waived with reason)
- [x] Matrix rows each have a covering step or "N/A — why"
- [x] Dual-write: N/A stated (single derived channel)
- [x] Fixtures honest — `_run_args` mandated over `_make_run_args`, with the
      measured reason
- [x] No vague verbs without a mechanism
- [x] Assumptions labelled (F5 "latent not live"; RK2 dynamic-import limit)
- [x] Security: N/A declared with reason
- [x] All IDs resolve — G1–G5, CT1–CT5, S9.0–S9.6, P1–P10, Q35b/Q37/Q38,
      RN1–RN12, RK1–RK5, F1–F7 (F4 withdrawn, retained as a numbered record)

### 11.4 READY gate

- [x] Preflight log present and non-trivial (probes, not "skipped")
- [x] Depth P1 declared and matches scope
- [x] Intent, non-goals, current/target state concrete
- [x] Contract subtypes present or explicitly N/A
- [x] Path + matrix gates satisfied
- [x] Every step file:symbol specific with exit criteria
- [x] Verification plan + LIVE-PATH PROOF present
- [x] Anti-theater checklist holds
- [x] Research notes dispositioned (RN1–RN12)
- [x] **BLOCKING open-question set is EMPTY** — Q36 resolved (option c);
      Q35b/Q37/Q38/Q39 non-blocking with defaults
- [x] All IDs resolve

**→ Status: READY.** Suggested order: **S9.0** → {**S9.1**, **S9.3**, **S9.4**
in parallel — disjoint files} → **S9.2** (only production behaviour change) →
**S9.5** → **S9.6** (mutation, last).


---

## 11. Execution record — 2026-07-31

| Step | Verdict | Evidence |
|---|---|---|
| S9.0 | PASS | 5 symbols re-resolved; AST scan reproduced `{cli.py}` / 139 modules; `-5d` still negative |
| S9.1 | PASS | authority↔projection agreement now asserted (`turns/in/out` equal, all non-zero) |
| S9.2 | PASS | **F6 fixed** — `-5d`/`0d` → `None`; one pre-dispatch guard; exit 2 on both branches |
| S9.3 | PASS | AST allowlist over 139 modules + 2 liveness controls; tautology deleted |
| S9.4 | PASS | `PARSED_KINDS` (23) + AST cross-check; 23+10=33 exact |
| S9.5 | **REPLACED** | the plan's premise was wrong — see below |
| S9.6 | PASS | gremlins 164/164 (`41 passed`); sweep 4/6 → **2 survivors found** → closed → 6/6 |

**Kill-checks — all executed and observed to bite:**

| Kill-check | Effect |
|---|---|
| Remove `_cmd_run` export | both S9.1 tests fail |
| Remove `_parse_since` sign guard | 4 tests fail (2 table rows + 2 CLI) |
| Remove the pre-dispatch guard | 2 CLI tests fail |
| Import `global_history` into `state.py` | guard fails, naming `['state.py']` |
| Delete a `_parse_events` dispatch branch | new AST test fails with a precise drift diff |
| Sweep S9-M1…M6 | 6/6 caught after the fix |

### S9.5 — the plan was wrong, and the test was replaced

S9.5 assumed a `run_id` could be re-run, and asked us to pin that `created_at`
survives `INSERT OR REPLACE`. **Measured: the second invocation is refused.**

```text
fresh run_id, no session   -> exit 0
same run_id, attached      -> exit 2  run_id_reused  (manager.py:394)
new run_id, attached       -> exit 0
```

So `export_run` is called **at most once per `run_id`** through the CLI, and
`created_at` cannot be clobbered because the second export never happens. **F5
is unreachable, not latent** — the earlier "latent" probe called
`GlobalHistoryStore.export_run` directly, bypassing the session manager that
makes it impossible. The test now pins the *guard*, which is the real
invariant. A test written to the plan's letter would have asserted a scenario
production forbids.

### S9.6 — mutation found what reading missed

The sweep produced **two survivors**: deleting the `manifest_path_mismatch`
and inactive-manifest guards inside `_discover_stats_sources` left all 2270
tests green.

The preflight had rated parent **Do#1 as L3 by reading those guards**. They
exist and are correct — but `_discover_stats_sources` carries its **own
copies**, independent of `SessionManager`'s (`manager.py:144-164`), and stats
never constructs a manager, so `test_session_manifest_guards.py` cannot reach
them. **"The guard is present" is not "the guard is verified."** Two
adversarial C2 tests were added and both mutations re-run: now caught.

This is the second time in S9 that a *reading* was overturned by a
*measurement* (the first being the F4 regex fiction). Recorded for S10/S11:
rate liveness from an executed probe, not from source inspection.

### Deferred, unchanged

`Q35b` (BLOCKED verdict exit code — owed to whoever owns the CLI contract
next), `Q37` (stream discipline, verified as already correct), `Q38`
(`read_all` complexity), `Q39` (`--run-id` precedence, pinned by test).
BACKLOG `I-36`/`I-37`/`I-39` remain operator-deferred.
