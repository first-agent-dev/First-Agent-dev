# Two decisions about the review step — a plain-language brief

*Rewritten. The previous version assumed you already knew the machinery. This
one explains it. Every number and transcript below was produced by running the
real code; the scripts are named so you can re-run them.*

---

## Part 1 — How this kind of system works (skip if you know it)

### The idea: don't let the worker grade its own homework

An AI coding agent is a loop: the model proposes an action, the harness runs
it, the result goes back to the model, repeat. The catch is that a language
model is a *fluent narrator*. It will end with "I've implemented the feature
and all tests pass" whether or not that happened — not from malice, but because
that's the shape of text that usually follows work.

So you cannot ask the worker "are you done?" and believe the answer. The
standard fix — the same one used in human engineering — is **separation of
duties**: one agent does the work, a *different* agent reviews it, and a piece
of ordinary code (not a model) decides what the review means.

In this harness that's three roles run in sequence:

```
  planner  ->  writes the plan (the contract)
  coder    ->  does the work
  eval     ->  judges the work against the plan
```

`eval` is the judge. It's the same underlying model, given a different job,
a different prompt, and — importantly — **no ability to edit files**.

### Where determinism comes in

The judge's answer arrives as *prose*. Prose can't drive a pipeline. So the
harness makes the judge end its message in a fixed shape:

```text
### Step results
- S1: PASS — verified with pytest, 14 passed
- S2: FAIL — the retry path is still unguarded

### Verdict
PASS | REPAIR_REQUIRED | REPLAN_REQUIRED | BLOCKED
```

`S1`, `S2` are **slice IDs** — the plan numbers its steps, and the judge is
supposed to return one line per step. A regular expression scrapes those lines
into a data structure, which is written to `eval_report.json`. From that point
on the decision is made by code, not by the model. That's the "deterministic
contract validation" idea: *the model supplies evidence; code supplies the
verdict.*

The four verdicts mean:

| Verdict | Meaning | What the loop does |
|---|---|---|
| `PASS` | work is good | stop, report success (exit 0) |
| `REPAIR_REQUIRED` | coder made a mistake | **re-run the coder**, up to a budget |
| `REPLAN_REQUIRED` | the *plan* was wrong | re-run the planner |
| `BLOCKED` | judge couldn't do its job | stop, report failure (exit 1) |

Both questions below are about what code should do when the judge's report is
*incomplete* or when the judge is *shown nothing*.

---

## Part 2 — The bug that produced both questions

The plan lists five steps. The judge reports on one and says PASS.
Real output from `worklogs/reviews/q17-q18-demos/demo_q17_the_bug.py`, run against the actual controller:

```
PLAN DECLARES : S1 S2 S3 S4 S5
JUDGE REPORTED: ['S1']
unreported_slices in artifact: ['S2', 'S3', 'S4', 'S5']
verdict: PASS | terminal status: DONE
EXIT CODE: 0  <- 0 means "success" to CI and to you
```

Four of five steps were never looked at. The harness **noticed** — that's the
`unreported_slices` field — wrote it into the report, and then shipped `DONE`
and exit code 0 anyway.

Nothing reads that field. It's a note in a logbook nobody opens.

```
                    judge returns "PASS", mentions only S1
                                  |
                                  v
                   +------------------------------+
                   |  code compares to the plan   |
                   |  finds S2,S3,S4,S5 missing   |
                   +------------------------------+
                                  |
                    writes "unreported_slices"
                                  |
                                  v
                   +------------------------------+
                   |   ...and does nothing else   |   <-- Q17 is here
                   +------------------------------+
                                  |
                                  v
                        DONE, exit 0, ship it
```

**Q17 asks: what should happen at that box instead?**

---

## Part 3 — Q17: what to do about steps nobody judged

### The three options, with measured consequences

I ran all three through the real controller (`worklogs/reviews/q17-q18-demos/demo_q17_options.py`). This is
actual output, not an estimate:

```
(c) warn only  -> PASS      status=DONE            exit=0  coder_runs=1 eval_runs=1
(a) REPAIR_REQUIRED         status=REPAIR_REQUIRED  exit=1  coder_runs=3 eval_runs=3
(b) BLOCKED                 status=FAILED           exit=1  coder_runs=1 eval_runs=1
```

Read the `coder_runs` column — that's the cost. Each run is a full LLM session.

```
                  judge skipped S2..S5
                          |
        +-----------------+------------------+
        |                 |                  |
       (a)               (b)                (c)
   REPAIR_REQUIRED     BLOCKED           warn only
        |                 |                  |
   re-run the CODER   stop the run      carry on
   3x, same prompt    exit 1            exit 0
        |                 |                  |
   costs 3 coder      costs nothing     costs nothing
   + 3 eval calls     extra             extra
        |                 |                  |
   but the coder      but "FAILED"      but this is
   did nothing        is vague          the bug
   wrong
```

