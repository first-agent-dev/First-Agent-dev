# Adversarial audit — how slice completion is measured

Date: 2026-09-07 · Tip: `6de5cad` · Auditor: harness engineering review
Scope: the completion/routing core, evaluated **as the plan intends to ship it**
(S6 onward implemented), not as a half-built system.

---

## 0. Correction to a previous claim

An earlier review said the ceremony was "aimed at the wrong role." **That was
wrong and is retracted.** The ceremony is a behavioural nudge for the
*implementer*; the coder is exactly the right target. Nudges shape the actor.
Gates measure the outcome. They are different instruments and the criticism
conflated them.

The accurate statement is narrower: **a nudge cannot also be its own gate.**
Everything below concerns the gate.

---

## 1. The completion chain, as verified in code

```
eval model writes prose
  -> parse_eval_report()                 workflow_artifacts.py:433
       _scan_verdict()   regex           :332  (PASS|REPAIR_REQUIRED|...)
       _scan_step_results() regex        :342  ^[-*] (S\d+...) : (PASS|FAIL|PARTIAL)
  -> verdict drives route                :472  (verdict is primary, route is consequence)
  -> EVAL_VERDICT_TO_TERMINAL_STATUS     workflow_controller.py:52  "PASS" -> "DONE"
  -> workflow_exit_code                  :776  0 if DONE else 1
```

**Measured probe results** (`parse_eval_report` called directly):

| Input | verdict | route | step_results |
|---|---|---|---|
| the single word `PASS` | PASS | complete | `[]` |
| `- S99: PASS` / `- S404: PASS` (slices in no plan) | PASS | complete | accepted, `acceptance_matched=True` |
| `- S6: PASS` / `- S7: PASS` (blocked on Q10 here) | PASS | complete | accepted |
| `- S1: PASS -` (empty evidence) | PASS | complete | `acceptance_matched=True` |

Good property, worth keeping: **fail-closed on unparseable output** — no verdict
token yields `BLOCKED`/`blocked` (`:456-468`), never silent success.

---

## 2. Findings

### F1 — `step_results` has no consumer (dead telemetry)

`grep -rn step_results src/fa/` outside `workflow_artifacts.py` returns exactly
one hit: a docstring in `prompt.py:829`. Per-slice verdicts are parsed,
serialised to `eval_report.json`, and **never read by any decision**. Routing
uses only the single top-level verdict.

Consequence: slice granularity is presentational. A run where `S1..S8` are
`PASS` and `S9` is `FAIL` routes identically to one where the model wrote
nothing but `REPAIR_REQUIRED`.

### F2 — `acceptance_matched` is a tautology

`workflow_artifacts.py:426`: `acceptance_matched=verdict == "pass"`.

The field name promises "the acceptance predicate was matched." It computes "the
model said pass." The planner prompt does require acceptance predicates
(`prompt.py:426`: *"every step must expose an acceptance predicate"*), but no
predicate is ever machine-evaluated. **This is the single most misleading name
in the artifact schema** — a reader of `eval_report.json` will believe an
acceptance check occurred.

### F3 — slice IDs are unvalidated; `plan_ids.py` is imported by nothing

`_STEP_LINE_RE` accepts any `S\d+[A-Za-z0-9_.-]*`. `S404` parses.
`grep -rn "plan_ids" src/fa/` outside the module itself: **empty**. The
extractor that already returns this plan's real slice IDs
(`S1,S2,S3,S4,S5a,S5,S6a,S6,S7,S8,S9,S10,S6b`) is shipped and unwired.

The dangerous direction is **omission**, not invention: a model that silently
drops `S7` from its step list produces a clean `PASS`.

### F4 — eval is not independent: it resumes the coder's conversation

`_run_initial_roles:583` and `_run_linear:747` both pass `fresh=index == 0`.
Only stage 0 starts fresh. **The eval stage resumes the same session**, i.e. it
reads the coder's own narration of success as its primary context.

This is the most consequential finding. Compounding factors:

- The harness passes eval **no plan file, no diff, no contract list**. `grep`
  for `plan_path|plan_file|diff` in `workflow_controller.py`: **zero hits**.
  Eval receives `ctx.task_for(role)` — a task string (`:283`).
