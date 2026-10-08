# `slice_verification` — requirements & design (draft for review, 2026-10-07)

Operator decision: non-vacuity is proven by **executing a declared kill-check**, not by asking
whether a test is new. This document restores the mental model, gathers the requirements with
their sources, and proposes a design. **Status update (2026-10-08):** SLICE5 STEP1–STEP2 are implemented; STEP3 is paused on Q52. The note
remains the design input; plan CT68/69/85/86 and resolved Q49 supersede its original per-command
baseline sketch.

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
| *Is this a good implementation?* | **the judge (I03 eval)** | genuinely a judgement |

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
| R7 | Routing: non-zero ⇒ synthesise an eval report with `route_decision="return_to_coder"`, harness-origin, governed by the `repair_round` cap | **Q10(a), answered 2026-09-07** |
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
4  KILL-CHECK  per FUNCTIONAL contract, in a worktree:
                 a. target missing      -> PRODUCER_ABSENT
                 b. mutate, run that contract's test
                 c. test still passes   -> VACUOUS
                 d. test fails          -> this contract is PROVEN
5  VERDICT     all contracts proven and no regression -> PROVEN
```

**Q49 correction (2026-10-08):** the baseline is per pytest nodeid, not per command or file;
both T0 and “now” are harness-issued JUnitXML runs. Capture is once at T0 (CT85/CT86).
**Open precedence:** whether a failing verify-command exit remains `FAILING` when the nodeid
run reports a regression is Q52; do not infer precedence from the phase ordering above.

Phase 4 runs **only the contract's own test**, never the suite — that is what keeps the cost
at roughly one extra test run per contract, and it is the natural reading of §6.2's
affected-path scoping.

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
