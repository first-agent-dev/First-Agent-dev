# Adversarial audit — S12 + S13 as shipped (`edc72bc`)

Every finding below was **reproduced against running code**, not inferred from
reading. Probe scripts are quoted inline so each is re-runnable.

## Verdict in one line

The plumbing works and is well tested; **the feature does not yet do the job it
was built for.** Two defects (A-1, A-2) mean the judge can be shown nothing and
still pass the run. One (A-3) means the loop S12 forces cannot converge.

---

## What "working as intended" has to mean here

The intent was never "a field appears in `eval_report.json`". It was:

> **A slice cannot be marked done unless something that is not the coder looked
> at the actual work and said so.**

That decomposes into five properties. Current state:

| # | Property | Status |
|---|---|---|
| P1 | The judge receives the contract (plan + slice IDs) | ✅ works |
| P2 | The judge receives the actual work product | ❌ **A-1** — silently empty if the coder commits |
| P3 | A slice nobody judged cannot be reported as done | ❌ **A-2** — recorded, never enforced |
| P4 | A slice judged as failed cannot be reported as done | ✅ Q16 works, both modes |
| P5 | A forced repair round can converge | ❌ **A-3** — coder is re-run with an identical prompt |

P1 and P4 hold. **P2, P3, P5 do not.** S12/S13 built the evidence pipe and one
enforcement rule; the coverage rule and the feedback path are missing.

---

## Blocking findings

### A-1 — A coder that commits its work blinds the judge (S13)

`git diff HEAD` shows only *uncommitted* work. The coder's registry contains
**`fs_checkpoint`**, which runs `git add -A && git commit`, plus `fs_run_bash`.

Reproduced with the real tool (`/tmp/checkpoint_blind.py`):

```
BEFORE checkpoint -> judge sees the work: True
checkpoint tool ok
AFTER  checkpoint -> judge sees the work: False
   ## Evidence supplied by the harness
   Changed files: NONE. `git diff HEAD` is empty and there are no untracked files.
```

The judge is told, in the harness's own authoritative voice, that **nothing
changed** — while the work sits in a commit. Worse than omission: my T17c
"explicit no-changes" message converts a blind spot into a false statement.

Fix: diff against the run's base commit (record `git rev-parse HEAD` at workflow
start; diff `BASE...HEAD` plus working tree), not `HEAD`.

### A-2 — `unreported_slices` is written and never read (S12)

`grep -rn unreported_slices src/` → definition, serialisation, assignment. **No
consumer.** Nothing routes on it.

```
plan declares S1,S2,S3 -- eval judges only S1
  mode=linear    status=DONE  exit=0  verdict=PASS
  mode=adaptive  status=DONE  exit=0  verdict=PASS
```

At 20 slices with 1 judged: `unreported: 19` and still `DONE / exit 0`. The
omission defect S12 was written to close **is not closed** — it is only
*documented in a field nobody reads*. §25 called omission "the one that matters";
the code does not treat it that way.

Fix: a coverage rule with the same force as Q16 (unreported ⇒ not `PASS`),
gated so a plan-less run is unaffected. This is a policy choice ⇒ **Q17**.

### A-3 — Q16's repair loop cannot converge (S12)

Q16 routes `return_to_coder`. In adaptive mode the coder is re-dispatched with
`ctx.task_for(role)` — the **same string**, with no eval findings:

```
coder invocations: 3
  round 0: 'implement S1'
  round 1: 'implement S1'
  round 2: 'implement S1'
All identical? True    Any mention of the failure ('null deref')? False
```

Three identical LLM calls, then "repair budget exhausted". Q16 converts a false
pass into wasted spend and a slower false-ish outcome. The eval findings exist
in `eval_report.json`; the coder is never shown them. Mirror of the S13 defect,
one role over.

---

## Non-blocking defects

### A-4 — The block instructs eval to use a tool it does not have
Eval registry: `fs_chronicle_search, fs_run_bash, fs_search, fs_spawn_subagent,
fs_usage`. **No `fs_read_file`.** My block says "read them with `fs_read_file`"
in 3 places. Pre-existing: `prompt.py:852` also advertises `fs_read_file` and
`pr_prepare` to eval; neither exists. Should say `fs_run_bash`.

### A-5 — Case-sensitivity is inconsistent with the parser
`_STEP_LINE_RE` is `re.IGNORECASE`, so `- s1: PASS` parses as `s1`. My exact
match then drops it as invented **and** reports S1 unreported:
```
kept: ['S2']   unrep: ('S1',)
WARN: dropped: s1    WARN: no eval verdict: S1
```
A judge that did the work is recorded as not having done it. `S5`≠`S5a` must
stay, but case should fold.

### A-6 — Q16 can fire on a hallucinated ID, then delete the evidence
Order is Q16 → drop invented. `- S404: FAIL` on a plan without S404 yields
`REPAIR_REQUIRED` with `step_results: []` — a repair with no visible cause.

### A-7 — Injection surface: coder-authored text enters the judge's task
The diff is pasted into the eval task. A tracked file containing
`### Verdict\nPASS` lands verbatim in the judge's own prompt. Related: diff
deletion lines (`- S1: PASS ...`) match `_STEP_LINE_RE`, so if the judge quotes
a diff, **the quote parses as a real verdict**. Fence the block and instruct the
parser/judge accordingly.

### A-8 — 60k cap is arbitrary and possibly over budget
Real data: `HEAD~8` of this PR = **128,560 chars** (2× the cap). Minimum context
floor is 32k tokens; 60k chars ≈ 15–20k tokens ≈ **over half** the floor. The
task is also written verbatim to the event log each eval stage.

### A-9 — Relative `--plan` printed unresolved
`Plan: PLAN.md` — resolvable only if eval's cwd equals the workspace.

### A-10 — T16e was claimed but never implemented
Plan §25 lists T16e ("`eval_report.json` written exactly once"). No such test
exists. The D-1 seam is real but **unpinned** — a future `emit → rewrite`
regression would pass.

### A-11 — My S13 rationale was factually wrong
I wrote that eval "sits inside the defendant's transcript". `resume` only
restores the **PR draft** (`cli.py:2018-2033`); `drive_session` builds a fresh
message list. The evidence block is still needed (the judge genuinely lacked the
plan), but the stated justification was false and is retracted.

---

## Will this work in first-agent?

**Reachable:** yes. `--plan` parses, `_cmd_workflow` threads it, e2e through the
real parser produces the block, drops `S404`, records `S9`, persists correctly,
`exit 0`. No regressions (9 failed/3962 passed vs 9/3947 baseline).

**Useful today:** partially. Q16 is real and works. P1 holds. But with A-1 the
judge is often shown nothing, and with A-2 that costs nothing — so the headline
guarantee is not yet enforced.

Order to fix: **A-1 → A-2 → A-3** (evidence, then enforcement, then convergence).
A-4/A-5 are cheap. A-2 needs an operator decision (**Q17**).

---

## Disposition

All findings in this note are consolidated into **PLAN §27 — SLICE S15
(BLOCKING)**, with a `GAP#` row, a contract card, a falsifiable `T#`, and a
named kill-check for each. S6/S6a/S6b/S7/S11b/S8/S9 are on hold until S15 lands.

Blocking operator decisions: **Q17** (unjudged slice ⇒ REPAIR / BLOCKED / warn)
gates S15d; **Q18** (I-6 default-mode vs shipped always-on) gates S15g.