- `ADVERSARIAL_EVAL_STANCE_PREAMBLE` exists (`prompt.py:907`) and is good, but
  it fires *only* when `models.eval_independence.stance == "adversarial"`
  (`:220-224`), i.e. when families overlap and it is configured. It changes
  **stance**, not **evidence**.

So "eval validates contracts in code vs what the plan proposed" is the
*intent*, and the eval system prompt genuinely asks for it — but the harness
supplies neither the plan nor the diff, and seats the judge inside the
defendant's transcript.

### F5 — eval *can* verify, and that is the opening

Eval holds `fs_run_bash` and its prompt already says *"repo-native verification
commands"* and *"try the verification steps yourself."* The capability and the
instruction both exist. **What is missing is enforcement**: nothing checks that
eval ran anything before saying PASS. This is why Q11 is high-ROI — it converts
an existing instruction into an invariant instead of adding a new subsystem.

---

## 3. Answering the operator's central question

> "eval is meant to validate contracts in code vs what plan proposed. so if
> everything works as I intend, code will always be as good as plan is."

**The logic is correct. The implementation does not yet close it, and it cannot
close by prompting alone.** Precisely:

- *"as good as the plan"* holds only if the plan's contracts are
  **machine-checkable** and **machine-checked**. Today they are prose read by a
  model that also read the coder's claims.
- A ceiling of "as good as the plan" is the right ambition and unusually
  well-posed for an LLM harness. Most harnesses have no ceiling at all because
  they have no contract.
- The failure mode is not "code worse than plan." It is **"the harness cannot
  tell"** — which is worse, because it reports DONE either way.

The gap is one word: **attestation vs. observation.** The plan currently
measures attestation.

---

## 4. Will shipping S6+ as planned leave a flawed core?

**Yes — if S6 lands as written in v7, but the flaw is small and local, not
architectural.** The plan's spine (named contracts → slices → per-slice
verdicts → routing) is sound. Three seams are unfinished:

1. S6 runs verification commands but v7 routes failures to `REPAIR_REQUIRED`, a
   constant nothing branches on (Q10, already blocking).
2. Nothing forces eval's verdict to *agree* with what S6 observed. A green
   command set and a `PASS` are two unrelated facts in the same run.
3. `step_results` remains unconsumed, so per-slice truth cannot route.

Fix those three and the core is sound. That is roughly 100 lines, not a
redesign. **The architecture is right; the last mile is missing.**

---

## 5. Recommendations (ranked by ROI)

### R1 — Reconcile the verdict against harness observation *(Q11 = yes)*

The harness already runs the plan's `verify` block (S6). Make the terminal
status a **function of both** signals, with the observation dominant:

| harness commands | eval verdict | terminal | rationale |
|---|---|---|---|
| all exit 0 | PASS | **DONE** | agreement |
| any non-zero | PASS | **REPAIR_REQUIRED** | observation overrides the claim |
| all exit 0 | REPAIR_REQUIRED | **REPAIR_REQUIRED** | eval may see what commands cannot |
| no commands | any | eval's verdict + `evidence: none` | honest degradation (G8) |

Only the second row is new authority, and it is exactly the row that removes
the "model typed a word" failure. Record both facts in `eval_report.json`
(`harness_verification` alongside `verdict`) so disagreement is auditable
rather than silently resolved.

This mirrors CI practice: a reviewer's approval does not merge a red build.

### R2 — Validate slice IDs against the plan *(Q12 = yes, warn on missing)*

Wire the already-shipped `extract_plan_ids`:

- claimed ID ∉ plan → **WARNING**, and drop it from `step_results` (it is noise,
  not evidence).
- plan slice with **no verdict** → **WARNING** per the operator's decision
  (start non-blocking; revisit once coverage is observed in real runs).
- Keep both in the artifact so the gap is visible.

Cheap, deterministic, no new concepts.

### R3 — Fix `acceptance_matched` *(rename or make real)*

Either rename to `claimed_pass` (honest, 1-line) or bind it to R1's observation
for the commands attributable to that slice. **Do not ship a field named
`acceptance_matched` that means "the model said pass."**

### R4 — Give eval the artifacts, and consider a fresh session

Two independent changes, in order of value:

