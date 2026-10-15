# `slice_verification` — requirements & design (draft for review, 2026-10-07)

Operator decision: non-vacuity is proven by **executing a declared kill-check**, not by asking
whether a test is new. This document restores the mental model, gathers the requirements with
their sources, and proposes a design. **Status update (2026-10-08; E193–E194):** SLICE5
STEP1–STEP6 are implemented and verified; Q53(c) requires every functional contract's kill
check to run every slice `TESTS:` path, with accepted attribution risk and O(contracts × paths)
cost, and Q54(b) uses the narrow `src/` + `scripts/` overlay with tests outside and exact
root-specific provenance. The real CT83 `verify_slice` composition returns `PROVEN`. SLICE6's
C1 `run_workflow` → `_cmd_run` → `drive_session` test passes with only `ProviderChain.request`
mocked; its nine declared kill-checks all return `PROVEN`, and an enforce-mode verifier failure
still reaches eval but cannot produce terminal DONE. Q55/Q56 replace the prior synthetic-report
routing proposal with always-eval-then-reconcile. Focused I02 slice paths, Ruff, full Pyrefly,
and targeted SLICE6 Mypy pass. Full I02 closure remains open: the latest full pytest run hit E174's
`WindowsPath` reporter INTERNALERROR without a final summary, full-repo Mypy has nine diagnostics
in five files outside SLICE6, the live-host e2e rows are planned, and operator-owned progress
ticks remain untouched. The note remains the design input; plan CT68/69/85/86 and resolved Q49
supersede its original per-command baseline sketch.

**Current scope/classification, 2026-10-15 (E200–E201):** historical results above are not new
proof. Retained I02 owns explicit admission/local composition and amended CT66 error classification;
foundation I03 owns nested/runtime and final host acceptance. Full-suite disposition remains open.
A failing exit alone is not mutation evidence; §3.5 below requires an executed failure report.
No extra clean-control baseline or per-contract nodeid policy is adopted.

---

## 0. The mental model, restored

The project exists to fix one failure: **a feature is reported done while nothing behind it
runs.** The operator's own account of the origin (E118) is that features once shipped to
production with dead code behind them, presented as working.

The chain the harness is building:

```
   planner writes a plan           I01 parses it            I02 proves it
   ───────────────────            ──────────────           ─────────────
   ## SLICE4: ...                 extract_plan_ids()        run the commands
   CONTRACTS: CT40 …     ───►     .slice_records    ───►    exit 0 = fact
   TESTS: tests/x.py              commands_for()            apply the kill-check
   ```verify                      tests_for()               test must die
   pytest tests/x.py              section()                 ↓
   ```                                                      PROVEN / VACUOUS / …
```

Three questions, three different answers, and the whole design rests on keeping them apart:

| Question | Who answers | Why |
| --- | --- | --- |
| *Did the slice's commands pass?* | **a command's exit code** | a fact; never ask a model |
| *Is the test bound to the production code?* | **the kill-check** | a fact; this module |
| *Is this a good implementation?* | **the judge (actual L2-eval successor)** | genuinely a judgement |

`SIMPLIFICATION-the-elegant-path.md` is the note that set this up: every hard question of
the preceding weeks was downstream of asking a model something that had a factual answer.

## 1. A contradiction inside the handoff, and why (d) is the compliant choice

I flagged a worry before designing and it resolved in favour of the operator's decision.

- Handoff **§5** says: *"No mutation/failure-injection proof in the core (that is the **I06
  verifier-co-evolution** story)."*
- Handoff **§6.4** says: *"Non-vacuity = **one scoped mutation run per slice, as a gate**,
  with appeal"* — and cites **E63, an operator decision**.

These contradict each other in the same document. Two facts break the tie:

1. **There is no verifier-co-evolution increment.** I06 in the roadmap is *"Telemetry &
   distillation"*. §5 defers mutation to an increment that does not exist, i.e. to never.
2. **E63 is an operator decision**; §5's bullet carries no decision id.

