# PLAN: S10 — CLI extraction decision + complexity-waiver retirement

Plan-ID: `PLAN-cli-trace-S10-cli-extraction-decision`
Status: **BLOCKED** — one blocking question (**Q40**, §7) must be answered
before S10.3. S10.0–S10.2 are READY and may proceed immediately.
Depth: **P2** — structural change to the CLI composition root, an
operator-visible surface, gated on a behaviour-invariance proof.
Revision: v1 · Changed-since-last: initial
Upstream context: parent
[`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md)
§Step S10; depends on **S2, S3, S7, S8, S9** — all COMPLETE.
Operator input 2026-07-31: *"there are tech debt in a form of sizable noqa
waiver in cli functions. they are extremely complex monoliths. can we
structure slice 10 with this refactor in mind? verify first."*

> **Authoring standard.** This plan follows the **attached** plan-authoring
> skill (v2: `GAP#`/`A#`/`T#`/`M#` taxonomy, deterministic-authority law,
> component/topology gates, degree-of-freedom closure, C4 mutation handoff).
> Every test named here MUST additionally be written under
> [`knowledge/skills/tests-writing/SKILL.md`](../../knowledge/skills/tests-writing/SKILL.md).

---

## Preflight log (§2 — run 2026-07-31, measured not assumed)

**Environment.** Sandbox reset; `pip install -e .` + tooling re-installed. The
16-file `scripts/`+`hooks/` diff is the known **file-mode** artifact (0 content
lines) and was restored. Base `5a3f4fd` (S9 COMPLETE), tree clean.

### 1. Roots and structure

| Fact | Measurement |
|---|---|
| `cli.py` size | **3,050 lines, 58 functions** |
| `build_parser` | **475 lines** — the largest function in the file |
| `_cmd_run` | **418 lines**, 78 top-level statements |
| Existing import-topology test | `tests/test_pyrefly_import_topology.py` **exists** |

### 2. The operator's claim — VERIFIED, with numbers

`max-complexity = 15` (`pyproject.toml:143`). Measured with `mccabe`:

**Two tools, one authority.** `ruff` is what CI runs; `mccabe` is a second
opinion that scores `try` +1 higher. **Gate numbers must come from ruff.**

Measured by stripping the `noqa` comments in a scratch copy and re-running
`ruff --select C901`, so these are the numbers **CI would report**:

| Function | ruff (**authority**) | mccabe | over 15 by | Waiver |
|---|---|---|---|---|
| `_cmd_run` | **39** | 51 | **2.6×** | `cli.py:1903` |
| `_cmd_stats` | **29** | 33 | 1.9× | `cli.py:2654` |
| `_discover_stats_sources` | **19** | 21 | 1.3× | `cli.py:2576` |
| `_cmd_selfcheck` | **19** | 24 | 1.3× | `cli.py:2359` |
| `_cmd_workflow` | **15** | 17 | passes ✅ | none needed |
| `_resolve_task` | **11** | 15 | passes ✅ | none needed |

All four waivers are **real and load-bearing** — remove any one and CI fails.
The debt is genuine; only my GAP5 sub-claim was wrong.

**The claim is correct and the codebase already agrees with it.** The ratchet's
own comment is binding intent, not a style opinion:

> *"Drift-stop, not a style opinion: existing offenders got explicit waivers;
> NEW functions above 15 fail CI. Agents must decompose instead of growing
> god-functions. **Do not raise this; lower it as waivers retire.**"*

So S10 is the natural home for *retiring* waivers — that is the documented exit
path. **But scope is repo-wide, not CLI-only: 19 `C901` waivers exist across
`src/fa`** (`coder_loop.py`, `loop.py`, `state.py`, `tools/*`, `stats.py`,
`skills/loader.py`, `sandbox/classifier.py`, …). Four are in `cli.py`.

### 3. The parent's stated premise — NOT supported by evidence

Parent Do #1 says *"identify real duplication and seam boundaries"*, and the
Do-not says *"do not split `cli.py` because it is large alone."*

```text
pylint R0801 (duplicate-code), min-similarity-lines=6, cli.py        -> 10.00/10, zero findings
pylint R0801, min-similarity-lines=5, cli.py + stats.py + cli_help.py -> 10.00/10, zero findings
```

**There is no duplication to extract.** The honest reading: the parent's
*trigger* for extraction is absent, and its Do-not forbids the remaining
motive (size). This is the decision S10 exists to make, and the evidence points
away from module extraction.

### 4. The constraint that governs everything — coverage

`cli.py` branch coverage over the five CLI suites: **59%** (1,226 statements,
476 uncovered).

Per-function statement coverage, measured (`--cov=fa.cli`, json report):

