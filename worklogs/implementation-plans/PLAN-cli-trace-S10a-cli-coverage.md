# PLAN: S10a — CLI coverage to 80% (prerequisite for S10b decomposition)

Plan-ID: `PLAN-cli-trace-S10a-cli-coverage`
Status: **COMPLETE (2026-07-31)** — all 7 steps executed. `cli.py` **59% →
83.5%**; all 11 target functions clear their floors; gate green. Execution
record in §11.
Previously: **READY** — no blocking questions. Q40 resolved by the operator
(in-module decomposition, **after** coverage); Q43–Q46 resolved 2026-07-31.
Depth: **P1** — additive tests plus narrowly-scoped testability seams. No
behaviour change, no module topology change.
Revision: **v1 (reviewed)** · Changed-since-last: split out of the former
single-slice S10 plan, then a **self-review pass** that found four defects in
this plan:
**(A)** the S10a.7 gate was specified as a **pytest test reading coverage
JSON** — proven to fail on every bare `pytest` run, re-introducing the exact
anti-pattern `pyproject.toml:169` warns about; moved to a `just`-invoked
script;
**(B)** S10a.4's mandated assertion string was **wrong** — the seam was
prototyped and the no-seam path emits `no roles found`, not
`configuration error`;
**(C)** the plan named per-command C2 tests **without the Namespace contracts**
— AST-extracted all seven and tabled them;
**(D)** artifacts `A1`/`A2` were referenced with **no ledger** — added §5a.
· **v3 review** found two more: **(E)** `coverage.json` is **not gitignored**,
so the new gate would leave a 1.2 MB untracked file on every `just check` —
and the parent uses `git status --short` as a verification oracle, so that
would permanently falsify "clean tree"; **(F)** the `_cmd_egress_proxy` floor
read *"80 (pre-serve only)"* while the gate scores the **whole function** —
measured 23 pre-`serve` statements vs 2 after, so ~93% is reachable and a
plain 80% whole-function floor is both achievable and unambiguous.
Upstream context: parent
[`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md)
§Step S10; depends on S2, S3, S7, S8, S9 — all COMPLETE.
**Successor:** `PLAN-cli-trace-S10b-cli-decomposition.md` — **must not start
until S10a's DoD is met.**

> **Operator directive (2026-07-31).** *"For all functions we touched here —
> first we establish ~80% strong test coverage using the tests-writing skill.
> After that we may proceed with refactoring."* S10a is that coverage slice.
> Written to the **attached** tests-writing skill (deterministic-enforcement
> and failure-observable central laws, FIX-regression docstring fields,
> manual-mutation minimum) and the attached plan-authoring skill v2
> (`GAP#`/`A#`/`T#`/`M#`).

---

## 0. Why this slice exists, in one paragraph

`cli.py` is **59%** covered. Six commands are effectively dark (1–11%), and
`_cmd_run` — the function whose complexity waiver S10b exists to retire — is at
**71%**. Refactoring any of them today would be *unfalsifiable*: the parity
suite could not fail. This workstream has already been burned six times by
checks that cannot fail (S7.C3, S7.C4, S7.C7, S9's F3, S9.6's two sweep
survivors). S10a buys the right to refactor.

---

## Preflight log (§2 — measured 2026-07-31)

### 1. The CI mystery, resolved — and it invalidated one of my findings

I previously reported **GAP5**: *"`_cmd_workflow` sits at complexity 17 with no
waiver; the ratchet is leaking."* **That was wrong. CI is correct.**

```text
ruff  --select C901   ->  _cmd_workflow = 15   (15 > 15 is FALSE -> passes)
python -m mccabe      ->  _cmd_workflow = 17
```

Root cause, isolated on a five-line fixture: **`mccabe` adds +1 per `try`
statement; `ruff` does not.** The delta equals the `try` count in every
divergent function:

| function | ruff | mccabe | Δ | `try` stmts |
|---|---|---|---|---|
| `_cmd_workflow` | 15 | 17 | +2 | **2** |
| `_resolve_task` | 11 | 15 | +4 | **4** |
| `_run_adaptive` | 14 | 14 | 0 | **0** |

**Consequence, now binding on both S10a and S10b:** `ruff` is the gate
authority (`[tool.ruff.lint.mccabe] max-complexity = 15`), so **every
complexity number in a test or exit criterion must be ruff's.** A gate built on
mccabe's number would disagree with CI permanently.

*Sixth instrument error in this workstream* (after S8.6's `trace` probe and
S9's digit-less regex). Rule: **measure with the tool the gate uses.**

### 2. True complexity, by the authority tool

Measured by stripping `noqa` in a scratch copy and re-running ruff:

| Function | ruff (**authority**) | mccabe | over 15 | Waiver |
|---|---|---|---|---|
| `_cmd_run` | **39** | 51 | **2.6×** | `cli.py:1903` |
| `_cmd_stats` | **29** | 33 | 1.9× | `cli.py:2654` |
| `_discover_stats_sources` | **19** | 21 | 1.3× | `cli.py:2576` |
| `_cmd_selfcheck` | **19** | 24 | 1.3× | `cli.py:2359` |
| `_cmd_workflow` | 15 | 17 | passes ✅ | none needed |
| `_resolve_task` | 11 | 15 | passes ✅ | none needed |

All four waivers are **real and load-bearing** — remove any and CI fails.

### 3. Per-function coverage census (`--cov=fa.cli`, json report)

| Function | cov% | stmts | dark | lines | S10a target |
|---|---|---|---|---|---|
| `build_parser` | 100 | 80 | 0 | 475 | — |
| `_run_stage` / `_run_linear` / `_run_initial_roles` | 100 | 41 | 0 | 129 | — |
| `_run_repair` | 96 | 28 | 1 | 78 | — |
| `_cmd_workflow` | 89 | 71 | 8 | 186 | — |
| `_cmd_inner_loop_smoke` | 87 | 38 | 5 | 148 | — |
| `_run_adaptive` | 79 | 48 | 10 | 138 | **80** |
| `_discover_stats_sources` | 77 | 52 | 12 | 76 | **80** |
| `_resolve_task` | 76 | 29 | 7 | 60 | **80** |
| **`_cmd_run`** | **71** | 180 | 53 | 418 | **80** ← S10b's target |
| `_cmd_stats` | 36 | 99 | 63 | 164 | **80** |
| `_cmd_authoring_check` | 11 | 9 | 8 | 15 | **80** |
| `_cmd_chunk` | 5 | 19 | 18 | 29 | **80** |
| `_cmd_routing_check` | 5 | 19 | 18 | 34 | **80** |
| `_cmd_egress_proxy` | 4 | 26 | 25 | 54 | **80** (see note) |
| `_cmd_probe` | 2 | 61 | 60 | 100 | **80** |
| `_cmd_selfcheck` | 1 | 87 | 86 | 113 | **best-effort** (Q45) |

### 4. Testability triage — why the dark commands are dark

| Command | Network/proc calls | Blocker | Seam available? |
|---|---|---|---|
| `_cmd_routing_check` | **0** | none — pure `models.yaml` lint | already testable |
| `_cmd_chunk` | **0** | none — file in, file out | already testable |
| `_cmd_authoring_check` | **0** | none — local AST scan | already testable |
| `_cmd_egress_proxy` | 0 | terminal `serve(...)` call | `serve` is an **imported delegate** → monkeypatchable |
| `_cmd_selfcheck` | 2 | both via `_selfcheck_http_get` | **one module-level function** → one patch point |
| `_cmd_probe` | 0 | builds its own transport internally | **needs a seam** (Q44) |

**Three of the six need no new code at all.** They were never dark for
technical reasons — only for lack of tests.

### 5. `_cmd_egress_proxy` has a real testable surface (answers Q4)

Reading the body: **four validation branches, each `return 2`, all before
`serve(...)`** — models-config error, route-table error, missing token, invalid
`--listen`. Plus `serve` is imported, so the happy path is assertable by
patching it and checking the call arguments. **No port is ever bound.** This is
a genuine surface, so per the operator's instruction it gets covered rather
than exempted.

### 6. Prior art for the seam question (answers Q2 — see §7 for the verdict)

`_cmd_run` and `_cmd_workflow` **already** carry keyword-only
`transport: Transport | None = None` / `secrets: Mapping[str, str] | None = None`
seams (`cli.py:1904-1908`, `:1718-1719`), and they are **production-used**, not
test-only: `_run_stage` passes `transport=ctx.transport` on the real workflow
path (`cli.py:1256`), and `_cmd_workflow` forwards to `_cmd_run` (`:1825`).
`_cmd_run` resolves it with the default-to-real idiom
(`effective_transport = transport if transport is not None else UrllibTransport()`,
`cli.py:2014`).

**These are also the two best-covered command functions in the file (71% and
89%) — and the dark ones are exactly those lacking the seam.** The correlation
is the argument.

---

## 1. GAP ledger (§4)

| GAP# | Verified current | Target | Owner |
|---|---|---|---|
| **GAP1** | 3 pure commands untested (`routing_check` 5%, `chunk` 5%, `authoring_check` 11%) despite needing no seam | ≥80% each | S10a.2 / T1 |
| **GAP2** | `_cmd_egress_proxy` 4%; 4 validation branches + delegate call untested | ≥80% of the **pre-serve** surface | S10a.3 / T2 |
| **GAP3** | `_cmd_probe` 2%; **no injection seam**, so untestable without one | seam added + ≥80% | S10a.4 / T3 |
| **GAP4** | `_cmd_selfcheck` 1%; 2 network calls behind one helper | **best-effort**, target ≥60% | S10a.5 / T4 |
| **GAP5** | ~~ratchet leaking~~ | **WITHDRAWN — instrument error, CI correct** | §Preflight 1 |
| **GAP6** | `_cmd_run` 71%, `_cmd_stats` 36% — both below the refactor bar | ≥80% each | S10a.6 / T5, T6 |
| **GAP7** | `_run_adaptive` 79%, `_discover_stats_sources` 77%, `_resolve_task` 76% | ≥80% each | S10a.6 / T7 |

---

## 2. Contracts (§6)

### CT1 — testability seams are production seams, not test hooks

- **AUTHORITY:** the existing `_cmd_run` / `_cmd_workflow` signature idiom.
- **Contract:** any seam S10a adds is **keyword-only**, defaults to `None`,
  and resolves to the real collaborator via the default-to-real idiom. Calling
  the command with no seam argument must be byte-identical to today.
- **DETERMINISTIC MECHANISM:** the default branch is exercised by a test that
  passes **no** seam argument, so "the default still works" is asserted, not
  assumed.
- **FAILURE SURFACE:** n/a — a seam cannot fail; its absence is a type error.
- **KILL-CHECK:** change the default from `None` to a stub → the
  no-argument test fails.

### CT2 — coverage floor per function

- **Contract:** every function in the GAP ledger reaches its stated target,
  measured by `pytest --cov=fa.cli` statement coverage.
- **DETERMINISTIC MECHANISM:** a test that reads the coverage JSON and asserts
  per-function floors — **not** an aggregate, which is gameable by covering
  easy functions (Q46).
- **FAILURE SURFACE:** named function + measured percentage in the assertion.

### CT3 — no behaviour change

- **Contract:** exit codes, stdout/stderr streams, flags, help registry and
  artifact paths are unchanged by S10a.
- **KILL-CHECK:** the full existing suite (2272 tests) stays green; any
  behaviour edit shows up there first.

**Security contract:** N/A — S10a adds no boundary. The seams carry
`secrets` *into* a function that already loads secrets itself; no secret
crosses a new trust line.

---

## 3. Steps (§8)

> **Per-step protocol.** Before editing: source-verified behaviour, GAP/CT IDs,
> exact files, stop on blockers. Each edit: idea / intent / current→target /
> mechanism / best practice / failure behaviour / DoD + negative proof / test
> class / kill-check / **degree of freedom closed**. After: targeted tests,
> static checks, `git diff`, **report actual output**. Never complete from "no
> exception".

### Step S10a.0 — Re-baseline every measurement with the authority tool

**Files allowed to change: none.**

Do:

1. `ruff --select C901` with `noqa` stripped in a scratch copy → record ruff's
   number for all four waived functions.
2. Coverage JSON → per-function census.
3. Confirm the three pure commands still need no seam.

Exit: all three reproduce, or the plan is amended before any test is written.

---

### Step S10a.1 — Shared CLI test fixtures (`A1`)

**Files:** `tests/test_s10a_cli_coverage.py` (NEW).

Build once, use everywhere: `_cli_home` (isolated `$HOME` + models config) plus
one `_args_for_<command>(**overrides)` helper per command. Rationale is the S9
lesson — five C2 tests were nearly written against a hand-rolled Namespace
reverse-engineered from two inconsistent examples.

**The Namespace contracts, AST-extracted during the v1 review** (do not
re-derive; do not guess — every attribute each command actually reads):

| Command | `args.*` attributes |
|---|---|
| `_cmd_chunk` | `output`, `path` |
| `_cmd_routing_check` | `config` |
| `_cmd_authoring_check` | `manifest`, `output`, `workspace` |
| `_cmd_egress_proxy` | `listen`, `models`, `secrets`, `token_file` |
| `_cmd_probe` | `all_roles`, `config`, `role`, `timeout` |
| `_cmd_selfcheck` | `config`, `role` |
| `_cmd_stats` | `dead_zones`, `global_history`, `output`, `run_id`, `session_id`, `since`, `workspace` |
| `_cmd_run` | use `_run_args` (`tests/test_s7_cli_run_paths.py:47`) — **do not rebuild** |

A missing attribute raises `AttributeError` at an arbitrary depth rather than
producing the exit code under test, so an incomplete Namespace fails for the
wrong reason. Verified by re-extraction rather than by reading the argparse
definitions, because `getattr(args, "x", default)` sites do not appear in the
parser.

**Do-not:** do not re-invent `_run_args`; import it
(`tests/test_s7_cli_run_paths.py:47`).

---

### Step S10a.2 — The three pure commands (GAP1 / T1)

**Files:** `tests/test_s10a_cli_coverage.py`.
**No production change** — these need no seam.

`_cmd_routing_check` (34 lines), `_cmd_chunk` (29), `_cmd_authoring_check` (15).
Each: happy path + at least one **failure-observable** path asserting the exact
exit code and the structured stderr message (attached skill's
failure-observable central law — no silent skips).

**Test class: C2.** **Oracle:** exit code + stderr substring + FS effect for
`chunk`. **Kill-check:** delete the command's error branch → the negative test
fails. **Negative proof:** assert a *specific* exit code, never `!= 0`.

---

### Step S10a.3 — `_cmd_egress_proxy` pre-serve surface (GAP2 / T2)

**Files:** `tests/test_s10a_cli_coverage.py`.
**No production change** — `serve` is already an imported delegate.

Cover the four `return 2` validation branches, then the happy path by
monkeypatching `serve` and asserting **the arguments it receives**
(`route_table`, `proxy_token`, `host`, `port`) — that is the real contract of
this command, and it never binds a port.

> **Floor arithmetic — v3-review, resolving an ambiguity.** The census note
> said *"80 (pre-serve only)"*, but the gate reads **whole-function**
> `percent_covered`; there is no way to score a hand-drawn subset. Measured:
> the function has **23 statements before `serve()` and 2 at/after**
> (`cli.py:2931-2984`, `serve` at `:2977`), i.e. **~92% is reachable** without
> binding a port, and with the 2 post-`serve` statements dark the best case is
> **~93% `percent_covered`**. So the plain **80% whole-function floor is both
> achievable and honest** — no subset carve-out, no exemption. The wording is
> corrected accordingly.

**Do-not:** do not start a server; do not assert on log prose.
**Kill-check:** delete the `--listen` validation → that negative test fails.

---

### Step S10a.4 — `_cmd_probe`: add the seam, then cover (GAP3 / T3 / CT1)

**Files:** `src/fa/cli.py`, `tests/test_s10a_cli_coverage.py`.

**This is the only step that changes a production signature.** Add
keyword-only `transport: Transport | None = None` and
`secrets: Mapping[str, str] | None = None` to `_cmd_probe`, resolved with the
same default-to-real idiom `_cmd_run` uses at `cli.py:2014`. See §7 Q44 for
the research verdict justifying this shape.

**Degree of freedom closed:** before, `_cmd_probe` could only be exercised by a
real network call, so *no* test could observe it and any future edit was
unverifiable. After, the collaborator is a parameter and the default path is
itself asserted.

**Do-not:** do not change the default behaviour; do not make the parameter
positional; do not thread it deeper than the existing `_build_provider_chain`
call (`cli.py:2527` already accepts `transport=`).

**Kill-check:** flip the default to a stub → the no-argument test fails.
**Negative proof:** a test that only ever passes a fake transport would not
notice the production path breaking — one test must call `_cmd_probe(args)`
with **no** seam and assert it still reaches config validation.

> **v1-review correction — the seam was prototyped and the mandated assertion
> was wrong.** I applied the seam to a scratch copy and ran it: `ruff` clean,
> `mypy` clean (315 files), fake transport → **exit 0** with `OK` on stdout,
> and the no-seam call → **exit 2**. But the no-seam path emits
> `fa probe: no roles found in <path>`, **not** `configuration error` — a
> missing file yields an empty-roles config rather than a read error. A test
> asserting the wrong string would have failed on correct code.
>
> **Mandated assertion:** exit code **2** plus stderr containing
> `no roles found`. The prototype was reverted; S10a.4 implements it for real.
>
> The seam's mechanics are confirmed: `transport` is a single local
> (`cli.py:2505`) flowing to one `_build_provider_chain` call (`:2527`), and
> `secrets` needs the same treatment because `load_models_config_from_path`
> consumes it (`:2518`). Both resolve with the house default-to-real idiom.

---

### Step S10a.5 — `_cmd_selfcheck`, best-effort (GAP4 / T4)

**Files:** `tests/test_s10a_cli_coverage.py`.
**No production change** — both network calls go through the single
module-level `_selfcheck_http_get` (`cli.py:2868`), so one monkeypatch covers
them.

Target **≥60%**, not 80 (Q45): the remainder is diagnostic output formatting
whose value per test is low. Cover: proxy-unreachable, health-endpoint failure,
routes-payload mismatch, happy path. The already-extracted helpers
`_selfcheck_expected_routes` (`:2886`) and `_selfcheck_parse_routes_payload`
(`:2895`) get direct **C0p** tests — they are pure and are where the real logic
lives.

**Do-not:** do not chase the last 40% with assertions on banner text.

---

### Step S10a.6 — Lift the runtime-critical functions to 80% (GAP6, GAP7 / T5–T7)

**Files:** `tests/test_s10a_cli_coverage.py`.
**Priority order — most operationally important first** (operator: *"focus on
important runtime functions first"*):

1. **`_cmd_run` 71 → 80** — the S10b target. **Feasibility measured in the v1
   review**, not assumed: its 53 dark statements decompose as *error/print* 8,
   *return* 7, *except/raise* 10, *other* 28 — and the "other" 28 are the
   **proxy-mode** branch (`cli.py:1978-1982`, `:2025-2029`), the **`--resume`
   draft read** (`:2077-2078`), and two **observer `try` blocks**
   (`:2120`, `:2129`). Every one is reachable from the CLI with a scripted
   transport; none needs network or a container. Reaching 80% requires roughly
   **17 additional covered statements** — comfortably inside three or four
   tests (proxy on, resume on, secret-redactor failure, unknown role).
2. **`_cmd_stats` 36 → 80** — largely the `--global-history` rendering branch
   and `--dead-zones`.
3. `_run_adaptive` 79 → 80, `_discover_stats_sources` 77 → 80, `_resolve_task`
   76 → 80 — small deltas, mostly one or two uncovered guards each.

**Kill-check per test:** delete the guard the test targets → that test fails.
This is the **manual-mutation minimum** from the attached skill: remove the
branch, rerun, confirm failure, restore, report.

---

### Step S10a.7 — Per-function coverage gate (CT2 / A2)

**Files:** `scripts/check_cli_coverage_floor.py` (NEW), `justfile`.
**NOT a pytest test — see the correction below.**

A deterministic gate reading the coverage JSON and asserting each function's
floor, floors as literals that may only be **raised**. Per-function, not
aggregate (Q46) — an aggregate is satisfiable by covering `build_parser`
harder while `_cmd_probe` stays dark.

> **v1-review correction — the original design was broken.** The gate was
> specified as `tests/test_s10a_coverage_floor.py`, i.e. a pytest test that
> reads the coverage report. **That fails on every bare `pytest` run**, because
> coverage flags are deliberately excluded from `addopts`. `pyproject.toml:169`
> states the reason:
>
> > *"coverage flags intentionally NOT in addopts. A bare `pytest
> > tests/test_x.py` must work for agents iterating on a single module (a
> > partial run would always 'fail' the 90% gate and **teach agents to ignore
> > red output**)."*
>
> Proven, not reasoned: a one-line test asserting `coverage.json` exists was
> dropped into `tests/` and run bare — **FAILED**. Shipping the gate as a test
> would have re-introduced the precise anti-pattern the config was written to
> prevent, and trained every future agent to ignore a red suite.
>
> **Correct home: a script invoked by `just`**, exactly like the eight existing
> gates (`contract-check`, `log-kind-check`, `authoring-check`, …). It runs
> after `just test` has produced coverage data, so the data is guaranteed
> present. This also matches the repo's own convention rather than inventing a
> ninth pattern.

Do:

1. `scripts/check_cli_coverage_floor.py` — read `coverage.json`, look up
   `files["src/fa/cli.py"]["functions"][<name>]["summary"]["percent_covered"]`
   (verified present: the report carries **59** function entries with a
   `percent_covered` float, so no line-range arithmetic is needed), compare
   against a `_FLOORS: dict[str, float]` literal, exit 1 listing every function
   below its floor.

   > **Metric choice is load-bearing — v2-review finding.** The summary block
   > exposes **two** different numbers and they disagree:
   > `percent_covered` = **74.7** vs `percent_statements_covered` = **76.5**
   > for `_discover_stats_sources`. A plan that says "80% coverage" without
   > naming the field lets an executor pick either and get a different
   > pass/fail.
   >
   > **Use `percent_covered`.** It is branch-inclusive, and the repo sets
   > `branch = true` (`pyproject.toml:188`, *"branch coverage catches untested
   > if/else paths"*), so it is the metric CI's own `fail_under` already
   > enforces. Choosing the statements-only number would be a quieter gate
   > than the one the repo already runs.
   >
   > **The §Preflight 3 census below reports statement percentages** (it was
   > built before this was settled); the *floors* in this script are
   > `percent_covered`. Where they differ the census reads ~1–2 points higher,
   > so the floors are marginally stricter than the census implies. That is
   > the safe direction, and it is stated rather than left as a trap.
2. Add `--cov-report=json` to the `just test` recipe so the artifact exists.
   Verified in review: the flag works on the exact existing command and writes
   `coverage.json` at the repo root (1.2 MB).
3. **Add `coverage.json` to `.gitignore`** — *v3-review finding*. It is **not**
   currently ignored (`.gitignore:45-52` covers `.coverage`, `.coverage.*`,
   `coverage.xml`, `coverage/` — but **not** `coverage.json`; confirmed by
   generating one and seeing `?? coverage.json`). Without this, every `just
   check` leaves a 1.2 MB untracked file. That is not cosmetic: the parent
   plan uses `git status --short` as a verification **oracle** (§CT at line
   1086, S11 step 11, S4 §2058), so a per-run artifact would make "the repo is
   clean after a run" permanently false and train reviewers to ignore it.
   This entry belongs next to the existing `coverage.xml` line so the two stay
   together.
4. Add a `cli-coverage-floor` recipe and append it to the `check` chain.

**Liveness controls (both mandatory):** the script exits non-zero if
`coverage.json` is **missing** (never silently passes) and if the function
table has **< 40** entries (a broken parse cannot pass vacuously).

**Failure surface:** a structured line per offender —
`_cmd_probe: 41.2% < floor 80.0%` — per the attached skill's
failure-observable law. Not a bare assertion error.

---

## 4. Verification plan (§9)

| T# | Test | Class | Oracle | Kill-check | GAP |
|---|---|---|---|---|---|
| T1 | `test_s10a_routing_check_*`, `_chunk_*`, `_authoring_check_*` | C2 | exit code + stderr + FS | delete an error branch | GAP1 |
| T2 | `test_s10a_egress_proxy_*` | C2 | exit code; `serve` call args | delete `--listen` validation | GAP2 |
| T3 | `test_s10a_probe_*` incl. **no-seam default** | C2 | exit code + chain built | flip seam default | GAP3 |
| T4 | `test_s10a_selfcheck_*` + C0p on the two pure helpers | C2+C0p | exit code; helper return values | delete a route-mismatch branch | GAP4 |
| T5 | `test_s10a_cmd_run_error_paths` | C2 | exit 2 + structured stderr | delete a guard | GAP6 |
| T6 | `test_s10a_cmd_stats_*` | C2 | exit code + rendered JSON keys | delete the filter branch | GAP6 |
| T7 | `test_s10a_*` small-delta tests | C2 | per-function | per-guard | GAP7 |
| T8 | `test_s10a_coverage_floor` | C1 | per-function coverage JSON | lower a floor | CT2 |

**CI authority:** `just check`.

---

## 5. Risks

| RK# | Risk | Mitigation | Detected by |
|---|---|---|---|
| RK1 | Seam on `_cmd_probe` changes production behaviour | Default-to-real; a no-seam test asserts the default path | T3 |
| RK2 | Coverage chased with assertion-free "it ran" tests | Every test asserts an exit code **or** a structured message; no bare smoke | Review + T8 |
| RK3 | `_cmd_selfcheck` best-effort becomes an excuse to skip it | Floor of 60% is a literal in the gate | T8 |
| RK4 | Tests written against internals freeze the shape S10b wants to change | Oracles are exit codes and artifacts, **never** call-order of internals | Review |
| RK5 | Coverage rises but the tests are vacuous | Manual-mutation minimum per step: delete the branch, confirm failure | Each step |

**RK4 is the subtle one.** Coverage tests written now must not become the thing
that makes S10b's refactor hard. They therefore assert **behaviour at the
command boundary** — exit code, streams, artifacts — never that a particular
private helper was called.

---

## 5a. Artifact ledger (A#)

| A# | Artifact | Kind | Owner |
|---|---|---|---|
| **A1** | `tests/test_s10a_cli_coverage.py` | NEW — all S10a tests + shared fixtures | S10a.1–S10a.6 |
| **A2** | `scripts/check_cli_coverage_floor.py` | NEW — the per-function gate | S10a.7 |
| **A3** | `justfile` | MODIFIED — `--cov-report=json` on `test`; new `cli-coverage-floor` recipe appended to `check` | S10a.7 |
| **A4** | `src/fa/cli.py` | MODIFIED — **the `_cmd_probe` seam only** | S10a.4 |
| **A5** | `.gitignore` | MODIFIED — add `coverage.json` beside `coverage.xml` | S10a.7 |
| **A6** | this plan | execution record | closeout |
| **A7** | `worklogs/HANDOFF.md` | handoff | closeout |

**No other file may change.** `git diff --stat` at closeout must show exactly
**A1–A5** plus the two worklog files (A6, A7). `.gitignore` is listed
explicitly because the DoD forbids unlisted edits — without the entry an
executor following the letter of the plan would be blocked from ignoring
`coverage.json`, and would either skip it (leaving the repo dirty every run)
or edit an unlisted file.

## 6. Definition of Done — S10a

- [ ] Per-function coverage: **≥80%** for `_cmd_run`, `_cmd_stats`,
      `_cmd_probe`, `_cmd_routing_check`, `_cmd_chunk`, `_cmd_authoring_check`,
      `_cmd_egress_proxy` (pre-serve), `_run_adaptive`,
      `_discover_stats_sources`, `_resolve_task`; **≥60%** for
      `_cmd_selfcheck`.
- [ ] `test_s10a_coverage_floor` enforces those floors as literals.
- [ ] Every test carries its class, ranked oracle and kill-check target in the
      docstring, per the **attached** tests-writing skill; every FIX-shaped
      test carries `degree-of-freedom-closed` / `deterministic-mechanism` /
      `sibling-callers-checked` / `mutation`.
- [ ] **Manual-mutation minimum executed per step** — branch removed, failure
      observed, code restored, result reported. A survivor means a weak oracle.
- [ ] `just check` green; full suite green; **zero new `noqa`**.
- [ ] **One** production change total: the `_cmd_probe` seam (**A4**).
      `git diff --stat` shows only A1–A5 plus worklogs — no other `src/` edit.
- [ ] **`git status --porcelain` is empty after a full `just check`** — no
      stray `coverage.json`. The parent uses tree cleanliness as an oracle
      (S11 step 11), so a per-run artifact is a regression, not noise.
- [ ] No behaviour change: exit codes, streams, flags, help, artifact paths.

**Negative proof.** Coverage percentage is *not* the DoD — a file can be 100%
covered by tests that assert nothing. The DoD is the **mutation minimum**: for
every branch this slice claims to cover, deleting it must fail a named test.
Six checks in this workstream have already been caught passing vacuously.

---

## 7. Open questions — all resolved

**Q40 — RESOLVED (operator):** in-module decomposition, **not** module
extraction — and only **after** coverage. Split into S10a (this plan) and
S10b.

**Q43 — RESOLVED (operator): scope is all seven+ functions**, coverage first.

**Q44 — RESOLVED: the `transport=`/`secrets=` seam is production-grade here.**

*Research findings.* The literature is genuinely split on optional-parameter
DI. The strongest critique ([codegenes on optional
dependencies](https://www.codegenes.net/blog/dependency-injection-optional-parameters/))
argues optional params hide dependencies, let a test silently exercise the real
collaborator, and encourage SRP violations — its recommendation is required
constructor params with a factory for defaults. The counter-position, and the
common Python idiom, is `def foo(dep=None): dep = dep or Real()` — described on
[Stack Overflow](https://stackoverflow.com/questions/33349025/how-to-do-basic-dependency-injection-in-python-for-mocking-testing-purposes/48615660)
as *"pure dependency injection (quite simple) without magical frameworks"*, and
echoed as a preferred pattern in [r/Python
discussion](https://www.reddit.com/r/Python/comments/195uk6d/do_you_prefer_mock_or_dependency_injection_when/).
[Chris Ayers](https://chris-ayers.com/posts/dependency-injection-architecture-and-testing/)
names this **parameter injection** and endorses it precisely for *"expensive
creation of dependencies used in infrequent edge cases"* — a live network
client in a diagnostic command is exactly that case.

*Why the critique does not bite here.* Its two real objections are (a) hidden
dependencies and (b) tests accidentally using the real collaborator. (a) is
answered because the parameter is **keyword-only and typed**, so it is visible
in the signature and enforced by mypy. (b) is answered by making the default
path an **explicit assertion**: T3 calls `_cmd_probe(args)` with no seam and
asserts it still reaches config validation, so the default is covered rather
than assumed. The critique's own preferred alternative — a factory — would add
a component this codebase has no other consumer for, which the attached
plan-authoring skill's **component gate** rejects.

*Decisive evidence — internal prior art.* This is not a new pattern being
introduced; it is the pattern **already used** by the two best-covered command
functions in the file, and it is **production-used, not a test hook**:

```text
_cmd_run(args, *, transport=None, secrets=None, outcome_sink=None)   cli.py:1904
_cmd_workflow(args, *, transport=None, secrets=None)                 cli.py:1718
_run_stage -> _cmd_run(..., transport=ctx.transport)                 cli.py:1256   (real path)
effective_transport = transport if transport is not None else UrllibTransport()   cli.py:2014
```

Coverage correlates exactly: the two commands **with** the seam are at 71% and
89%; the ones **without** it are at 1–5%. Adopting the house idiom is also
strictly better than inventing a second one.

**Verdict: adopt for `_cmd_probe` only** (GAP3). `_cmd_selfcheck` does **not**
need it — one monkeypatch on `_selfcheck_http_get` suffices, and the smallest
change that works wins.

**Q45 — RESOLVED (operator): `_cmd_selfcheck` is best-effort**, floor 60%.

**Q46 — RESOLVED (operator): per-function**, not aggregate.

**Q47 — RESOLVED (operator + measurement): `_cmd_egress_proxy` gets real
tests.** It has four pre-`serve` validation branches and a monkeypatchable
`serve` delegate, so no exemption is warranted.

---

## 8. Anti-theater + READY gate

- [x] Every symbol verified with file:line + a measurement
- [x] Every GAP# has an owning step and a T#
- [x] Kill-check named per step; manual-mutation minimum mandated
- [x] Fixtures honest (`_run_args` imported, not re-invented)
- [x] Component gate applied — it **rejects** a DI factory/framework (Q44)
- [x] Deterministic authority — CT2 is a gate, not a judgement
- [x] Assumptions labelled; GAP5 withdrawn with its root cause
- [x] All IDs resolve: GAP1–GAP7, CT1–CT3, S10a.0–S10a.7, T1–T8, RK1–RK5,
      Q40/Q43–Q47, A1–A2
- [x] **BLOCKING question set EMPTY**

**→ Status: READY.** Order: S10a.0 → S10a.1 → {S10a.2, S10a.3 parallel} →
S10a.4 → S10a.5 → S10a.6 → S10a.7.


---

## 11. Execution record — 2026-07-31

| Step | Verdict | Evidence |
|---|---|---|
| S10a.0 | PASS | ruff re-baseline matched (39/29/19/19); census reproduced |
| S10a.1 | PASS | shared fixtures + the 7 AST-extracted Namespace contracts |
| S10a.2 | PASS | `_cmd_chunk` **100** · `_cmd_routing_check` **100** · `_cmd_authoring_check` **100** |
| S10a.3 | PASS | `_cmd_egress_proxy` **89.7** (~93 is the no-bind ceiling) |
| S10a.4 | PASS | `_cmd_probe` **2 → 81.6**; the one production change |
| S10a.5 | PASS | `_cmd_selfcheck` **1 → 60.7** (best-effort floor met) |
| S10a.6 | PASS | `_cmd_run` **82.1** · `_cmd_stats` **87.7** · `_discover_stats_sources` **84.3** · `_resolve_task` **80.0** |
| S10a.7 | PASS | gate script + `just` recipe; 3 kill-checks bite |

**Final gate:** 2334 passed / 14 skipped / 1 xfailed · `ruff` clean · bare
`mypy` 316 files clean · `pylint src/fa` 10.00/10 · `authoring-check` 0 ·
**0 new `noqa`** · `git status` clean.

**Artifacts** — exactly the ledger, nothing else: A1 `tests/test_s10a_cli_coverage.py`
(62 tests), A2 `scripts/check_cli_coverage_floor.py`, A3 `justfile`,
A4 `src/fa/cli.py` (**the `_cmd_probe` seam only**), A5 `.gitignore`.

### Mutation minimum — the part that actually found things

Roughly 30 guards were deleted one at a time. **Seven survivors**, each a real
weakness, each fixed:

| survivor | why it survived | fix |
|---|---|---|
| `_cmd_chunk` path guards ×2 | *redundant guards* — `is_file()` also rejects a missing path, so exit 2 either way | recorded, not "fixed"; the product is fine |
| `_cmd_selfcheck` no-proxy-url | same shape — `_validate_proxy_url` rejects `""` too | recorded |
| `health != 200`, `routes == 403` | tests asserted only exit 1 + the status number; the downstream generic handler produces both | assert **branch-unique wording** |
| compactor block | run succeeds without a compactor chain | count `_build_provider_chain` invocations |
| `--dead-zones` | exit 0 either way | assert the report text |

**A mutation that hangs is not a survivor.** Deleting the empty-token guard let
execution reach the real blocking `serve()`; the harness scored a 300-second
timeout as "SURVIVED". Every proxy test now patches `serve` so the mutation
**fails fast** — a hang is indistinguishable from a slow suite and gets retried
away.

### Three findings, none fixed here (coverage slice)

- **I-40** — `fa routing-check --config /does/not/exist` exits **0**
  ("no roles declared"). `scripts/fa-clean-rebuild.sh:471` uses it as a
  **pre-build deploy gate** and logs "Routing lint: OK" having validated
  nothing. Found by a test written to assert exit 2 that failed. Also:
  unparseable YAML escapes as `yaml.ParserError`, which that handler does not
  catch. Today's behaviour is **pinned** so the fix is a visible diff.
- **I-41** — `fa.stats.render_session`/`render_aggregate` bind
  `stream=sys.stderr` as a *default argument*, i.e. at import time. **Third
  instance** of the import-time-binding class after V10 (`state.py`) and S8.8
  (`global_history.py`). Found because a test passed alone and failed in the
  suite.
- **`_cmd_run`'s `SecretRedactorError` handler is unreachable** from the CLI —
  config validation rejects an empty secret store ~40 lines earlier. Left
  uncovered with the reason in-line: an honest gap beats a test that proves
  only its own mock.

### Method note — the instrument was wrong again

Early mutation runs reported **6/6 survived**, which was implausible. Cause:
the editable install pointed at a leftover rebase-test clone
(`~/.s10b-rebase-test/src/fa`), so every test ran against the **wrong source
tree**. Reinstalled, and the same sweep produced real results. *Verify what the
interpreter actually imported before trusting a measurement* — the seventh
instrument error in this workstream.

### Ready for S10b

Every function S10b intends to decompose is now above its floor, so the parity
suite it writes can actually fail. Oracles here are exit codes, structured
messages, artifacts and delegate arguments — never internal call order — so the
decomposition stays free to move code (plan RK4).

---

## 12. Post-closeout baseline repair — 2026-08-01

S10a's own DoD was independently re-verified and **holds** (audit:
`worklogs/VERIFY-S10a-2026-08-01.md`). Re-measuring in a rebuilt sandbox
surfaced two gates in the `just check` chain that were **red and unread**,
neither introduced by S10a. Both are closed; the baseline is now green.

| Finding | Root cause | Resolution |
|---|---|---|
| **F1** | `test_pyrefly_check_passes` ignored the return code and filtered stdout, so a **missing** pyrefly scored as zero errors | Split into an installed-check (**Q51: fail loudly**) and a three-oracle gate: exit code + parsed count + the stderr `INFO <n> errors` liveness line |
| **Q50** | pyrefly claimed "Advisory-only" in `pyproject.toml` while the test blocked | Declared **BLOCKING** in all four seats |
| **F3** | `PARSED_KINDS` duplicated 23 `LogKind` names → R0801 → `fail-on` binary gate → `pylint` exit 8 since **S9 (`c611b34`)** | Derived as `frozenset(get_args(LogKind)) - UNPARSED_KINDS` |
| **F2** | 41 `.md` files vs main's `6262e7d` format commit | 40 clear on rebase; the 2 that did not are fixed |

**Why the numbers had been believed.** Earlier sessions installed tooling with
bare `pip`, but every `just` recipe runs through `uv run` — so `just check` had
never executed end to end in this sandbox. `pyrefly` was simply absent (and its
gate scored that as a pass), and `pylint`'s **exit code** was never read because
the `10.00/10` score line looks conclusive. *A score is not an exit code, and an
absent tool is not a clean tool.*

**Correction to §11's coverage table.** `_cmd_probe` **81.6** and
`_cmd_selfcheck` **60.7** were measured with
`pytest tests/test_s10a_cli_coverage.py --cov=fa.cli` (this file alone);
every other row came from the full-suite run. Under the full suite — which is
what `scripts/check_cli_coverage_floor.py` actually reads — they are **97.4**
and **93.8**. Both readings reproduce exactly; only the full-suite column is
binding. Floors were **not** raised to match: they are deliberate minimums, and
S10b moves code between these functions.

**Kill-checks executed for this repair** (all bite; tree restored each time):
pyrefly absent → named failure with remediation · type error in `src/` → gate
names the file · `search-path` commented out → config test fails (the *old*
test passed on this) · `scripts` dropped from `project-includes` → fails ·
`elif` branch deleted from `_parse_events` → AST test fails · new `LogKind`
with no parser → count test fails · typo in `UNPARSED_KINDS` → stray-name test
fails.

That last one is the interesting case. Deriving `PARSED_KINDS` makes
`PARSED_KINDS | UNPARSED_KINDS == set(LogKind)` **true by construction** —
measured, not assumed: with the derivation in place a fictional `LogKind`
left the old union assertion green. It was deleted rather than reworded, and
replaced with cardinality assertions plus a check for the failure mode
derivation *introduces* (a typo'd name is silently subtracted away). Removing
duplication is correct here, but it silently converts a live check into a
vacuous one — **check for that every time a plan simplifies a structure.**