So mutation-as-gate was already sanctioned. ⚠️ **But (d) is not the same thing as §6.4**, and
collapsing them would be a scope error:

| | §6.4 (E63) | (d) kill-check (this module) |
| --- | --- | --- |
| Mutants | **generated** by mutmut over changed lines | **one declared** per contract |
| Cost | minutes per slice | one extra test run per contract |
| Authored by | the tool | the **planner**, in the plan |
| Failure meaning | "some mutant survived somewhere" | "**this** producer is not bound to **this** test" |

They are complementary: (d) is the cheap per-contract gate; §6.4 is a broader adequacy sweep.
**Recommendation: build (d) in I02; keep §6.4 as a later phase.** (d) is strictly more
aligned with SIMPLIFICATION's minimality warning, and it is the one that answers the
operator's original failure mode.

## 2. Requirements, each traced to its source

**Functional**

| # | Requirement | Source |
| --- | --- | --- |
| R1 | Commands come from the **plan**, never from model output | S6 Do:1 |
| R2 | Run each of the slice's commands; record the **real integer exit code** | S6; SIMPLIFICATION §4 |
| R3 | For each `FUNCTIONAL` contract, apply its declared kill-check and require the test to **fail** | operator decision; `feature-planning/SKILL.md:332` |
| R4 | A kill-check whose **target does not exist** blocks — the producer was never written | `tests-writing/SKILL.md:68` ("vacuous kill-check = theater") |
| R5 | Three-or-more-state result; **ERROR is never PASS** | handoff §1 (`_git_output` collapses errors — the anti-pattern) |
| R6 | No commands ⇒ `skipped: true`, advisory, do **not** block | S6 Do:5 (G8); SIMPLIFICATION §4.1 (legacy plans) |
| R7 | Always run eval after a successful coder stage, then reconcile the actual eval route with verifier facts. In enforce mode, a blocking determinate result overrides only eval `complete` to `return_to_coder`; an indeterminate result overrides only eval `complete` to `blocked`; preserve every eval non-complete route. Keep the existing bounded repair budget. Never synthesize or replace the model's `EvalReport`. | **Q55/Q56, operator-selected 2026-10-08; Q10(a)'s repair cap retained, synthetic-report mechanism superseded** |
| R8 | Existing test GREEN→RED ⇒ **REGRESSION**, blocks | `verify-block-design.md` truth table |

**Non-functional**

| # | Requirement | Source |
| --- | --- | --- |
| N1 | Per-command wall-clock timeout **and** a run-deadline check between commands; a hang is ERROR | S6 Do:3 |
| N2 | Scrubbed env + venv-PATH prepend, reusing the **policy pieces only** from `run_bash.py:233-250`; **never** `_run_subprocess_fallback` | S6 Do:2 (F-5) |
| N3 | Baselines scoped to affected paths, not the whole suite | §6.2 (E66) |
| N4 | The coder must not be able to write where verification runs | §6.7 |
| N5 | Pure-parsing `plan_ids.py` stays pure; a subprocess runner lives elsewhere | schema §7 contract |