| Function | cov% | stmts | dark | lines | Refactor-safe today? |
|---|---|---|---|---|---|
| `build_parser` | **100** | 80 | 0 | 475 | ✅ pinned |
| `_run_stage` / `_run_linear` / `_run_initial_roles` | **100** | 41 | 0 | 129 | ✅ |
| `_run_repair` | 96 | 28 | 1 | 78 | ✅ |
| `_cmd_workflow` | 89 | 71 | 8 | 186 | ✅ |
| `_cmd_inner_loop_smoke` | 87 | 38 | 5 | 148 | ✅ |
| `_run_adaptive` | 79 | 48 | 10 | 138 | ⚠️ |
| `_discover_stats_sources` | 77 | 52 | 12 | 76 | ⚠️ |
| `_resolve_task` | 76 | 29 | 7 | 60 | ⚠️ |
| **`_cmd_run`** | **71** | **180** | **53** | 418 | ⚠️ **below the 80% bar** |
| `_cmd_stats` | 36 | 99 | 63 | 164 | ❌ |
| `_cmd_authoring_check` | 11 | 9 | 8 | 15 | ❌ dark |
| `_cmd_chunk` | 5 | 19 | 18 | 29 | ❌ dark |
| `_cmd_routing_check` | 5 | 19 | 18 | 34 | ❌ dark |
| `_cmd_egress_proxy` | 4 | 26 | 25 | 54 | ❌ dark |
| `_cmd_probe` | **2** | 61 | 60 | 100 | ❌ dark |
| `_cmd_selfcheck` | **1** | 87 | 86 | 113 | ❌ dark |

**Six commands are effectively dark, not two** — my earlier count was low
because I only looked at the functions carrying waivers.

**Operator directive (2026-07-31): reach ~80% coverage on every function S10
touches *before* refactoring it.** That inverts the plan's original ordering
and is the correct call — `_cmd_run` at **71%** would not have met its own
parity bar.

