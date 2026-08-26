> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN: S10b — in-module decomposition + C901 waiver retirement

Plan-ID: `PLAN-cli-trace-S10b-cli-decomposition`
Status: **COMPLETE (2026-08-01)** — all four in-module decompositions executed
(`_cmd_run` 39→<15, `_cmd_stats` 29→<15, `_discover_stats_sources` 19→<15,
`_cmd_selfcheck` 19→<15); all C901 waivers in `cli.py` retired (0 remaining);
gate green (2460 passed); see HANDOFF §S10b COMPLETE and S10b execution
record in §11.
Depth: **P2** — structural change to the CLI composition root, gated on a
behaviour-invariance proof.
Revision: **v1 (reviewed)** · Changed-since-last: split out of the former
single-slice S10 plan, then a **self-review pass** that found four defects:
**(A)** S10b.4 claimed `_discover_stats_sources` was *"already 100%-covered by
S9"* — **it is 74.7%**, and my own S10a census said 77%; the two plans
contradicted each other and this one would have refactored 12 unpinned
branches;
**(B)** the coverage metric was never named — `percent_covered` (74.7) and
`percent_statements_covered` (76.5) disagree, so "80%" was ambiguous; pinned
to `percent_covered` because the repo sets `branch = true`;
**(C)** **T3 as specified passes today, before any refactor** — ruff reports
zero C901 findings while the `noqa` suppresses them, so the obvious
implementation is the S7.C3 tautology again; T3 is now a two-part assertion;
**(D)** no artifact ledger (v2 skill requires one) and three dangling
cross-plan IDs.
Upstream context: parent
[`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md)
§Step S10. **Predecessor (hard gate):**
[`PLAN-cli-trace-S10a-cli-coverage.md`](./PLAN-cli-trace-S10a-cli-coverage.md).

> **Operator decisions (2026-07-31).** `Q40` (defined in the superseded
> single-slice S10 plan, carried into S10a §7) → **in-module decomposition**,
> no new modules. Operator Q5 (chat, not a plan ID) → target **≤15** with the
> waiver deleted, not "meaningfully lower". Coverage first: *"after that we
> may proceed with refactoring."*

---

## 0. The decision this slice records (parent's actual ask)

Parent §Step S10 is titled *"**Decide** whether CLI extraction is warranted"*.
The decision, with evidence:

| Question | Measurement | Verdict |
|---|---|---|
| Is there duplication to extract? | `pylint R0801` on `cli.py`: **zero**; across `cli.py`+`stats.py`+`cli_help.py`: **zero** | **No** |
| Is size alone a reason? | parent §Do-not: *"do not split `cli.py` because it is large alone"* | **No** |
| Is there a repeated consumer for a command registry? | none found | **No** |
| Is complexity debt real? | ruff: `_cmd_run` **39**, `_cmd_stats` **29**, `_discover_stats_sources` **19**, `_cmd_selfcheck` **19**, all vs threshold 15 | **Yes** |
| Does the ratchet document an exit path? | `pyproject.toml:140` — *"Do not raise this; **lower it as waivers retire**"* | **Yes** |

**Decision: module extraction is NOT warranted. In-module decomposition IS.**
The attached plan-authoring skill's **component gate** is dispositive — new
modules would relocate coupling, not reduce it, and no evidence shows a
`src/fa/cli/` package is needed. Revisit only if duplication appears.

---

## 1. GAP ledger

| GAP# | Verified current (ruff) | Target | Owner |
|---|---|---|---|
| **GAP1** | `_cmd_run` complexity **39**, waived `cli.py:1903` | **≤15**, waiver deleted | S10b.2 |
| **GAP2** | `_cmd_stats` **29**, waived `cli.py:2654` | **≤15**, waiver deleted | S10b.3 |
| **GAP3** | `_discover_stats_sources` **19**, waived `cli.py:2576` | **≤15**, waiver deleted | S10b.4 |
| **GAP4** | `_cmd_selfcheck` **19**, waived `cli.py:2359` | **≤15** *(only if S10a reached ≥60%; else defer with owner)* | S10b.5 |
| **GAP5** | Waiver count unmanaged; nothing fails if it grows | Ratchet gate, budget may only decrease | S10b.1 |

---

## 2. Contracts

### CT1 — behaviour invariance (the whole slice rests on this)

- **AUTHORITY:** pre-refactor behaviour, captured by S10a's suite **plus** the
  S10b parity suite, both green **before** any structural edit.
- **Contract:** exit code, stdout bytes, stderr presence, durable artifacts
  (session DB rows, `flow_state.json`, `global_history` row) and artifact paths
  are unchanged.
- **DETERMINISTIC MECHANISM:** C2 parity tests are the gate, not review.
- **KILL-CHECK:** alter an extracted helper → a named parity test fails.

### CT2 — complexity ratchet (deterministic gate)

- **Contract:** `max-complexity` may only decrease; the `noqa: C901` count
  under `src/fa` may only decrease. **All numbers are ruff's.**
- **MECHANISM:** a test asserting `count <= _C901_WAIVER_BUDGET`, the budget a
  literal edited **down** in the same commit that removes a waiver.
- **KILL-CHECK:** add a `# noqa: C901` anywhere → gate fails.

### CT3 — parser composition root

`build_parser()` stays the single composition root; the subcommand set and each
command's flags are unchanged (parent Do #3, Do #4).

---

## 3. Steps

### Step S10b.0 — Verify the S10a gate is actually met

**Files: none.** Re-run the coverage census. **If any target function is below
its S10a floor, STOP** — S10b does not start. This is the hard gate, and it is
checked by measurement rather than by assuming S10a "finished".

### Step S10b.1 — Complexity ratchet (GAP5 / CT2)

**Files:** `tests/test_s10b_complexity_ratchet.py` (NEW). No production change.

Census `noqa: C901` under `src/fa` (**19 today**); assert
`<= _C901_WAIVER_BUDGET`; assert `max-complexity <= 15` so the threshold can
never be raised to silence a failure; assert every waived function is genuinely
over threshold (a waiver on a simple function is dead weight).

**Do-not:** do not fail on the existing 19 — a gate that red-lights on day one
gets disabled. **Liveness control:** assert `count >= 15`, so a broken census
cannot pass vacuously. **Kill-check:** add a waiver → fails.

### Step S10b.2 — `_cmd_run` 39 → ≤15 (GAP1 / CT1)

**Files:** `src/fa/cli.py`, `tests/test_s10b_cli_parity.py` (NEW).

**Parity first (parent Do #5).** Write the parity suite, run it against
**unmodified** `cli.py`, and record that run. A parity suite never green
pre-change proves nothing.

> **All four cells verified reachable during the v2 review** — no cell needs
> network, a container, or a live proxy:
>
> | cell | mechanism | status |
> |---|---|---|
> | happy path | `_run_args` + `_ScriptedTransport` | proven (S7/S8 suites) |
> | quiet mode | `output_mode="quiet"` | proven (S8.4) |
> | config error | bad `--config` path → exit 2 | proven |
> | **proxy mode** | `monkeypatch.setenv("FA_EGRESS_PROXY_URL", ...)` + `FA_PROXY_TOKEN_FILE` | **executed in review: exit 0** |
>
> Proxy mode was the only cell in doubt — `_resolve_proxy_url` (`cli.py:288`)
> reads a plain env var, and the token comes from a file, so both are
> `monkeypatch`-able. A full `_cmd_run` with proxy mode on and a scripted
> transport returned **exit 0**, exercising the `_proxy_rewrite_chain` branch
> that is dark today (`cli.py:1978-1982`). This cell therefore does double
> duty: it is both a parity oracle for S10b **and** part of S10a's route to
> 80% on `_cmd_run`.

Then extract **pure, side-effect-free** helpers. Candidate seams measured in
the S10a preflight: secret-redactor construction, provider-chain assembly,
proxy rewrite, and the outcome/export epilogue (`drive_session` is called at
`cli.py:2235`; `output_bus = EventBus()` at `:2217` is the natural boundary
between setup and execution).

Re-measure with **ruff** after each extraction; stop at ≤15; delete the
`noqa`; lower the budget 19 → 18 in the same commit.

**Degree of freedom closed:** before, "refactor `_cmd_run`" could mean anything
and be justified by inspection; after, only changes keeping four parity oracles
byte-identical are admissible, and ruff's number is the completion criterion
rather than a reviewer's judgement.

**Do-not:** no new module; no flag/exit/stream/path change; do not extract
anything the parity suite does not observe.

### Step S10b.3 — `_cmd_stats` 29 → ≤15 (GAP2)

Same shape. Natural seams: the `--global-history` branch (already a
self-contained block), the `--since` filter, and console rendering.

### Step S10b.4 — `_discover_stats_sources` 19 → ≤15 (GAP3)

Smallest of the four. The manifest-validation chain extracts cleanly into a
per-manifest validator.

> **v2-review correction — my own two plans contradicted each other.** This
> step claimed `_discover_stats_sources` was *"already 100%-covered by S9"*.
> **It is 74.7%** (12 dark statements, measured). S9 added tests for exactly
> **two** of its guards (`manifest_path_mismatch`, inactive-manifest) after
> the mutation sweep found them surviving — that is not the same as covering
> the function. The remaining dark branches are `invalid_run_id`,
> `invalid_session_id`, `unknown_session`, `manifest_corrupt` (×2),
> `manifest_identity_mismatch`, the `SessionDatabaseError` re-raise, and the
> `--since` mtime filter.
>
> **Consequence:** this step depends on **S10a `GAP7`** (a cross-plan ID) lifting it to ≥80% first,
> exactly like the other three. It is **not** a shortcut. Had the claim gone
> unchecked, S10b.4 would have refactored a function with 12 unpinned
> branches while believing the parity net was complete — the precise failure
> mode the S10a/S10b split exists to prevent.

### Step S10b.5 — `_cmd_selfcheck` 19 → ≤15 (GAP4), conditional

**Only if S10a reached ≥60%** (S10a `GAP4`). Otherwise record a BACKLOG item with an owner
and leave the waiver. Refactoring under-covered code is the failure mode this
two-slice split exists to prevent.

### Step S10b.6 — Mutation (C4 handoff)

Sweep spec `scripts/sweep_specs/s10b_decomposition.json`: delete each extracted
helper's guard; every mutation must be **CAUGHT** by the parity suite. Confirm
the `N passed` line. **A survivor blocks shipped status.**

---

## 4. Verification plan

| T# | Test | Class | Oracle | Kill-check |
|---|---|---|---|---|
| T1 | `test_s10b_c901_waiver_budget` | C1 | waiver census + `max-complexity` | add a `noqa: C901` |
| T2 | `test_s10b_cmd_run_parity_*` (happy, quiet, proxy, config-error) | C2 | exit code + stdout bytes + DB/FS | change an extracted helper |
| T3 | `test_s10b_complexity_under_threshold` | C1 | **two-part**: waiver absent **and** ruff silent — see below | re-inline a helper |
| T4 | `test_s10b_cmd_stats_parity_*` | C2 | exit code + JSON keys | change a helper |

**Two independent oracles.** Re-inlining a helper must leave **T2 green** (behaviour
unchanged) while **T3 fails** (structure regressed). Behaviour and structure are
measured separately — that is what makes "no behaviour change" falsifiable.

> **T3 must be two-part, or it is a check that cannot fail — v2-review
> finding.** The obvious implementation ("assert `ruff --select C901` reports
> nothing for `cli.py`") **passes right now, before a single line is
> refactored** — measured: ruff currently emits **0** C901 findings, because
> `# noqa: C901` suppresses them. Shipping that alone would be the S7.C3
> tautology a fourth time.
>
> T3 therefore asserts **both**:
> 1. the `# noqa: C901` comment is **absent** from the target function's
>    definition line (parse the source; a `grep` on the whole file would pass
>    while another function still carries one), **and**
> 2. `ruff --select C901` reports **no finding** for that function.
>
> Part 1 alone would pass on a function whose complexity is still 39 with the
> waiver merely deleted — CI would then fail, but *after* merge-time review.
> Part 2 alone passes today. Only the conjunction proves *complexity actually
> dropped below the threshold*. **Liveness control:** the test asserts ruff
> exited 0 (it ran) and that `cli.py` was actually scanned — a typo'd path
> yields "no findings" too.

---

## 5. Risks

| RK# | Risk | Mitigation |
|---|---|---|
| RK1 | Extraction silently changes an operator contract | Parity suite green **before** the edit, recorded |
| RK2 | "Refactor" becomes a rewrite | Pure helpers only; ≤15 is the stop condition |
| RK3 | Complexity measured with the wrong tool | **ruff only** — mccabe differs by +1 per `try` (S10a §Preflight 1) |
| RK4 | Moving `_cmd_run`'s prologue relocates an early return and changes an exit code | The config-error parity cell is mandatory |
| RK5 | Scope creep into the other 15 waivers | Budget lowers by exactly the number retired here |

---

## 5a. Artifact ledger (A#)

| A# | Artifact | Kind | Owner |
|---|---|---|---|
| **A1** | `tests/test_s10b_cli_parity.py` | NEW — parity oracles, written **before** any edit | S10b.2 |
| **A2** | `tests/test_s10b_complexity_ratchet.py` | NEW — waiver budget + threshold gate | S10b.1 |
| **A3** | `scripts/sweep_specs/s10b_decomposition.json` | NEW — statement-deletion sweep | S10b.6 |
| **A4** | `src/fa/cli.py` | MODIFIED — helpers extracted, waivers deleted | S10b.2–S10b.5 |
| **A5** | this plan | decision record + execution record | closeout |
| **A6** | `worklogs/HANDOFF.md` | handoff | closeout |

**No other file may change.** In particular **no new module under
`src/fa/cli/`** — that is the decision recorded in §0, and a new file
appearing in `git diff --stat` is a scope violation, not an implementation
detail.

## 6. Definition of Done — S10b

- [ ] `_cmd_run`, `_cmd_stats`, `_discover_stats_sources` at **≤15 by ruff**;
      waivers deleted; `_cmd_selfcheck` likewise or deferred with an owner.
- [ ] Waiver budget lowered by exactly the number retired; ratchet gate green.
- [ ] **Parity suite ran green against pre-change code, and that run is
      recorded in the execution record.** Without it CT1 is unproven.
- [ ] Re-inlining any extracted helper: **T2 green, T3 fails** (proven, not
      assumed).
- [ ] Mutation sweep over extracted helpers: **no survivors**, `N passed`
      confirmed.
- [ ] `just check` green; full suite green; **zero new `noqa`**; no UX change.
- [ ] No new modules; `build_parser()` still the composition root.

**Negative proof.** "The suite is green after refactoring" is **not** evidence —
it was green before. The proof is (a) the parity suite was written and run
against pre-change code, and (b) the two oracles diverge on re-inlining. Assume
vacuity until each kill-check is executed.

---

## 7. Open questions

**Q48 — NON-BLOCKING, default recorded.** Should the remaining ~15 C901
waivers get a scheduled programme? **Default: no separate slice** — the S10b.1
ratchet makes the direction structural, and each future slice retires waivers
in code it already touches. Revisit if the budget has not moved in three
slices.

**Q49 — NON-BLOCKING, default recorded.** Does `build_parser` (475 lines,
complexity 100% covered but monolithic) need decomposition? **Default: no** —
it is 100% covered, has **no waiver**, and is a flat sequence of
`add_argument` calls with near-zero branching. Length without complexity is not
debt. Splitting it would satisfy an aesthetic, not a measurement.

---

## 8. Execution record — 2026-08-01

Status: **S10b.0–S10b.2 COMPLETE.** S10b.3–S10b.6 not started.

| Step | Verdict | Evidence |
|---|---|---|
| S10b.0 | **PASS** | Hard gate re-measured, not assumed: `_cmd_run` 82.1 · `_cmd_stats` 87.7 · `_discover_stats_sources` 84.3 · `_cmd_selfcheck` 93.8. All above floor, so S10b.5 is in scope rather than deferred. |
| S10b.1 | **PASS** | 3 C1 gates in `tests/test_s10b_complexity_ratchet.py`; kill-checks bite. |
| S10b.2 | **PASS** | `_cmd_run` **39 → under 15**; waiver retired; budget 19 → 18. |
| S10b.3–.6 | not started | `_cmd_stats` 29, `_discover_stats_sources` 19, `_cmd_selfcheck` 19 still waived. |

### The measurement mechanism changed (worth keeping)

`ruff check --select C901 --ignore-noqa` reports **true** complexity without
touching the working tree. The plan assumed a scratch-copy-and-`sed` approach;
`--ignore-noqa` is exact, faster, and cannot measure a stale copy — which this
workstream has done before (instrument error #7). Both the ratchet gate and
every number below use it.

### CT1 discharged in the required order

The parity suite was written and **run green against unmodified `cli.py`**
before any edit. Recorded: `cli.py` sha256 `8bf6ad56…`, `git diff` empty,
13 passed, `_cmd_run` complexity 39.

Then the net was **proven live** by injecting three regressions into the
pre-change tree — each failed exactly one targeted cell, tree restored each
time: `status_stream` forced to stdout → quiet cell only; `outcome_sink`
export guard removed → LOGIC-11 cell only; a prologue message swapped → the
matching parametrised case only.

### Complexity trajectory (ruff, authority)

`39 → 35 → 32 → 27 → 22 → 18 → 16 → under 15`, parity green at **every** step.
Nine helpers: `_validate_run_args`, `_resolve_run_models`,
`_build_compactor_chain`, `_build_role_registry`, `_build_run_hook_registry`,
`_build_pty_pool`, `_build_output_bus`, `_prepare_pr_draft`,
`_session_db_runtime_error_message`.

### The DoD's central proof, executed

Re-inlining `_validate_run_args`: **T2 green (14 passed) / T3 fails.** Behaviour
and structure are measured independently — that is what makes "no behaviour
change" falsifiable rather than asserted.

### One silent regression caught, and how

`_loop_guard_warn_sink` closed over `output_bus`, a local assigned ~90 lines
*after* hook registration; Python resolves closures at call time, so it worked.
Making the deferred read explicit (`output_bus_ref`, a one-element list) was
fine — but annotating `OutputEvent` under `TYPE_CHECKING` made the emit line
raise `NameError`, and the observer's `except Exception` **swallowed it**.

Every console `loop_warn` would have silently stopped: exit codes unchanged,
artifacts unchanged, all 13 parity cells green. Found only by invoking the sink
directly. Fixed with a function-local import and pinned by a permanent 14th
cell; both kill-checks bite and fail only that cell.

**The lesson generalises beyond this bug:** a decomposition's characteristic
failure is not a wrong exit code, it is an *observability* path that quietly
stops working. Behavioural parity suites do not see it. Any extraction that
moves a callback across a scope boundary needs a direct functional probe.

### Coverage — floors raised, not conceded

`_cmd_run` dipped to **75.7%** when five helpers existed (missing lines
**identical** at 30; the aggregate over `_cmd_run` + helpers *rose* 82.1 →
83.2, so nothing was lost — the same uncovered statements simply sat in a
smaller function). It recovered to **84.5%** as extraction continued, so the
temporary concession to 75 was **reverted** and the 80 floor stands.

Extraction also made three helpers' gaps visible for the first time — inline,
their uncovered branches were absorbed into `_cmd_run`'s aggregate. Rather than
floor them at their measured values, S10b.2 added **8 C0p tests**. The fatal
`draft_store.clear` path is security-relevant (M-7 `IntentGuard` provenance:
proceeding with an unresettable draft would let a mutating tool act on intent
the session never established) and had **no test at all**.

Gate now enforces **20** `cli.py` functions, up from 11.

### Findings

- **I-40, second instance.** `fa run --config <malformed.yaml>` escapes as a raw
  `yaml.YAMLError` traceback instead of exit 2 — the handler catches
  `ConfigurationError`/`EvalFamilyConflictError`/`OSError`, and `YAMLError` is
  none of them. Filed during S10a for `routing-check`; it reproduces on
  `_cmd_run`, so the class is CLI-wide. **Pinned, not fixed**: changing an exit
  code inside a behaviour-invariance slice would make the parity proof
  dishonest. `test_s10b_parity_unparseable_yaml_crashes` inverts when I-40 is
  fixed, which is its purpose.
- **`_build_role_registry`'s permissive `else`** means `fa run --role <typo>`
  gets write+bash tools rather than failing closed. Existing shipped behaviour,
  preserved exactly and documented in the helper so it is not "tidied" into an
  allow-list without treating it as the product change it would be.
- **`_build_compactor_chain` swallows its proxy-rewrite error** while the
  primary chain aborts on the same failure. Deliberate (compaction is
  optional); documented because it reads like a bug.

### Gate

2361 passed / 14 skipped / 1 xfailed · ruff clean · mypy 318 clean · pyrefly
0 errors · pylint exit 0 · authoring-check 0 · cli-coverage-floor 20/20 ·
`ruff format` has zero branch-owned offenders (39 remain from main's `6262e7d`
and clear on rebase).

---

## 9. Execution record — S10b.3–S10b.6 (2026-08-01)

Status: **S10b COMPLETE.** All four C901 waivers in `cli.py` are retired;
`ruff --ignore-noqa` reports **zero** C901 findings for the file.

| Step | Target | Verdict |
|---|---|---|
| S10b.3 | `_cmd_stats` **29 → <15** | **PASS** — GAP2 |
| S10b.4 | `_discover_stats_sources` **19 → <15** | **PASS** — GAP3 |
| S10b.5 | `_cmd_selfcheck` **19 → <15** | **PASS** — GAP4 |
| S10b.6 | mutation sweep | **PASS** — 15/15 CAUGHT, 0 survivors |

Waiver budget **19 → 15**, ratcheted one step per retirement in the same
commit, census-verified at each step. `_RETIRED_WAIVERS` (T3) now covers all
four functions.

### Helpers extracted (16 total across S10b.2–S10b.5)

S10b.3 `_cmd_stats_global_history`, `_render_dead_zones` ·
S10b.4 `_resolve_stats_session_dirs`, `_validate_session_manifest` ·
S10b.5 `_selfcheck_proxy_preflight`, `_selfcheck_fetch_proxy_routes`,
`_selfcheck_route_problems`.

The `_cmd_selfcheck` split follows the command's real phases, which makes the
**exit-2-vs-exit-1 contract structural**: nothing in
`_selfcheck_proxy_preflight` ("your config is wrong") can produce a 1, and
nothing in `_selfcheck_fetch_proxy_routes` ("the proxy is wrong") can produce a
2. `_selfcheck_route_problems` is pure, so the command's actual purpose is now
testable with no proxy at all.

### CT1 discharged for every step

Parity cells written and run green against **unmodified** `cli.py` first
(S10b.3 baseline: sha256 `f40fe066…`, 28 cells, complexity 29), then the net
proven live by injecting regressions that each failed exactly one cell.

DoD divergence re-proven per step — re-inline → **T2 green / T3 fails**:
S10b.3 (28 passed / `_cmd_stats`), S10b.4 (36 / `_discover_stats_sources`),
S10b.5 (42 / `_cmd_selfcheck`).

### Findings and corrections worth carrying

- **I-41 was a live defect, not a smell — and fixing it revealed a second
  binding.** `fa.stats.render_session`/`render_aggregate` declared
  `stream: TextIO = sys.stderr`, evaluated at **import** time. It surfaced as
  `ValueError: I/O operation on closed file` when an S10b.3 parity cell ran
  after a test whose capsys buffer had since closed. Fixing `.write` alone was
  not enough: both functions also call `stream.flush()`, which my first patch
  turned into `None.flush()`. The stream is now resolved **once** into a local
  so write and flush cannot diverge. Q53 → operator chose fix-now. Third
  instance of the class after V10 and S8.8; a repo-wide grep confirms these
  were the only two sites.
- **A kill-check that does not fail is a claim about the kill-check.** In
  S10b.4 the first divergence attempt re-inlined *one* of two helpers and T3
  **passed** — correctly: complexity landed at exactly 15, legitimately under
  threshold. The honest inverse is re-inlining both. Investigate a
  non-failing kill-check before concluding the gate is fine *or* broken.
- **A trap I introduced and removed.** After ratcheting to 15 the liveness
  floor `_C901_CENSUS_FLOOR` was *also* 15, so the next legitimate retirement
  anywhere under `src/fa` would fail the liveness check — and the obvious fix
  would be to edit the floor down, training exactly the reflex the gate exists
  to prevent. Lowered to 13 and re-verified that a deliberately broken census
  still fails it.
- **Sweep specs need a pre-check.** Two of fifteen `old` patterns did not match
  the source (one indentation, one line ruff had reformatted). The harness
  scores an absent pattern as **SKIP**, so the run would have silently covered
  13 mutations while the summary still looked clean. Every pattern is now
  asserted to match exactly once before the sweep runs.
- **Ruff as a collaborator, not just a gate.** `F401` caught an
  `import time as _time` stranded in `_cmd_stats` after its only user moved,
  and **`RUF100` announced the C901 waivers as unused** — which is how the
  ratchet is supposed to report that a target has been met.

### Gate

2387 passed / 14 skipped / 1 xfailed · ruff check clean · mypy 318 clean ·
pyrefly **0 errors** · pylint **exit 0** · authoring-check 0 · lock-check,
dependency-contract, contract-check, log-kind, no-mocked-dataclasses all PASS ·
`cli-coverage-floor` **27/27** (was 11 at S10b start) · `cli.py` coverage
**90.6%** · mutation sweep 15/15 caught.

### Open

- **Q48** (a scheduled programme for the remaining 15 waivers) is now live:
  every `cli.py` waiver is gone, and the 15 that remain are in
  `inner_loop/`, `stats.py`, `skills/`, `memory/`, `sandbox/` and
  `verifier/`. The recorded default was "no separate slice"; the ratchet makes
  the direction structural.
- **I-40** remains open and is now pinned in two places (`routing-check` from
  S10a, `_cmd_run` from S10b.2). `fa run --config <malformed.yaml>` still
  escapes as a raw `yaml.YAMLError`. Fixing it is a product change and will
  invert `test_s10b_parity_unparseable_yaml_crashes` by design.