1. **Supply the evidence**: pass the plan path and `git diff` into the eval
   stage's task. Today it gets neither. This is the cheaper half and probably
   the larger quality win.
2. **Consider `fresh=True` for eval.** Resuming the coder's transcript is the
   structural independence break. Caveat, stated honestly: a fresh eval loses
   useful context and costs tokens, and the coder transcript does contain real
   evidence. Recommendation: make it a **flag**, default unchanged, and measure
   — this is an empirical question, not a settled one.

### R5 — Q10: route synthesis

Operator's instinct (synthesise a report with `return_to_coder` /
`return_to_planner`) is right. Refinement: **the harness should only ever
synthesise `return_to_coder`.** A failing verification command is by definition
an implementation defect — `prompt.py:804-812` reserves `REPLAN_REQUIRED` for
plan-shape problems, a judgement requiring reading comprehension the harness
does not have. Let eval escalate to planner; let the harness escalate to coder
only. Cap via `repair_round` (already exists).

---

## 6. Q14 — the flow chart

Verified against `workflow_controller.py`. Two modes exist; `--roles` makes the
sequence custom.

```
fa workflow --roles A,B,C  --mode {linear|adaptive}
        │
        ├─ deadline check ───────────────── _run_stage:263 (single choke point)
        │
   ┌────┴──────────── LINEAR (_run_linear:738) ─────────────────┐
   │  for i, role in roles:  fresh=(i==0)                        │
   │      run stage; non-zero exit -> STOP, terminal FAILED      │
   │      if role == eval: parse report                          │
   │  terminal = verdict or DONE-if-no-eval  (:468)              │
   └─────────────────────────────────────────────────────────────┘

   ┌───────────────── ADAPTIVE (_run_adaptive:596) ──────────────┐
   │  initial roles (planner -> coder -> eval)                   │
   │  loop:                                                       │
   │    route == return_to_coder    -> repair_round+1             │
   │         cap hit -> terminal, exit 0  (:621-628)              │
   │         else re-run coder->eval  (_canonical_loop_roles:641) │
   │    route == return_to_planner  -> replan_round+1             │
   │         re-run planner->coder->eval (:707)                   │
   │    route == complete           -> DONE                       │
   │    route == blocked            -> terminal BLOCKED           │
   └──────────────────────────────────────────────────────────────┘
```

**Where R1/R2 insert** (one place, both modes):

```
   coder stage ends
        │
        ├─ S6a: capture packet   (sink[-1].final_text)
        ├─ S6:  run plan verify commands -> observations
        │
   eval stage ends
        │
        ├─ parse_eval_report -> claimed verdict + step_results
        ├─ R2: validate slice IDs vs extract_plan_ids  -> warnings
        ├─ R1: reconcile(observations, claimed) -> effective verdict
        │
        └─ route on the EFFECTIVE verdict
```

The important property: **one reconciliation point**, immediately after eval,
feeding the existing router. Linear and adaptive both pass through it; custom
`--roles` orders inherit it; no second routing concept is introduced.

---

## 7. On the meta-question

> "this project is my attempt to exercise an LLM trained on tons of mediocre
> code to perform like seniors. am I achieving this?"

Partly, and the part that works is not the part usually credited.

- **The ceremony changes output format reliably; its effect on code quality is
  unproven.** The operator's own read matches the literature: structured
  self-reports improve *legibility* and *consistency* far more than
  *correctness*. Format compliance is easy to satisfy without doing the work —
  and this codebase contains the proof, in `acceptance_matched`: a field with a
  senior-sounding name and tautological content.
- **What actually raises the ceiling here is the contract spine** — named
  GAP/CT/S/T IDs, kill-checks, negative proof, mutation testing. Those are
  falsifiable. That is genuinely senior practice and it is unusual.
- **The one senior habit still missing is exactly R1**: senior teams do not
  accept "I ran the tests" — the pipeline runs them. The harness should hold
  the same standard it asks of the model. The operator's own rule, *"never mark
  a slice complete from 'no exception'"*, currently binds the coder but not the
  harness itself.

Make the harness obey its own rule and the ceiling moves from *"as good as the
model's self-report"* to *"as good as the plan"* — which was the intent.