**`_cmd_selfcheck` and `_cmd_probe` have zero test references and are ~95%
uncovered.** Refactoring them is *unfalsifiable*: no parity test could fail, so
"behaviour preserved" would be an assertion, not a proof. This workstream has
already been burned four times by checks that cannot fail (S7.C3, S7.C4,
S7.C7, S9's F3) — extracting dark code is the same mistake with a bigger blast
radius.

### 5. Conflicts / invariants

- Parent §Do-not (**binding**): do not split because it is large; no
  framework/registry abstraction without a repeated consumer; do not change UX
  and topology in one patch.
- Parent Do #5: **add import-topology and C2 parity tests *before* deleting
  old functions.**
- `build_parser()` stays the public parser composition root (Do #3).
- Attached skill's **component gate** applies to any new module: state what
  evidence proves need, what breaks if omitted, why existing structure cannot
  serve.
- Deferred and untouched: `I-36`, `I-37`, `I-39`; and the cross-slice open
  questions `Q35b` / `Q38` (defined in the S9 plan §7, not re-opened here).

### 6. As-is liveness

| Signal | Liveness | Evidence |
|---|---|---|
| CLI behaviour per command | **L3** for `run`/`workflow`/`stats` | S7/S8/S9 C2 suites |
| CLI behaviour for `selfcheck`/`probe` | **L0** | zero test references |
| Import topology | **L2** | `test_pyrefly_import_topology.py` exists; does not constrain `cli.py` internals |
| Complexity ratchet | **L3 as a drift-stop** | `max-complexity=15` enforced for new code |

### 7. Unresolved → **Q40** (blocking S10.3)

---

## 0. Executive intent (§3)

**IDEA.** Answer the parent's question — *is CLI extraction warranted?* — with
measurement rather than taste, and convert the answer into the one change the
evidence does support: **retiring complexity waivers by decomposing inside
`cli.py`**, starting only with code that is provably pinned.

**PROJECT MEANING.** `cli.py` is the composition root every slice S2–S9 wired
behaviour into. It is the last place where a "tidy-up" can silently change an
operator-visible contract, and the first place a reviewer looks. S10 is where
the substrate's structural debt is either paid down safely or explicitly
deferred with a reason.

**GOALS**

- **G1** — produce a *recorded, evidence-backed decision* on module extraction
  (parent's actual ask), not a refactor justified by vibes.
- **G2** — retire the **`_cmd_run` C901 waiver** (51 → ≤15) with zero
  behaviour change, proven by parity tests and mutation.
- **G3** — make the complexity ratchet **self-lowering**: a deterministic gate
  that fails if the waiver count or the threshold regresses.
- **G4** — close the `selfcheck`/`probe` coverage hole **or** record it as an
  explicit, owned deferral — never refactor dark code.

**NON-GOALS** — §1.

**INTENT.** Code should ensure that *structural change cannot alter an
operator-visible contract undetected* — every extraction is fronted by a parity
oracle that fails when behaviour moves.

**MECHANISM SKETCH.** Measure → decide (G1) → pin `_cmd_run` with parity tests
→ extract pure helpers *within the module* → assert complexity dropped by a
deterministic gate → ratchet the waiver count down.

**PROOF SKETCH.** Root `_cmd_run` observes exit code + durable artifacts;
kill-check re-inlines a helper and the complexity gate fails, while parity
tests keep passing — proving the gate measures structure and the parity tests
measure behaviour, independently.

**SIZE.** M.

---

## 1. Non-goals & minimal-mechanism check (§5)

1. **No new modules under `src/fa/cli/`** unless Q40 resolves that way. The
   attached skill's *component gate* is not satisfiable on current evidence:
   duplication is zero, and "the file is large" is the parent's explicit
   Do-not.
2. **No command-registry / framework abstraction** — no repeated consumer.
3. **No refactor of `_cmd_selfcheck` or `_cmd_probe`** while they are dark.
   Coverage first, or defer.
4. **No UX change**: flags, help registry, exit codes, output streams and
   artifact paths are frozen (parent Do #4).
5. **No repo-wide waiver campaign.** 19 waivers exist; S10 retires **one**
   (`_cmd_run`) and installs the ratchet that forces the rest down over time.
6. **No `max-complexity` raise, ever** — the ratchet only moves down.
7. `I-36`/`I-37`/`I-39` untouched, as are `Q35b` and `Q38` (both carried from
   earlier slices; see the S9 plan §7).

**Minimal-mechanism check (P2 — required).** The maximal reading of "refactor
the monoliths" is a `src/fa/cli/` package with per-command modules. Rejected on
three independent grounds: zero measured duplication, the parent's explicit
Do-not, and 59% coverage meaning the parity net has holes exactly where the
biggest functions are. The minimal change that satisfies the operator's intent
is **in-module decomposition of the single best-pinned offender**, plus a gate
that makes the remaining debt visibly shrink.

---

## 2. Current → target, as a GAP ledger (§4, v2)

| GAP# | Verified current | Target | Owner |
|---|---|---|---|
| **GAP1** | Extraction question unanswered; parent lists it as a *decision* | Decision recorded with measurements + rationale | S10.1 / T1 |
| **GAP2** | `_cmd_run` complexity **51** vs threshold 15, waived | ≤ **15**, waiver **deleted** | S10.3 / T3, T4 |
| **GAP3** | Waiver count is unmanaged; nothing fails if it grows | Deterministic gate pins the count; may only decrease | S10.2 / T2 |
| **GAP4** | `_cmd_selfcheck` 98% dark, `_cmd_probe` 91% dark, 0 test refs | Smoke-level C2 coverage, **or** recorded deferral with owner | S10.4 / T5 |
| ~~GAP5~~ | ~~`_cmd_workflow` at 17 with no waiver~~ | **WITHDRAWN — my measurement error, CI is correct** | — |

> **GAP5 WITHDRAWN (2026-07-31), and the withdrawal matters more than the
> finding.** I reported that `_cmd_workflow` sits above the threshold with no
> waiver and that "the ratchet is leaking". **The ratchet is not leaking; my
> instrument disagreed with CI's instrument.**
>
> ```text
> ruff  --select C901  ->  _cmd_workflow = 15   (15 > 15 is FALSE -> passes)
> python -m mccabe     ->  _cmd_workflow = 17
> ```
>
> Root cause, isolated on a 5-line fixture: **`ruff` and `mccabe` score `try`
> statements differently — mccabe adds +1 per `try`, ruff does not.** Verified
> the delta equals the `try` count in every divergent function:
>
> | function | ruff | mccabe | Δ | `try` stmts |
> |---|---|---|---|---|
> | `_cmd_workflow` | 15 | 17 | +2 | **2** |
> | `_resolve_task` | 11 | 15 | +4 | **4** |
> | `_run_adaptive` | 14 | 14 | 0 | **0** |
>
> **Consequence for this plan:** `ruff` is the CI authority
> (`[tool.ruff.lint.mccabe] max-complexity = 15`), so **every complexity
> number in a gate or exit criterion must be ruff's**, never `mccabe`'s.
> `_cmd_run` is **51 by mccabe** but the number CI enforces is ruff's — S10.0
> must re-baseline all targets with `ruff --select C901` before any threshold
> is written into a test. Using a second tool's number would have produced a
> gate that disagrees with CI: the exact class of defect this workstream keeps
> finding.
>
> *Sixth instrument error in this workstream* (after S8.6's `trace` probe and
> S9's `[a-z_]+` regex). The rule is now explicit: **measure with the tool the
> gate uses.**

**TO-BE (machine-checkable)**

- `grep -c "noqa: C901" src/fa/cli.py` → **3** (was 4).
- `mccabe` on `_cmd_run` → **≤ 15**.
- New test asserts the repo-wide C901 waiver count is `<= 19` and *decreasing*.
- `just check` green; behaviour byte-identical on every parity oracle.

---

## 3. Contracts (§6, v2 fields)

### CT1 — behaviour invariance under extraction (invariant)

- **CT1:** For every extraction in S10, the command's **exit code, stdout
  bytes, stderr presence, durable artifacts (session DB rows, `flow_state`,
  `global_history` row) and artifact paths** are unchanged.
- **AUTHORITY:** the pre-extraction behaviour, captured by parity tests written
  **before** the edit (parent Do #5).
- **DETERMINISTIC MECHANISM:** C2 parity tests over the shipped `_cmd_run`;
  they are the gate, not review.
- **FAILURE SURFACE:** a failing named test identifying the changed field.
- **KILL-CHECK:** alter any extracted helper's behaviour → a parity test fails.

### CT2 — complexity ratchet (data/gate contract)

- **CT2:** `max-complexity` may only decrease; the count of `noqa: C901`
  waivers under `src/fa` may only decrease.
- **AUTHORITY:** `pyproject.toml` + the waiver census in the gate test.
- **DETERMINISTIC MECHANISM:** a test that recounts waivers and asserts
  `<= _WAIVER_BUDGET`, with the budget a literal that must be edited *down* in
  the same commit that removes a waiver.
- **FAILURE SURFACE:** test failure naming the new waiver's file:line.
- **KILL-CHECK:** add a `# noqa: C901` anywhere in `src/fa` → the gate fails.

### CT3 — parser composition root (signal contract)

- **PRODUCER:** `build_parser()` (`cli.py:362`).
- **CONSUMER:** `main()`, the help registry, and every C2 test.
- **Contract:** `build_parser()` remains the single composition root; the set
  of subcommands and each command's flag set is unchanged by S10.
- **KILL-CHECK:** remove a flag → the parser-parity test fails.

**Security contract (§6.5):** N/A — S10 moves no boundary. *(Stated, not
dressed up: the one security-adjacent finding in this area, I-36, is
operator-deferred.)*

---

## 4. Path & matrix (§7, v2)

### Paths

| P# | Trigger | Site | Covering S# |
|---|---|---|---|
| P1 | `fa run` happy path | `_cmd_run` | S10.3 (parity) |
| P2 | `fa run` config/chain error → exit 2 | `_cmd_run` prologue | S10.3 |
| P3 | `fa run --output-mode quiet` | `_cmd_run` epilogue | **covered L3** (S8.4) |
| P4 | `fa run` proxy mode | `_cmd_run` prologue | S10.3 |
| P5 | `fa workflow` (all modes) | `_cmd_workflow` | **covered L3** (S8) |
| P6 | `fa stats` | `_cmd_stats` | **covered L3** (S9) |
| P7 | `fa selfcheck` | `_cmd_selfcheck` | **DARK** → S10.4 / Q40 |
| P8 | `fa probe` | `_cmd_probe` | **DARK** → S10.4 / Q40 |

### Matrix

| M# | Dimension | Proves | Covering S# |
|---|---|---|---|
| M1 | pre- vs post-extraction | behaviour invariance | S10.3 |
| M2 | `--output-mode console` / `quiet` | the S8.4 contract survives | S10.3 |
| M3 | proxy on / off | prologue branch survives extraction | S10.3 |
| M-x | provider family | N/A — extraction is provider-agnostic | N/A |

---

## 5. Steps (§8)

> **Per-step protocol (operator-mandated).** Before editing: state
> source-verified behaviour, contract + GAP IDs, exact files allowed to change,
> stop on unresolved blockers. For each edit: idea / intent / current→target /
> mechanism / best practice / failure behaviour / DoD + negative proof / test
> class / kill-check target / **degree of freedom closed**. After each edit:
> targeted tests, static checks, `git diff` inspection, **report actual
> output**; never mark complete from "no exception". After the big chunk:
> targeted mutation.

### Step S10.0 — Re-verify the preflight measurements

Traces-to: all. **Files allowed to change: none.**

Do:

1. Re-run `mccabe --min 8` on `cli.py`; confirm `_cmd_run` = 51.
2. Re-run `pylint R0801` on `cli.py`; confirm **zero** duplication.
3. Re-run coverage over the five CLI suites; confirm ≈59% and that
   `_cmd_selfcheck`/`_cmd_probe` remain dark.
4. Re-count `noqa: C901` under `src/fa`; confirm **19**.

Exit criteria: all four reproduce, or the plan is amended before any edit.

---

### Step S10.1 — Record the extraction decision (GAP1, G1)

Traces-to: G1, GAP1. Depends-on: S10.0. **Files allowed to change:** this plan.

**This is the parent's actual deliverable.** Parent §Step S10 is titled
*"Decide whether CLI extraction is warranted"* — a decision step, not a
refactor step. The decision must be written with its evidence so a future
reader can re-open it on new evidence rather than re-litigating taste.

Do:

1. Record: duplication **zero**; parent Do-not forbids size-only splits;
   coverage 59% with the two largest untested commands dark.
2. Record the **recommendation: do not extract modules now**; decompose
   in-module instead, and revisit if duplication appears or coverage reaches a
   level where parity is provable for every command.
3. Leave the door open via **Q40** rather than closing it unilaterally.

Exit criteria: decision + evidence recorded; Q40 posed with options.

**T1 (verification):** documentation-only; the "test" is that §7 Q40 carries
measurements, not adjectives.

---

### Step S10.2 — Deterministic complexity ratchet (GAP3, GAP5, G3, CT2)

Traces-to: G3, GAP3, GAP5, CT2. Depends-on: S10.0.
**Files allowed to change:** `tests/test_s10_complexity_ratchet.py` (NEW).
**No production change.**

**Current source-verified behaviour.** `max-complexity = 15` stops *new*
offenders, but nothing prevents adding a `# noqa: C901` to bypass it, and
nothing notices that `_cmd_workflow` sits at 17 **with no waiver** (GAP5 —
measured this preflight). The ratchet's comment says *"lower it as waivers
retire"*, but no mechanism enforces the lowering.

Do:

1. Census every `noqa: C901` under `src/fa` by AST/line-scan; assert
   `count <= _C901_WAIVER_BUDGET` with the budget a literal set to **today's
   19**.
2. Assert every waived function is *actually* over the threshold — a waiver on
   a simple function is dead weight and should be deleted.
3. Assert `max-complexity` in `pyproject.toml` is `<= 15`, so the threshold can
   never be raised to make a failure disappear.
4. Record GAP5 in the test's docstring with the measured value.

Do-not:

- Do not fail on the *existing* 19 — a gate that red-lights on day one gets
  disabled. It pins and ratchets, it does not moralise.
- Do not add per-file exemptions.

**Idea now implemented:** the drift-stop becomes a *ratchet*. **Intent:** make
the debt's direction structurally guaranteed. **Mechanism:** a literal budget
that must be edited down in the same commit that removes a waiver.
**Best practice:** budget-with-a-literal beats a trend metric — it is
deterministic, reviewable in the diff, and impossible to satisfy accidentally.
**Failure behaviour:** test failure naming the offending file:line.

**Degree of freedom closed:** before, a contributor could silence C901 with a
comment and CI stayed green; after, the waiver count is a reviewed number.

Exit criteria:

- [ ] gate passes at 19; fails at 20
- [ ] gate fails if `max-complexity` is raised to 16
- [ ] GAP5 (`_cmd_workflow` = 17, unwaived) recorded

**Test class: C1** (source-topology gate). **Oracle:** the census count +
parsed `pyproject.toml` value. **Kill-check target:** add one `# noqa: C901`
→ gate fails. **Execute it.**

**Negative proof:** a census that silently matched zero files would pass. Assert
`count >= 15` as a liveness control — the scan must be finding the known debt.

---

### Step S10.3 — **BLOCKED on Q40.** Retire the `_cmd_run` waiver (GAP2, G2, CT1)

Traces-to: G2, GAP2, CT1. Depends-on: **Q40 answered**, S10.2.
**Files allowed to change:** `src/fa/cli.py`,
`tests/test_s10_cli_parity.py` (NEW).

**Current source-verified behaviour.** `_cmd_run` is **418 lines, complexity
51, 78 top-level statements**, waived at `cli.py:1903`. It is the
best-pinned large function in the file: **12 test references** and only ≈44
uncovered lines. `drive_session` is invoked at `:2235`; everything before
`output_bus = EventBus()` (`:2217`) is config → chain → proxy → session
resolution, and everything after is outcome handling and export.

Do (**parity first — parent Do #5**):

1. **Write `tests/test_s10_cli_parity.py` BEFORE touching `cli.py`.** Capture
   exit code, stdout bytes, stderr non-empty, DB row count, and the
   `global_history` row for: happy path (M1), quiet mode (M2), proxy mode
   (M3), and a config-error path (P2).
2. Run it against **unmodified** `cli.py` and record the output in the
   execution record. A parity suite that was never green pre-change proves
   nothing.
3. Extract **pure, side-effect-free** helpers only — candidates measured this
   preflight: secret-redactor construction, provider-chain assembly, proxy
   rewrite, and the outcome/export epilogue.
4. Re-measure complexity after each extraction; stop at ≤15.
5. **Delete the `# noqa: C901`** and lower `_C901_WAIVER_BUDGET` to 18 in the
   same commit.

Do-not:

- Do not move code to another module (that is Q40, not this step).
- Do not change any flag, exit code, stream, or artifact path.
- Do not extract anything whose behaviour the parity suite does not observe.
- Do not batch extraction with the ratchet edit — separate commits.

**Idea now implemented:** the largest waiver is retired by decomposition, not
by raising the limit. **Intent:** prove the ratchet's exit path works on the
hardest case so the remaining 18 have a template. **Mechanism:** extract pure
helpers; the orchestrator keeps its sequence. **Best practice:** parity oracle
before structural edit — the only way "no behaviour change" is falsifiable.
**Failure behaviour:** none introduced; extraction is behaviour-preserving by
construction and by test.

**Degree of freedom closed:** before, "refactor `_cmd_run`" could mean anything
and be justified by inspection; after, only changes that keep four parity
oracles byte-identical are admissible, and the complexity number is the
completion criterion rather than a reviewer's judgement.

Exit criteria:

- [ ] parity suite green **before** the edit (recorded)
- [ ] `mccabe` on `_cmd_run` ≤ **15**
- [ ] `grep -c "noqa: C901" src/fa/cli.py` → **3**
- [ ] budget literal lowered 19 → 18
- [ ] full suite green; `just check` green
- [ ] `git diff` shows **no** change to flags/exit codes/streams/paths

**Test class: C2** (CLI root). **Oracle:** exit code + stdout bytes + DB/FS
effects. **Kill-check target:** change an extracted helper's return value →
a named parity test fails. **C4/mutation handoff:** after green, run the
statement-deletion sweep over the new helpers; a surviving mutation blocks
"shipped".

**Negative proof:** "the suite is green after refactoring" is not proof — the
suite was green before. The proof is that the parity suite was **written and
run against the pre-change code**, and that re-inlining a helper leaves parity
green while the *complexity gate* fails. Two independent oracles, one for
behaviour and one for structure.

---

### Step S10.4 — Close or own the dark-command gap (GAP4, G4)

Traces-to: G4, GAP4. Depends-on: S10.0. Parallelizable-with: S10.2.
**Files allowed to change:** `tests/test_s10_cli_parity.py`, `knowledge/BACKLOG.md`.

**Current source-verified behaviour.** `_cmd_selfcheck` (113 lines, C=24) and
`_cmd_probe` (100 lines, C=14) have **zero test references** and are ~95%
uncovered. Both are operator-facing diagnostics.

Do:

1. Add a **smoke-level C2** for each: invoke through the shipped function with
   an isolated `$HOME`, assert the exit code and that it does not raise.
2. If a command cannot be smoke-tested without network or a live container,
   **do not fake it** — record a BACKLOG item with the specific blocker and
   the owner.
3. Explicitly record that these two are **excluded from any extraction** until
   covered.

Do-not: do not write a test that merely imports the function; that is the
`test_stats_global_history_projection_only` tautology S9 deleted.

**Test class: C2.** **Oracle:** exit code. **Negative proof:** assert a
*specific* exit code, not "did not raise" — the latter passes for a function
that returns immediately.

---

### Step S10.5 — Targeted mutation (C4 handoff)

Traces-to: G2, G3. Depends-on: S10.3.

Do:

1. Sweep spec `scripts/sweep_specs/s10_cli_extraction.json` — delete each
   extracted helper's guard; every mutation must be CAUGHT by the parity suite.
2. Confirm the `N passed` line before believing any kill percentage.
3. A surviving mutation **blocks** shipped status (attached skill §9).

---

## 6. Verification plan (§9, v2 `T#`)

| T# | Test | Class | Oracle | Kill-check target | Covers |
|---|---|---|---|---|---|
| **T1** | decision recorded with measurements | doc | §7 Q40 content | — | GAP1 |
| **T2** | `test_s10_c901_waiver_budget` | C1 | waiver census + `max-complexity` | add a `noqa: C901` | GAP3, GAP5 |
| **T3** | `test_s10_cmd_run_parity_*` (4 cells) | C2 | exit code + stdout bytes + DB/FS | change an extracted helper | GAP2, M1–M3 |
| **T4** | `test_s10_cmd_run_complexity_under_threshold` | C1 | `mccabe` value ≤ 15 | re-inline a helper | GAP2 |
| **T5** | `test_s10_selfcheck_smoke`, `test_s10_probe_smoke` | C2 | exit code | delete the command body | GAP4, P7, P8 |

**LIVE-PATH PROOF**

```text
root:        _cmd_run (src/fa/cli.py)
matrix:      M1 pre/post · M2 console|quiet · M3 proxy on|off
test:        tests/test_s10_cli_parity.py::test_s10_cmd_run_parity_happy_path
oracle:      exit code + stdout bytes + session DB rows + global_history row
kill-check:  change an extracted helper's behaviour -> named parity test fails
             re-inline a helper -> T4 fails while T3 stays green (two oracles)
producer:    _cmd_run and its extracted helpers
consumer:    main() -> SystemExit(func(args)); operator scripts
paths:       P1, P2, P4 by new tests; P3, P5, P6 already L3; P7, P8 -> S10.4
contract:    just check PASS required
pyramid:     A
```

**CI authority:** `just check` — `lock-check`, `dependency-contract-check`,
`lint` (ruff + deptry + `pylint src/fa`), `typecheck` (bare `python -m mypy`),
`authoring-check`, `contract-check`, `log-kind-check`, `no-mocked-dataclasses`,
`test` (`pytest --cov`, `fail_under = 80`).

---

## 7. Risks, rollback, open questions (§10)

### Risks

| RK# | Risk | Mitigation | Detected by |
|---|---|---|---|
| RK1 | Extraction silently changes an operator contract | Parity suite written **and run green before** the edit | T3 |
| RK2 | "Refactor" becomes a rewrite | Only pure, side-effect-free helpers; ≤15 is the stop condition | `git diff` review + T4 |
| RK3 | Ratchet gate red-lights on day one and gets disabled | Budget set to today's count, not to zero | T2 |
| RK4 | Extracting `_cmd_run`'s prologue moves an early-return and changes an exit code | P2 config-error cell is a required parity cell | T3 |
| RK5 | Scope creep into the other 18 waivers | §1 non-goal 5; budget lowers by exactly 1 | Review |
| RK6 | Dark commands get "tidied" opportunistically | §1 non-goal 3 + S10.4 records the exclusion | Review |

### Rollback

Every S10 change is behaviour-preserving and independently revertible:
`git revert` of the S10.3 commit restores `_cmd_run` verbatim; the ratchet test
and parity tests are additive. No schema, no migration, no flag change.

### Open questions

**Q40 — BLOCKING S10.3. Does S10 extract modules, decompose in-module, or
neither?**

Measured inputs: **zero** duplication; parent Do-not forbids size-only splits;
`cli.py` at 59% coverage with the two largest commands dark; `_cmd_run` at
complexity 51 against a threshold of 15 whose own comment says *"lower it as
waivers retire."*

- **(a) Extract to `src/fa/cli/` modules.** Satisfies the "monolith" instinct.
  **Rejected on evidence**: no duplication to remove, parent's explicit
  Do-not, and the attached skill's component gate cannot be met — moving code
  into new files reduces no verified coupling, it relocates it.
- **(b) In-module decomposition of `_cmd_run` only, plus the ratchet.**
  **Recommended.** Pays the operator's stated debt, keeps the parity net where
  it is strongest (12 test refs, 44 dark lines), respects every Do-not, and
  leaves a template for the remaining 18 waivers.
- **(c) Decide "not warranted", change nothing structural, ship only the
  ratchet + coverage.** Defensible and the most conservative reading of a
  *decision* step; leaves the 51-complexity function in place.

**This plan is written assuming (b).** §5 S10.3 encodes it. If the operator
picks (a), the component gate must be satisfied first and this plan returns to
DRAFT; if (c), S10.3 is dropped and S10.2/S10.4 stand alone.

**Q41 — NON-BLOCKING, default recorded.** Should the 18 remaining C901 waivers
get a scheduled retirement programme? **Default: no separate slice now** —
the S10.2 ratchet makes the direction structural, and each future slice
retires waivers in the code it already touches. Revisit if the budget has not
moved in three slices.

**Q42 — NON-BLOCKING, default recorded.** `_cmd_workflow` is at complexity 17
with **no** waiver (GAP5). **Default: record it in the ratchet test, do not
fix in S10** — fixing it is a second extraction and would violate the one-at-a-
time discipline S10.3 is demonstrating.

---

## 8. Research-note disposition (§11a)

| RN# | Item | Verdict | Why | Anchor |
|---|---|---|---|---|
| RN1 | Parent Do#1 "identify real duplication" | **Reject — premise absent** | pylint R0801 finds **zero** duplication in `cli.py`, and none across `cli.py`+`stats.py`+`cli_help.py` | §Preflight 3 |
| RN2 | Parent Do#2 "extract one command family at a time" | **Defer to Q40** | Conditional on extraction being warranted; evidence says it is not | Q40 |
| RN3 | Parent Do#3 "keep `build_parser()` as root" | **Accept as constraint** | Encoded as CT3 | CT3 |
| RN4 | Parent Do#4 "preserve flags/help/exit/streams/paths" | **Accept** | Becomes CT1, the parity contract | CT1 / T3 |
| RN5 | Parent Do#5 "topology + parity tests before deleting" | **Accept** | S10.3 Do#1–2 make parity-first mandatory | S10.3 |
| RN6 | Operator: "sizable noqa waivers, complex monoliths" | **Accept — verified** | `_cmd_run` 51, `_cmd_stats` 33, `_cmd_selfcheck` 24, `_discover_stats_sources` 21 vs threshold 15 | GAP2 / G2 |
| RN7 | Operator: "structure slice 10 with this refactor in mind" | **Accept in part** | Yes for `_cmd_run` + ratchet; **no** for dark commands and for module extraction | Q40 / §1 |
| RN8 | *(preflight)* `_cmd_workflow` at 17 with no waiver | **Accept as finding** | The ratchet is already leaking | GAP5 / Q42 |
| RN9 | *(preflight)* 19 C901 waivers repo-wide | **Rewrite scope** | Repo-scale, not CLI-scale; S10 retires one and installs the ratchet | §1 non-goal 5 |
| RN10 | *(preflight)* `cli.py` at 59% coverage | **Accept as constraint** | Governs *what may be refactored at all* | GAP4 |

---

## 9. Definition of Done (§11.3)

**STATE — before → after, and how to observe**

| | Before | After | Observed by |
|---|---|---|---|
| Extraction question | open | decided, with measurements | §7 Q40 |
| `_cmd_run` complexity | **51** (waived) | **≤15**, waiver deleted | T4 + `grep` |
| C901 waivers in `cli.py` | 4 | **3** | `grep -c` |
| Repo waiver budget | unmanaged | pinned literal, may only decrease | T2 |
| `max-complexity` | 15, raisable | 15, **gate forbids raising** | T2 |
| `selfcheck` / `probe` | 0 test refs, ~95% dark | smoke-covered **or** owned BACKLOG item | T5 |
| CLI behaviour | L3 for run/workflow/stats | **unchanged** — proven, not assumed | T3 |

**ARTIFACTS (A#)**

- **A1** `tests/test_s10_cli_parity.py` (NEW)
- **A2** `tests/test_s10_complexity_ratchet.py` (NEW)
- **A3** `scripts/sweep_specs/s10_cli_extraction.json` (NEW)
- **A4** `src/fa/cli.py` (modified — helpers extracted, one waiver deleted)
- **A5** this plan (decision record), `worklogs/HANDOFF.md`
- **A6** `knowledge/BACKLOG.md` (only if S10.4 defers)
- **No other file may change.**

**CONTRACTS:** CT1–CT3 each PLANNED → IMPLEMENTED → **VERIFIED**.

**S10 is DONE only when:**

- [ ] G1–G4 resolved; every GAP# closed or explicitly deferred with an owner.
- [ ] **Parity suite was green against pre-change code**, and that run is
      recorded in §11. Without it CT1 is unproven.
- [ ] Every test written under the tests-writing skill — class declared,
      ranked oracle, producer kill-check named, honest fixtures (`_run_args`,
      not `_make_run_args`), no unpaired C0.
- [ ] `just check` green — bare `mypy`, `pylint src/fa` 10.00/10, coverage ≥80.
- [ ] **Zero new `noqa` of any kind**; net C901 waivers **decreased by 1**.
- [ ] Mutation sweep over extracted helpers: **no survivors**, `N passed`
      confirmed.
- [ ] Non-goals respected — no new modules, no registry, no dark-code
      refactor, no UX change.
- [ ] All RN# dispositioned; Q40 answered; Q41/Q42 defaults in the handoff.

**Negative proof (plan-level).** This plan is invalid if G2 is claimed on "the
suite is green" — the suite was green before the refactor. CT1 requires the
parity suite to have run green **pre-change**, and requires two *independent*
oracles: re-inlining a helper must leave T3 green while T4 fails. Five checks
in this workstream have already been caught passing vacuously (S7.C3, S7.C4,
S7.C7, S9's F3, and S9.6's two sweep survivors). Assume the same failure mode
here until each kill-check is executed.

---

## 10. Anti-theater + READY gate (§11.2, §11.4)

### Anti-theater

- [x] Every referenced symbol verified in preflight (file:line + measurement)
- [x] Every G# maps to ≥1 GAP#, CT#, S#, T#, A# — G1→GAP1/S10.1/T1,
      G2→GAP2/CT1/S10.3/T3+T4/A1, G3→GAP3+GAP5/CT2/S10.2/T2/A2,
      G4→GAP4/S10.4/T5
- [x] Signal contracts two-sided (CT3 producer `build_parser`, consumer `main`)
- [x] Every kill-check targets the PRODUCER
- [x] Path inventory complete; P7/P8 flagged dark rather than silently skipped
- [x] Matrix rows each have a covering step or explicit N/A
- [x] Fixtures honest — `_run_args` mandated
- [x] No vague verbs without a mechanism
- [x] Assumptions labelled (Q40 assumption stated in §5 and §7)
- [x] Security N/A declared with reason
- [x] **Component gate applied** — and it *rejects* new modules on current
      evidence (§1.1, Q40a)
- [x] **Deterministic authority** — CT2 is a gate, not a judgement call
- [x] All IDs resolve — G1–G4, GAP1–GAP5, CT1–CT3, S10.0–S10.5, P1–P8, M1–M3,
      T1–T5, A1–A6, Q40–Q42, RN1–RN10, RK1–RK6

### READY gate

- [x] Preflight present and non-trivial (six independent measurements)
- [x] Depth P2 declared and matches scope
- [x] Intent, non-goals, current/target concrete
- [x] Contract subtypes present or explicitly N/A
- [x] Path + matrix gates satisfied
- [x] Every step file:symbol specific with exit criteria
- [x] Verification plan + LIVE-PATH PROOF present
- [x] Anti-theater checklist holds
- [x] Research notes dispositioned (RN1–RN10)
- [ ] **BLOCKING question set EMPTY — FAILS: Q40 is open**
- [x] All IDs resolve

**→ Status: BLOCKED** (not DRAFT — the plan is complete; it awaits one
decision). **S10.0, S10.1, S10.2 and S10.4 may proceed immediately.**
**S10.3 is gated on Q40.** Answering Q40 with **(b)** flips this plan to READY
with no other edit.