### Why (a) is tempting but wrong

`REPAIR_REQUIRED` means "the coder made a mistake, send it back." But the coder
didn't make a mistake here — *the judge skipped work*. Option (a) punishes the
wrong party, and the measurement shows it costs 3 coder runs plus 3 eval runs
to accomplish nothing.

There's a second problem I found by testing the repair loop: the coder is
re-run **with exactly the same prompt**, with no information about what failed.
Three identical calls to the same model. (That's a separate defect, logged as
A-3, fixed by slice S15e.)

### Why (b) is right-ish but says the wrong word

`BLOCKED` stops the run and reports failure — the correct *outcome*. But here's
the sentence that matters, from the judge's own instructions
(`src/fa/inner_loop/prompt.py:814`):

> **Blocked (`BLOCKED`)** only for hard external blockers, contradictory
> evidence, or missing capabilities that prevent a fair repair/replan decision.

`BLOCKED` is a thing **the judge says about the world** — "I couldn't test this,
the database was down." Q17 is about the harness making a statement **about the
judge** — "you didn't finish your review."

Same word, two different meanings. If we reuse it, then later, when you see a
run marked `FAILED`, you can't tell whether the environment broke or the
reviewer was lazy. That's a real cost: it makes your logs ambiguous forever.

**I recommended (b) in an earlier draft. Reading line 814 changed my mind about
how clean it is.** It's still the best of the three, but it's a word being
borrowed, not a word that fits.

### The option that wasn't on the list

**(d) Ask the judge again.**

The failure is "the reviewer skipped four items." The natural response isn't to
punish the coder or kill the run — it's to hand the review back with a note:
*"you didn't cover S2, S3, S4, S5. Do those."* If it skips twice, then stop.

```
   judge skipped S2..S5
            |
            v
   re-run the EVAL stage, naming the missing IDs   <-- 1 extra eval call
            |
      +-----+-----+
      |           |
   covered      skipped again
      |           |
   continue    stop, and say why
              ("evaluator did not complete
                its review after 2 attempts")
```

Cost: **1 eval call**, versus 3 coder + 3 eval for option (a). It re-runs the
party that actually failed. It needs one new counter (`max_eval_retries`), which
is why it's more work to build than (b).

### What I'd suggest

| If you want | Choose |
|---|---|
| The smallest change that stops the bug today | **(b)**, with a distinct reason string so logs stay readable |
| The behaviour you'd want in a year | **(d)**, with (b) as its fallback |
| To keep shipping unreviewed work | (c) — this is the current state |

**A smaller question hiding inside Q17:** is one missing step out of twenty as
bad as nineteen? Right now any gap would trip the rule. You might want a
threshold. I have no basis for picking one — that's a judgement about how much
partial review you'll tolerate.

---

## Part 4 — Q18: should the judge be handed the evidence by default?

### What the "evidence block" is

The judge used to be given only a task string: *"Judge whether the coder
completed the plan."* It was not given the plan. It was not given the diff. It
was asked to check work against a contract it had never seen.

Slice S13 fixed that by attaching a block of facts the *harness* gathers — not
facts the coder claims. Here's the real difference, from `worklogs/reviews/q17-q18-demos/demo_q18_evidence.py`.
The coder has replaced a password check with `return True`:

**With the block OFF, the judge receives:**

```
Judge whether the coder completed the plan.
```

**With the block ON, the judge receives:**

```
Judge whether the coder completed the plan.

## Evidence supplied by the harness

Plan: /tmp/.../PLAN.md
Plan slices to judge (1): S1
Read the plan for the execution contract; do not infer it from the transcript.
Diff (git diff HEAD):
-def check_password(p): return verify(p)
+def check_password(p): return True  # TODO fix
```

With the block off, a judge has essentially no way to catch that. With it on,
it's the first thing in view.

### So why is this even a question?

