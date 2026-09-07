# Decision brief — Q17 and Q18

Everything you need is ~90 lines of reading. Line ranges, not documents.

---

# Q17 — an unjudged plan slice: REPAIR / BLOCKED / warn?

## Read, in this order

| # | Source | Lines | Why |
|---|---|---|---|
| 1 | `src/fa/inner_loop/prompt.py` | **795-816** | The route definitions the evaluator is held to. This is the decisive text. |
| 2 | `src/fa/inner_loop/workflow_controller.py` | **53-58** | Verdict → terminal status. `BLOCKED → FAILED`. |
| 3 | `src/fa/inner_loop/workflow_controller.py` | **944, 981** | Only `return_to_coder` and `return_to_planner` loop. Everything else is terminal. |
| 4 | `AUDIT-S12-S13-adversarial.md` | A-2 | The measured hole: 1-of-20 judged ⇒ `DONE`, exit 0. |

## What the source says (verbatim, prompt.py:814)

> **Blocked (`BLOCKED`)** only for hard external blockers, contradictory
> evidence, or missing capabilities that prevent a fair repair/replan decision.

**This weakens my earlier recommendation and I want to flag that directly.**
I argued for BLOCKED because "the fault is the evaluator's". But the prompt
defines BLOCKED as *the evaluator reporting an external obstacle* — a claim the
evaluator makes about the world, not a verdict the harness imposes on the
evaluator. Overloading it to mean "you did your job badly" reuses a channel that
already means something else, and the operator reading `FAILED` cannot tell the
two apart.

## The three options, by consequence

| | Terminal status | Exit | Loop | Who is re-run | Honest? |
|---|---|---|---|---|---|
| **(a) REPAIR_REQUIRED** | `REPAIR_REQUIRED` | 1 | retries | **the coder** | ✗ blames the coder for the judge's omission |
| **(b) BLOCKED** | `FAILED` | 1 | halts | nobody | ~ correct outcome, wrong vocabulary |
| **(c) warn only** | `DONE` | **0** | — | nobody | ✗ this is today's A-2 bug |

(c) is the status quo the audit found broken: coverage recorded, nothing
enforced. It cannot be the answer if P3 ("a slice nobody judged cannot be
reported done") is a real requirement.

## What I'd now recommend: (b), with a caveat — or a fourth option

**(d) re-run the EVAL stage once, then fall back to (b).** The failure is
"the judge skipped work", and the cheapest correct response is to ask the judge
again with the unreported IDs named. It re-runs the party at fault, costs one
eval call instead of a coder round-trip, and only escalates if the judge skips
twice. Cost: it needs its own budget counter (`max_eval_retries`), so it is
strictly more work than (b).

If you want the smallest correct change now: **(b)**, and treat (d) as a
follow-up. If you want the right long-term shape: **(d)**.

**Sub-question worth settling in the same breath:** does *one* unreported slice
out of twenty carry the same weight as nineteen? A threshold ("any" vs
"a majority") is a policy dial I should not pick.

---

# Q18 — registered injection default: `observe` or `enforce`?

## Read, in this order

| # | Source | Lines | Why |
|---|---|---|---|
| 1 | `knowledge/adr/ADR-10-...md` | **473-481** | Clause 4, the rule in question, *with its stated rationale*. |
| 2 | `knowledge/adr/ADR-10-...md` | **451-458** | I-6's scope: "Every prompt **injection**". The whole question is whether evidence is an injection. |
| 3 | `src/fa/feature_flags.py` | **46, 51-57** | The existing polarity split: `intent_guard_mode="enforce"` (safety gate) vs `coder_slice_ceremony_mode="observe"` (advisory payload). |
| 4 | `AUDIT-S12-S13-round2.md` | B-9 | How S13 violates all five I-6 clauses today. |

## The rationale is the crux (ADR-10:476-481)

> The polarity is deliberately the opposite of a safety gate such as
> `intent_guard_mode`, which fails CLOSED to `enforce`: a guard failing quiet is
> dangerous, whereas **an advisory payload failing loud would rewrite context
> nobody asked to change**.

I-6's `observe` default exists to protect against *unrequested context rewrites*.
Ask whether that rationale applies to the S13 block:

- The ceremony injection **adds instructions** telling the coder how to behave.
  Defaulting it on would change agent behaviour nobody asked for. → `observe` is right.
- The evidence block **supplies the artifact under review**. Defaulting it off
  means the judge evaluates a contract it was never shown — which is the
  original S13 defect. → `observe` reintroduces the bug S13 fixed.

So the two payloads are different *kinds*, and clause 4's stated reason does not
reach the second. That is an argument for amending I-6's scope, not for quietly
breaking it.

## The three options

| | Behaviour | ADR standing | Risk |
|---|---|---|---|
| **(i) `enforce` + amend I-6** | keeps shipped behaviour | honest: carve-out is written down | needs an ADR edit + review |
| **(ii) `observe`** | judge stops receiving evidence unless configured | complies literally | **silently regresses a landed slice**; the feature rots unused |
| **(iii) reclassify** — evidence ≠ injection, give it its own I-# | keeps behaviour | cleanest conceptually | most work; risks a second registry |

**My recommendation: (i)**, phrased in the ADR as a narrow carve-out —
*"payloads that supply the artifact under review, rather than instructions to
the model, default to `enforce`; they must still be registered, role-gated, and
introspectable."* That keeps four of five clauses intact and makes the exception
auditable instead of implicit.

**(iii) is the more principled version of the same idea** and is worth choosing
if you expect more evidence-class payloads (diffs, plans, prior findings — S15e
adds another). If this is the only one, (i) is proportionate.

**Not acceptable:** shipping as-is. Today the block is unregistered, always-on,
and invisible to `fa inject` — a third state where we neither comply nor
document the deviation.

---

# Q19 (non-blocking) — base commit under `--resume`

Read `src/fa/cli.py:2018-2033` (`resume` restores only the PR draft, not
history). Default if you say nothing: **the resumed session's HEAD**, recorded
in the artifact so the judge's frame of reference is always explicit.

---

# The minimum path

If you only read two things: **`prompt.py:795-816`** (settles Q17) and
**`ADR-10:473-481`** (settles Q18). Both are short, and both contain the exact
sentence the decision turns on.
