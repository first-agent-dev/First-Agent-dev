# Yes. A simpler solution exists — and it is already half-built.

You are right that this got complicated. This note says where the complexity
came from, what the elegant version is, and what it lets us delete.

---

## 1. Where the complexity came from

Look at what the current plan is trying to do:

> The judge writes prose. We parse the prose to learn which slices it looked at.
> Then we argue about what to do when the prose is incomplete, or bolded, or in
> a table, or lies.

Every hard question of the last several turns is downstream of that one design
choice:

| Question | Exists only because... |
|---|---|
| Q17 — unjudged slice? | ...the judge's coverage is *self-declared* |
| Q20 — regex vs tool vs schema | ...the answer arrives as *text* |
| normalisation matrix (T51) | ...text has infinite formatting |
| `tool_choice` adapter work | ...we want to *force* the text into a shape |
| Q21 — coder self-report | ...we're hunting for a more reliable narrator |

Current cost: **29 GAPs, 46 verification rows.** That is the price of making an
unreliable narrator trustworthy.

**The complexity is not in the problem. It is in the choice to ask a model a
question that has a factual answer.**

---

## 2. The question we should be asking instead

"Did slice S1 get done?" is not a matter of opinion. It's a matter of fact:

```
   ASKING A MODEL                     RUNNING A COMMAND
   ---------------                    -----------------
   "did you finish S1?"               pytest tests/test_retry.py -q
           |                                   |
     prose answer                        exit code 0 or 1
           |                                   |
   parse it, normalise it,            ...that's it
   validate IDs, detect
   silence, re-ask, halt
           |
   29 GAPs, 46 T-rows
```

A test either passes or it doesn't. There is no formatting drift in an exit
code, no bolding, no "PASSED" vs "PASS", no silence to detect.

---

## 3. The mechanism already exists in this repo

This is the part that matters. I went looking for what it would cost to build,
and found it mostly built.

`feature-planning/SKILL.md` already requires every slice to name its tests with
kill-checks (`SKILL.md:630`):

```
Verification:
- T1 C1 create: response schema + DB row; kill-check=remove insert.
- T4 C3 isolation: B excludes A row; kill-check=remove user filter.
```

And `inner_loop/plan_ids.py` already **extracts runnable commands** from the
plan — `_VERIFY_BLOCK_RE:85` and `_extract_commands:123`. Verified by running
it:

```
slices  : ('S1', 'S2')
commands: ('pytest tests/test_retry.py -q', 'pytest tests/test_cli_retry.py -q')
```

The harness already has a subprocess runner (`workflow_controller.py:413`) with
timeouts and fail-safe degradation.

**And here is the finding that decides this:**

```
who reads PlanIds.commands?   -> nobody. zero call sites.
who reads PlanIds.slices?     -> workflow_controller.py:332, :461
```

We extract the executable acceptance criteria out of every plan, put them in a
frozen dataclass — **and then throw them away.** Meanwhile we built a
regex-parsed prose contract to recover a weaker version of the same
information, from a less reliable source.

That is the whole answer. The elegant path isn't new architecture. It's
*using the field we already populate.*

---

## 4. The elegant design

Per slice, the plan carries a verify block. The harness runs it. That's the
gate.

```
   plan slice S1  --->  ```verify
                        pytest tests/test_retry.py -q
                        ```
                              |
                    HARNESS runs it (not the model)
                              |
                    exit 0 = S1 done.  exit != 0 = S1 not done.
                              |
                    +---------+----------+
                    |                    |
              all slices pass       some slice fails
                    |                    |
              run may finish        REPAIR, and the coder is
                                    told exactly which command
                                    failed, with its output
```

The judge does not disappear — it keeps the job models are genuinely good at
and commands are bad at: *is this a good implementation? did it break something
adjacent? is the test itself honest?* But it stops being the **bookkeeper of
what got done**, because that was never a judgement call.

### What this changes about the open questions

| Question | Under the elegant design |
|---|---|
| **Q17** (unjudged slice) | **Dissolves.** Coverage is no longer self-declared. A slice with no passing verify command is not done — no re-ask, no halt-for-operator, no full-gate policy. |
| **Q20** (regex/tool/schema) | **Demoted.** The verdict prose stops being load-bearing. Still nice to have structured output; no longer a correctness dependency. |
| **normalisation (T51)** | **Deleted.** Nothing depends on `**S1**` parsing. |
| **`tool_choice` adapter work** | **Deferred indefinitely.** |
| **Q21** (coder self-report) | **Dissolves.** Nobody's self-report matters; the command decides. |
| **Q16** (per-slice FAIL) | Unchanged, still live, still correct. |
| **Q18** (evidence to judge) | Unchanged and *more* valuable — the judge now also sees real command output. |

### What it does NOT solve

Being honest about the boundary, because this is where "elegant" usually
oversells:

1. **A plan with no verify blocks.** Legacy plans have none. Behaviour must
   degrade to today's advisory path, not fail. (The operator already ruled
   legacy non-conformance expected, not a kill signal.)
2. **A command that doesn't actually test the slice.** `pytest -q` on an empty
   file exits 0. This is why the *judge stays* — reviewing whether the test is
   honest is exactly the kill-check discipline the skill already mandates.
3. **A coder that edits the test to pass.** Real risk. Mitigated by the diff
   already going to the judge (S13/Q18) — a test weakened in the same diff is
   visible.
4. **Slices that are not testable by command** (docs, ADR edits). These fall
   back to judge assessment. Expect a genuine mix, not a clean sweep.

So it's not "delete the judge." It's **move factual questions to facts, leave
judgement questions to the judge.**

---

## 5. What I'd propose concretely

Replace the tail of S15 with one small slice:

**S16 — the harness runs the plan's own acceptance commands.**

- read `PlanIds.commands` per slice (already extracted, currently discarded)
- run each in the workspace with a timeout, capture exit code + output
- a slice is complete iff its commands exit 0
- feed the results into the evidence block the judge already receives
- no verify blocks ⇒ advisory, exactly as today

Rough size: one new function, one call site, plus tests. Compare against the
**29 GAPs / 46 T-rows** currently queued to make prose trustworthy.

### Sequencing, honestly

**S15c still ships first regardless.** A secret in a diff currently reaches the
model unmasked — that's a live security defect and it is independent of all of
this.

After that, my recommendation is: **stop, do S16, then re-derive what's left of
S15.** I expect a large part of S15d/S15e and all of the Q20 follow-on work to
evaporate rather than get built. Re-deriving is cheaper than building things we
then delete.

---

## 6. The uncomfortable part

I should have found this earlier. I audited the eval path twice, wrote 29 GAPs,
and built an increasingly elaborate apparatus for extracting trustworthy
answers from prose — without asking whether the question needed to be asked in
prose at all.

The tell was visible the whole time: `PlanIds.commands` is populated and read by
nobody. A field that is extracted and never consumed is either dead code or a
design that hasn't arrived yet. I logged the same pattern as a lesson earlier in
this work — *grep for readers, not writers* — and then didn't apply it to the
one field that mattered.

Your instinct to stop and ask was correct.