Because the harness has a written rule about attaching text to prompts, and
S13 broke it. The rule is ADR-10 invariant I-6. In plain terms, any text the
harness injects into a prompt must be: **registered** in one table, **resolved
once** per run, **restricted to specific roles**, **introspectable** (you can
ask `fa inject` what's on without running a model), and — the clause in
question — **default to `observe`, not `enforce`.**

Three settings exist for any such payload:

| Mode | Meaning |
|---|---|
| `off` | attach nothing; identical to not having the feature |
| `observe` | log that it *would* have fired; change nothing |
| `enforce` | actually attach the text |

S13's evidence block is registered nowhere, has no setting, and is always on.
You currently cannot turn it off or see it listed. That part is simply a bug,
and slice S15g fixes it regardless of which way you answer.

The genuine question is: **once registered, what should its default be?**

### The argument, and why the rule's own reasoning is the key

Here's the rule with its stated rationale (`ADR-10:476-481`):

> The polarity is deliberately the opposite of a safety gate such as
> `intent_guard_mode`, which fails CLOSED to `enforce`: a guard failing quiet
> is dangerous, whereas **an advisory payload failing loud would rewrite
> context nobody asked to change.**

The rule exists to prevent *unrequested changes to how an agent behaves*. Now
compare the two payloads this harness attaches:

| | **Ceremony injection** (the existing one) | **Evidence block** (S13) |
|---|---|---|
| Contains | *"State, before any edit: current verified behavior, contract IDs, files allowed to change... If blocking: STOP."* | the plan path, the step IDs, and the actual `git diff` |
| Kind | **instructions** — tells the model how to work | **exhibits** — the material being reviewed |
| If on by default | agent behaviour silently changes | judge can see what it's judging |
| If off by default | agent behaves as before — safe | **judge reviews blind — the original bug** |

They're different kinds of thing. Turning instructions on by surprise is the
hazard I-6 was written to stop. Turning *exhibits* off by default doesn't avoid
a hazard — it recreates the defect S13 existed to fix.

An analogy: I-6 says "don't slip extra instructions into the judge's ear
without being asked." Reasonable. But the evidence block isn't a whisper in the
judge's ear — it's the case file on the table. A rule against coaching the
judge shouldn't be read as a rule against giving them the exhibits.

### The three ways forward

```
        S13 block is unregistered and always-on
                        |
          register it (S15g) -- required either way
                        |
              what default?
        +---------------+---------------+
        |               |               |
      (i)             (ii)           (iii)
   enforce +        observe        new category:
   write the        (comply         "evidence" gets
   exception        literally)      its own rule
   into ADR-10
        |               |               |
   behaviour       judge goes      behaviour kept,
   kept, rule      blind again     concept clarified
   honest          unless you
                   configure it
```

| | Effect | Cost |
|---|---|---|
| **(i) `enforce` + amend the ADR** | keeps today's behaviour; the exception is written down and reviewable | one ADR edit |
| **(ii) `observe`** | literal compliance | **silently undoes a shipped fix** — judges go back to reviewing blind unless someone edits config. Features that need configuring to work tend to stay off. |
| **(iii) new category** | cleanest: says evidence ≠ instructions, and gives it its own rule | most work; only worth it if more evidence-type payloads are coming — and slice S15e adds one (past failure notes for repair rounds) |

**My reading:** (i) if this stays a one-off; (iii) if you expect a family of
evidence payloads — which the current plan suggests you do.

**What isn't acceptable is the status quo**: unregistered, invisible, always-on.
That's not a decision, it's an oversight — we neither follow the rule nor
record that we're departing from it.

---

## Part 5 — What to actually read

You don't need to read the code. Two short passages contain the sentences the
decisions hinge on:

| For | Read | Length | The sentence that matters |
|---|---|---|---|
| **Q17** | `src/fa/inner_loop/prompt.py` lines **795-816** | ~20 lines | line 814 — the definition of `BLOCKED`. Decide whether "the judge skipped work" fits it. |
| **Q18** | `knowledge/adr/ADR-10-deterministic-harness-invariants.md` lines **473-481** | ~9 lines | the rationale: "an advisory payload failing loud would rewrite context nobody asked to change." Decide whether that reasoning covers *exhibits* as well as *instructions*. |

Optional background: `AUDIT-S12-S13-adversarial.md` finding **A-2** (the
measured hole) and `AUDIT-S12-S13-round2.md` finding **B-9** (how S13 breaks
I-6). Both are one screen each.

---

## Part 6 — Answer template

You can reply in one line each.

> **Q17** = (a) REPAIR / (b) BLOCKED / (c) warn only / (d) re-ask the judge, then stop
> — threshold: any missing step, or only if more than N are missing?
>
> **Q18** = (i) enforce + amend ADR-10 / (ii) observe / (iii) new "evidence" category

**Q19** is minor and has a sensible default; ignore it unless you care: when a
run resumes, should the diff be measured from the original run's starting point
or the resumed one? Default is the resumed one, recorded in the artifact.

### What unblocks on your answer

- **Q17** → slice **S15d** (the coverage rule)
- **Q18** → slice **S15g** (registration and framing)
- Everything else in slice **S15** — including the security fix, where a secret
  in a diff currently reaches the model unmasked — proceeds without you.