**Out of scope — do not build** (§5, and SIMPLIFICATION's warning)

- No DSL for verify blocks. No fence-depth parsing. No `VERIFIED` status from I02 alone.
- No findings format, top-K ranker, shadow phase or graduation rule (E63 rejected all four).
- No generated-mutant sweep in this module.

## 3. Proposed design

### 3.1 Module

`src/fa/inner_loop/slice_verification.py`.

Two notes. The operator wrote `slice-verification.py`; a hyphen is not importable in Python,
so the file must be `slice_verification.py`. S6 called it `verification.py`; the longer name
is better because the unit of verification *is the slice*, and a bare `verification` in a
codebase this size invites unrelated things to accrete in it.

### 3.2 The verdict lattice

The single most important design choice, because it is what callers branch on:

```python
class SliceVerdict(StrEnum):
    PROVEN          = "proven"           # commands green AND every kill-check killed its test
    VACUOUS         = "vacuous"          # commands green BUT a kill-check SURVIVED
    PRODUCER_ABSENT = "producer_absent"  # a kill-check target does not exist in the tree
    FAILING         = "failing"          # a command exited non-zero
    REGRESSION      = "regression"       # an existing test went GREEN -> RED
    ERROR           = "error"            # could not determine: timeout, worktree failure, tooling
    SKIPPED         = "skipped"          # no verify block (legacy plan) -> advisory only
```

**Why `PRODUCER_ABSENT` is separate from `VACUOUS`.** They have different causes and
different repairs, and merging them would discard the signal this project was created for:

- `VACUOUS` — the producer exists, the test passes, but removing the producer does **not**
  break the test. The *test* is wrong. Repair: strengthen the test.
- `PRODUCER_ABSENT` — the declared producer is not in the tree at all. The *feature* is
  wrong. Repair: wire it. **This is the "dead code shipped as a working feature" detector**,
  stated directly rather than inferred.

### 3.3 The kill operators — a closed set of two

The directive must be machine-applicable, which rules out prose. Deliberately only two
operators, and the set is closed until evidence demands a third:

```
kill: neutralise  <file>::<symbol>
kill: remove-call <file>::<enclosing_symbol> -> <callee>
```

- **`neutralise`** — replace the body of `<symbol>` with `return None`. Use when the contract
  is "this function computes X".
- **`remove-call`** — delete statements inside `<enclosing_symbol>` that call `<callee>`. Use
  when the contract is "X is actually wired into the loop". This is the SD-C producer
  kill-check, and it is the one that matters most.

**Why symbols and not line numbers.** A line range is the obvious encoding and it is wrong:
the coder edits the file during the slice, every line below the edit shifts, and the
kill-check then mutates something unrelated — silently, because mutating the wrong line still
produces *a* test result. A symbol path survives edits. This is the same class of bug as the
`HEAD`-drift problem that killed option (c).

**Mechanism: AST, not text.**

```python
class _Neutralise(ast.NodeTransformer):
    def __init__(self, symbol: str) -> None:
        self.symbol, self.hits = symbol, 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name == self.symbol:
            self.hits += 1
            node.body = [ast.Return(value=ast.Constant(value=None))]
        return node
```

then `ast.unparse(tree)`. `ast.unparse` discards comments and formatting — acceptable and in
fact desirable here, because the mutated file exists only inside a throwaway worktree and is
never committed, and a formatting-blind transform cannot accidentally be mistaken for a real
edit. **`self.hits` is load-bearing**: `hits == 0` is `PRODUCER_ABSENT`, and `hits > 1` is an
ambiguous target that must ERROR rather than guess.

### 3.4 Isolation: a throwaway git worktree (ADR-15)

A kill-check modifies production code. It must never touch the operator's tree — that is the
one objection that could sink this design, and the repo already solved it.

```bash
git worktree add --detach "$SCRATCH" HEAD
git diff HEAD            | git -C "$SCRATCH" apply          # the coder's tracked edits
git ls-files --others --exclude-standard | tar -T - -c | tar -C "$SCRATCH" -x   # NEW files
# ... apply the mutation, run the contract's test ...
git worktree remove --force "$SCRATCH"
```

⚠️ **The untracked-file trap, called out because it is the same trap as option (c).** The
planner-authored test is usually a **new, untracked** file. `git diff HEAD` does not contain
it. A worktree built from `HEAD` + `git diff HEAD` would therefore run the kill-check against
a tree where the new test does not exist, and the phase would report a confusing error — or
worse, silently skip. Untracked files must be copied explicitly.

This isolation also satisfies **N4** for free: the coder never has a handle on the scratch
worktree, so it cannot write where verification runs.

### 3.5 Phases

```
0  PRE-CHECK   I01 precheck()                     static, already shipped
1  BASELINE    run the slice's existing TESTS: paths at T0; record {pytest nodeid -> GREEN|RED}; an absent row is unknown, never RED   (Q49 / CT68-69)
   ── coder works ──
2  PASS-AFTER  run the slice's commands           any non-zero  -> FAILING
3  REGRESSION  compare against baseline           GREEN -> RED  -> REGRESSION
4  KILL-CHECK  per FUNCTIONAL contract, in a throwaway source overlay:
                 a. target missing       -> PRODUCER_ABSENT
                 b. mutate, run every slice TESTS: path (Q53(c))
                 c. executed tests all pass, valid current report -> VACUOUS
                 d. executed test failure + valid current report + no infra error -> PROVEN
                 e. collection/setup/runner/timeout/error, missing/stale/invalid report,
                    zero executed/all-skipped -> ERROR, never PROVEN
5  VERDICT     all contracts proven and no regression -> PROVEN
```

**Q49 correction (2026-10-08):** the baseline is per pytest nodeid, not per command or file;
both T0 and “now” are harness-issued JUnitXML runs with the explicit `fa_pytest_nodeid`
property from `fa.inner_loop.junit_nodeid_plugin` (stock XML omits `Item.nodeid`, E180). Capture
is once at T0 (CT85/CT86).
**Q52 ruling:** the command exit remains authoritative (`ERROR > FAILING > REGRESSION`). A
nodeid regression is returned only when verify commands pass; red-to-red is not itself a
regression and does not suppress an independent non-zero command result.

**Q53(c) ruling (2026-10-08):** Phase 4 runs every path in the slice's `TESTS:` list for
each `FUNCTIONAL` contract, never the repository-wide suite. Cost is O(functional contracts ×
slice test paths); no contract-to-test attribution is claimed. A failing unrelated test can
make a kill-check appear `PROVEN`; the operator explicitly accepted that weaker attribution.
This caveat applies to genuine executed test failures, not collection/setup/runner/timeout errors
or false bool-map rows. Reuse one detailed JUnit parser with baseline-compatible projection;
runner status, individual outcomes and counters must agree. Fresh per-invocation report identity
is retained I02; independently supervised job/revision binding is I03 integration.
The baseline and current nodeid capture remain slice-scoped and harness-issued.

**Q54(b) ruling (2026-10-08):** CT60–CT63 allow two separately-contained overlay roots: required
`src/` and optional `scripts/`. `tests/` remains outside, and mutmut's global `source_paths` is
unchanged. For `scripts/`, `PYTHONPATH` alone is insufficient because pytest may import the
workspace-root `scripts` package first. The scripts-target environment loads a bootstrap from the
overlaid `src/` before test collection; the probe and bootstrap both require the exact target
module to resolve under `<overlay>/scripts`. Any mismatch is `ERROR`, never `PROVEN`. This keeps
the CT83 developer checker out of the runtime package while constraining mutation authority.

### 3.6 Worked example

A slice that wires the gate into the controller:

```markdown
## SLICE2: Wire the gate into the controller
CONTRACTS:
  CT51 [FUNCTIONAL]: after a coder stage, the harness runs that slice's verify commands.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> run_slice_verification
TESTS: tests/test_slice_verification_wiring.py   (NEW — author it)
```verify
uv run pytest tests/test_slice_verification_wiring.py -q
```
```

What the harness does, and what each outcome means:

| Situation | Phase 4 result | Verdict | Why it is right |
| --- | --- | --- | --- |
| Coder wired the call; test boots `drive_session` and asserts commands ran | call removed ⇒ test **fails** | **PROVEN** | the test is bound to the wiring |
| Coder wrote `run_slice_verification` but never called it from `_run_stage` | target not found ⇒ `hits == 0` | **PRODUCER_ABSENT** | the exact failure this project exists to catch |
| Coder wired it, but the test only calls `run_slice_verification` directly | call removed ⇒ test **still passes** | **VACUOUS** | the test proves the function works, not that anything uses it |

The third row is worth dwelling on: it is a test that is green, honest-looking, and proves
nothing about the product. Fail-before/pass-after would have **passed** it — the file was new
and it did go red→green. The kill-check catches it. That is the whole argument for (d).

## 4. Forks that need your decision

### F1 — where does `kill:` live in the grammar? ✅ **RESOLVED 2026-10-07 — and my first answer was wrong**

The operator asked for one more check before accepting (a). It failed, and the failure was
worth finding. **Placement is unchanged — indented under its contract — but the *reader* must
change.**

**What broke.** (a) as first written said "I02 extracts it from the contract **body**". But
`_section_contracts` joins continuation lines with **single spaces**, so the body is one flat
string and the line boundary is gone. Measured over six cases:

| Case | Result under (a) |
| --- | --- |
| directive is the last line | extracts correctly |
| directive followed by trailing prose | **NO MATCH — directive silently lost** |
| two directives on one contract | silently takes the **last**, ignores the first |
| typo'd keyword / missing `::` | NO MATCH, indistinguishable from "none declared" |

Four of six degrade to "no kill-check found", and "not found" is indistinguishable from "the
planner declared none" — a **silently disabled gate**, which is the precise failure this
project exists to prevent. Anchoring the regex to end-of-string is what makes the second row
fail, and un-anchoring it is worse: with the line boundary gone, `\S+` runs on into the prose.

**The fix: read `section()`, not the contract body.** I01 already exposes the slice's **raw
text**, newlines intact. Parsing the directive there keeps line structure, so per-contract
attribution is exact and trailing prose is harmless. Verified on the same corpus:

```
CT1 [FUNCTIONAL]  -> [('remove-call', 'src/a.py', 'f', 'g')]    # trailing prose present
CT2 [FUNCTIONAL]  -> [('neutralise',  'src/b.py', 'h', None)]
CT3 [PRESERVATION]-> None                                        # correctly none
```

**Plus a fail-loud validator, because placement alone is not safety.** Two patterns: a *soft*
one (`^\s*kill\s*:`) meaning "the planner intended to declare", and the *strict* one meaning
"well-formed". Comparing them converts every silent case into a loud diagnostic:

```
CT3  line 9  kill-directive-malformed     # soft matched, strict did not
CT2  line 0  kill-directive-missing       # FUNCTIONAL with no directive
CT4  line 0  kill-directive-ambiguous     # two directives on one contract
CT5  line 0  kill-directive-missing
```

A typo in the keyword itself (`kil:`) escapes the soft pattern and lands as
`kill-directive-missing` — still loud, still blocking, but the message is imprecise. A
near-miss pattern should catch it, matching this project's existing `heading-near-miss`
(CT26) and `step-near-miss` (CT37) family. Specified as **CT51** in the plan.

**Why not (b) a `KILLS:` block.** Measured: an unknown `KILLS:` block passes the shipped
pre-check cleanly (`ok=True`, zero diagnostics), so (b) would *also* need no I01 change. It is
rejected anyway, on the project's own evidence: two parallel lists drift apart, which is
exactly what the id table did. Colocation under the contract is what keeps a kill-check and
the claim it proves from separating.

**Net:** the directive sits under its contract, the reader is `section()` not the contract
body, validation is loud and runs **pre-coder**, and **I01 is still not reopened.**


### F2 — is `remove-call` + `neutralise` enough to start?

My recommendation is yes, and that the set stays closed until a real slice cannot be
expressed. Every extra operator is a step toward the DSL §5 forbids.

### F3 — what happens on `VACUOUS`: block, or block-with-appeal?

E63 granted an appeal for *generated* mutants (`GUESS→decided:` in the ledger). A **declared**
kill-check is different: the planner wrote it themselves, so "I dismiss my own kill-check" is
much weaker. **Recommendation: `VACUOUS` blocks with no appeal; `PRODUCER_ABSENT` blocks with
no appeal.** Keep the appeal for §6.4's generated sweep, where false positives are real.

### F4 — does the kill-check run on `CONSTRAINT` and `PRESERVATION` contracts too?

**Recommendation: no, `FUNCTIONAL` only.** A `PRESERVATION` contract's test is an existing
test asserting unchanged behaviour; there is no new producer to remove. A `CONSTRAINT` is
"must not violate X" — its kill-check would have to *introduce* a violation, which is a
different and much larger mechanism. Starting with `FUNCTIONAL` keeps the module small.

---

## 4b. Both load-bearing mechanisms were executed, not asserted

The two claims this design rests on were run against the shipped parser and stdlib before
being recommended.

**F1(a) — does a `kill:` continuation survive I01's parser untouched?** Fed the §3.6 example
slice to the shipped `extract_plan_ids` / `precheck`:

```
CT51 [FUNCTIONAL] -> "after a coder stage, the harness runs that slice's verify commands.
                      kill: remove-call src/fa/…/workflow_controller.py::_run_stage -> run_slice_verification"
CT52 [PRESERVATION] -> 'existing callers keep working.'
commands   : ('uv run pytest tests/test_slice_verification_wiring.py -q',)
test_paths : ('tests/test_slice_verification_wiring.py',)
strict regex extracts -> ('remove-call', 'src/fa/.../workflow_controller.py',
                          '_run_stage', 'run_slice_verification')
precheck ok: True | diagnostics: []
```

So the directive rides along, all four fields extract cleanly, `commands`/`test_paths` are
unaffected, and the pre-check stays clean with **zero** diagnostics. **I01 needs no change.**

**§3.3 — does the AST `remove-call` operator work, and does it distinguish the two blocking
verdicts?** Against a miniature `_run_stage`:

```
hits = 1   ->  the call statement is gone from the unparsed output, rest of file intact
hits = 0   ->  PRODUCER_ABSENT, correctly distinguished from VACUOUS
```

`hits` is what separates "the test is weak" from "the feature was never wired" — the
distinction §3.2 argues for, now demonstrated rather than claimed.

## 5. What I am NOT proposing

To be explicit, since the project's failure mode is scope growth: no mutant generation, no
ranking, no flake detection, no retry policy inside this module, no new sandbox gate (S6's
Do-not: a stricter gate denied 8/10 real verifier commands), no parallelism, and no reuse of
`_run_subprocess_fallback`.

## 6. CT66 implementation evidence (2026-10-15)

**Scope:** E204 completes amended I02 SLICE5 STEP7, not SLICE6 or I03. Pre-edit base
`ea77299b65346f70c466eac096160f750de2b6f3` classified any kill command `FAIL` as PROVEN.
No report was required. No blocking CT66 policy question remained: Q53(c) continues to allow
slice-level attribution, including a genuine unrelated failure. Q59/Q60/Q63 stay unresolved
for their affected work; this change neither ratifies them nor adopts a clean-control baseline gate.

### Mechanism and failure contract

- `_run_kill_check` still applies the declared mutation, creates the existing narrow overlay,
  and requires the provenance probe before running tests. It then allocates a private temporary
  report directory and fresh UUID run ID. Mandatory plugin/JUnit arguments are appended by the
  harness, not supplied by the plan. The run ID is computed into the scrubbed child environment.
- The explicitly loaded `pytest_itemcollected` plugin retains authoritative nodeids and adds
  `fa_pytest_run_id` when `FA_VERIFY_JUNIT_RUN_ID` is set. Each testcase must carry exactly one
  matching run ID. A previous report copied to a new report path is rejected. The report is
  parsed before temporary-directory cleanup; tests verify cleanup on success and rejection.
- `_parse_junit_report` is the single detailed parser. It distinguishes pass/failure/skip,
  rejects testcase errors, duplicates, DTD/entity declarations (including UTF-16/32 input),
  malformed XML/unknown encodings, invalid suite structure and contradictory counters. Required
  pytest suite counters and any supplied aggregate counters must agree. Decimal comparison
  avoids oversized-counter integer conversion exceptions while accepting leading zeros.
- `_parse_nodeid_report` projects the same report into the old baseline map: passed=True,
  failed/skipped=False, unusable=None. A valid zero-test baseline still yields `{}`; the same
  zero-execution report is not evidence of a successful kill.
- `_kill_check_result` requires at least one executed failure and pytest exit 1/FAIL for PROVEN.
  Valid executed all-pass requires exit 0/PASS and yields VACUOUS. Missing/stale/malformed/error
  reports, zero/all-skipped, timeouts and exit/report disagreements yield ERROR. Original
  scripts-import provenance diagnostics and directive metadata remain intact.
- This is local correlation, not authentication against hostile test code. Independently
  supervised job/revision binding remains I03 work. No retries, second verifier, new test mapping,
  new dependency, global mutation-scope change, or production fault-injection switch was added.

### Environment and actual checks

Python 3.11 was not used as a substitute. The normal uv standalone download failed at its
non-allowlisted GitHub release-asset redirect. Certificate-verified codeload source builds supplied
CPython **3.13.16** and OpenSSL **3.0.18**; SQLite **3.40.1**, zlib **1.2.13** and ctypes imported
successfully. `uv 0.13.1 sync --frozen --extra dev --python <built-python3.13>` installed all 76
locked project/dev packages. No TLS-verification bypass or dependency-file edit. Build products,
venv, scratch mutation copies and raw logs remain outside tracked files.

Executed in this checkout (uv available on PATH):

```text
Before edit:
uv run --frozen pytest tests/test_verify_slice.py tests/test_slice_verification_runner.py tests/test_mutation_overlay.py -q
131 passed in 8.33s

Final normal suite:
uv run --frozen pytest tests/test_verify_slice.py tests/test_slice_verification_runner.py tests/test_mutation_overlay.py -q
195 passed in 28.30s

Exact STEP7 exit command:
uv run pytest tests/test_verify_slice.py tests/test_slice_verification_runner.py -q
151 passed in 22.76s

ruff check <both changed production modules and both changed test files>
All checks passed!
mypy <both changed production modules> tests/test_verify_slice.py
Success: no issues found in 3 source files
pylint <both changed production modules>
Your code has been rated at 10.00/10
```

The four-file mypy invocation also exposed two **pre-existing** overlay-test errors: accessing
unexported module `shutil`, and an already-narrowed enum identity comparison. Running mypy on
`git show HEAD:tests/test_mutation_overlay.py` with the same two explicit production modules
reproduced exactly those errors. No unrelated repairs or weakened assertions.

Whole-file formatter check still reports pre-existing hunks (production verifier 5, verifier
suite 1, overlay suite 1; plugin 0). A `SequenceMatcher`/Counter comparison of original-versus-
formatted and current-versus-formatted text proved these hunk contents identical: **no new
format violations**. Only new test regions were formatted. This is not a claim that the whole
repository passes formatter/mypy or that the full repository test suite ran.

### Exact producer kill and targeted mutation evidence

The actual production operator ran:

```python
from pathlib import Path
from fa.inner_loop.slice_verification import (
    KillDirective, KillOperator, SliceVerdict, apply_kill, _run_kill_check,
)
root = Path.cwd()
d = KillDirective(operator=KillOperator.REMOVE_CALL,
    path="src/fa/inner_loop/slice_verification.py", symbol="verify_slice",
    callee="_run_kill_check", line=1)
a = apply_kill((root / d.path).read_text(), d)
assert (a.targets, a.edits) == (1, 1)
c = _run_kill_check(d, (
    "tests/test_verify_slice.py::test_verify_slice_composes_a_proven_kill_into_the_frozen_slice_result",
), root)
assert c.verdict is SliceVerdict.PROVEN, c
```

Actual output: `CT66 producer kill: targets=1, edits=1, verdict=proven, detail=''`.
This executes the real overlay, probe, subprocess pytest and fresh bound report, not a mocked
return or source-only assertion. It is C0 real-I/O, not a workflow-composition C1 claim.

**mutmut 3.6.0:** an excluded scratch copy used `source_paths` containing only
`src/fa/inner_loop/slice_verification.py`, `also_copy = ["src/fa", "scripts"]`, and explicit
selection of the three suites above. `pytest_add_cli_args` was `-x -q -k
'not test_the_overlay_leaves_the_real_checkout_untouched'`: only that unrelated real-Git
checkout-invariance case is excluded from the non-Git scratch run, never from the normal suite.
The child pytest plugin stays uninstrumented because mutmut's trampoline cannot initialize from
those throwaway child working directories. Two initial stats-collection failures established
these setup requirements; neither was counted as mutation evidence. The eventual clean and
forced-failure controls passed before mutations ran.

```text
mutmut run --max-children 4 \
  'fa.inner_loop.slice_verification.x__kill_check_result*' \
  'fa.inner_loop.slice_verification.x__junit_testcase*' \
  'fa.inner_loop.slice_verification.x__junit_counter_error*' \
  'fa.inner_loop.slice_verification.x__parse_junit_report*'
```

The first sweep executed all **223 selected mutants: 183 killed, 40 survived**. Tests were then
strengthened without removing old assertions; fresh coverage was collected and all **40 exact
survivor IDs** explicitly rerun: **38 killed, 2 survived**. These are two measured runs, not a
claim that all 223 ran again on the final test snapshot. Source bytes were verified identical
between the checkout and both scratch runs: SHA256
`96021dbf5c05ad9fd2ec7e200d70b651dc5170f057e97e1bd163ecb925d9e2c5`.

**KILLED VIA EXACT ASSERTIONS (221 across those runs):**
- `fa.inner_loop.slice_verification.x__junit_testcase__mutmut_1..32` (32): nodeids,
  invocation binding, outcomes and independently detectable testcase errors.
- `fa.inner_loop.slice_verification.x__junit_counter_error__mutmut_1..74`, except `_70`
  (73): malformed/contradictory counters, later-suite validation, partial aggregate counters,
  and valid leading-zero/optional-section controls.
- `fa.inner_loop.slice_verification.x__parse_junit_report__mutmut_1..45` (45): missing,
  malformed, wrong-root and encoding/declaration negatives, duplicate rows and valid roots.
- `fa.inner_loop.slice_verification.x__kill_check_result__mutmut_1..71` (71): PROVEN vs
  VACUOUS vs ERROR, preserved directives, bounded measured duration and actionable diagnostics.

**ACCEPTED AS EQUIVALENT / UNOBSERVABLE (2; no source suppression):**
- `fa.inner_loop.slice_verification.x__junit_testcase__mutmut_33`: changes the successful
  row's accompanying error string from `""` to `"XXXX"`. Its sole production caller only reads
  that error when the row is None; successful rows proceed through counter validation and
  return a new empty detail. Every public report/projection/kill result is identical.
- `fa.inner_loop.slice_verification.x__junit_counter_error__mutmut_70`: changes
  `raw.lstrip("0")` to `raw.lstrip("XX0XX")`. The preceding ASCII-digit validation excludes X;
  Python strips a set of characters, so on every admitted input the operation is identical.
  This is an upstream-validation/standard-library invariant, not an untested exception path.

Raw scratch results are not committed/generated artifacts. The scoped configuration, exact IDs,
source hash, counts, reproduction command and equivalence proofs above preserve the result.
Global mutmut configuration/CI scope is unchanged.

### Remaining acceptance

Every new callable/property producer is registered in
[e2e-live-verification-register.md](e2e-live-verification-register.md) with H01–H07 planned host
cases, controls, safe scratch execution, observed artifacts and BLOCKED conditions. No host
fixture helper was implemented before independent review. Local tests are C0 (including real
I/O); C1 belongs to the remaining SLICE6 wiring; no new C2 or deployed C3 result is claimed.
STEP7 completion is not I02 SHIPPED, not GAP-01–15 closure, and not I03 delivery.
