# Q20 — how should agents report structured results?

Answers four things you asked: what "100% vs 64%" means, who should carry a
schema, whether the coder could self-report per slice, and what we actually
concluded about slice granularity.

Every number below was produced by running the code or read from a cited
source.

---

## Part 1 — What "100% vs 64%" means

### The problem it measures

When you ask a model for JSON, there are three different levels of guarantee,
and they are routinely confused:

| Level | What you send | What you get | What can still break |
|---|---|---|---|
| **Prompt only** | "reply in JSON" | usually JSON | truncated, prose wrapper, wrong fields |
| **JSON mode** (`json_object`) | a flag | **always valid JSON** | any shape at all — wrong field names, missing keys |
| **Schema mode** (`json_schema`) | your schema | **JSON matching your schema** | refusals, unsupported schema features |

The jump that matters is the second to the third. JSON mode guarantees the text
*parses*. It does not guarantee the object has the fields you need. Schema mode
constrains the model's token sampler so that tokens violating the schema
**cannot be emitted** — it's a hard constraint at decode time, not an
instruction the model may ignore.

### Where the numbers come from

The `100% vs 64%` line lives in this repo at `src/fa/providers/mistral.py:22-26`.
I traced it to its source rather than trusting the comment. It comes from a
pydantic-ai benchmark ([issue #4762](https://github.com/pydantic/pydantic-ai/issues/4762)),
testing both modes across nested schemas:

| Schema shape | `json_schema` strict | `json_object` |
|---|---|---|
| 3 levels nested | 5/5 | 5/5 |
| **4 levels nested** | 5/5 | **1/5 (20%)** |
| **4 levels + optionals** | 5/5 | **0/5 (0%)** |
| 3 levels + lists | 5/5 | 5/5 |
| **Total** | **25/25 (100%)** | **16/25 (64%)** |

Note the shape of the failure: flat schemas are fine in both modes. The
collapse happens at depth. **Our verdict schema is shallow** — a list of
`{step_id, status, note}` plus a verdict string. So the 64% figure is the
*pessimistic* end and probably doesn't apply to us directly.

Vendor figures agree on direction, and are worth knowing because they rank the
options: OpenAI's own evaluations put Structured Outputs at **100%** schema
compliance, **function/tool calling at ~86%**, and plain JSON mode lower still
([datastudios summary](https://www.datastudios.org/post/openai-structured-outputs-vs-json-mode-schema-enforcement-reliability-and-failure-modes)).

**That last number matters and it corrects my earlier advice.** I recommended
the tool-call route over `response_format`. On reliability alone, tool calling
is the *middle* option, not the best one.

---

## Part 2 — Who should carry the schema?

You said you're fine giving a new tool to eval only. Here's the honest state of
what's available, which changes the recommendation.

### A blocking constraint I found: we cannot force a tool call

```
anthropic        tool_choice: 0 references
openai_compat    tool_choice: 0 references
mistral          tool_choice: 0 references
```

`tool_choice` is the parameter that says "you MUST call this tool." **No adapter
in this repo sends it**, and it isn't in Mistral's recognised-parameter set
either. So today a `submit_verdict` tool is one the model is *invited* to call
and may simply not.

That undercuts the clean story I told you last turn. A tool the model can skip
doesn't remove the parsing fallback — it adds a second path to maintain.

### And `response_format` is Mistral-only here

```
mistral.py                16 references
mistral_conversations.py   3
anthropic.py               0
openai_compat.py           0
```

So the two candidate mechanisms are each partially unavailable:

| Mechanism | Reliability | Available in this repo | Enforceable? |
|---|---|---|---|
| `response_format: json_schema` | ~100% | **Mistral only** | yes, when available |
| Tool call + `tool_choice` | ~86% | tools yes, **`tool_choice` no** | **not today** |
| Tool call, unforced | — | yes | model may ignore it |
| Regex on prose | brittle (see Part 4) | yes | n/a |

**Neither is a drop-in.** Whichever we pick, the first piece of work is adapter
plumbing, not prompt design.

### Recommendation

**Eval only, and do the adapter work first.** Concretely, in this order:

1. Add `tool_choice` passthrough to all three adapters. Small, isolated, and it
   is the thing that converts "the judge might report structurally" into "the
   judge must."
2. Give eval a `submit_verdict` tool with a **flat** schema.
3. Keep the regex as fallback for models that end with prose anyway.

Not `response_format`, despite its better number — making the verdict contract
work only on Mistral is a worse property than losing ~14 points of schema
adherence on a schema shallow enough that the 64% collapse doesn't apply.

---

## Part 3 — Could the *coder* self-report per slice instead?

You asked whether the coder could declare slices done as a last step. This is
the most important question of the four, because it looks like a shortcut and
is actually a change in trust model.

### What separates the two roles

```
   coder says "S1 done"          eval says "S1 PASS"
           |                             |
   a CLAIM about work            a JUDGEMENT of work
   made by the party             made by a party with
   that did it                   no stake in the outcome
           |                             |
   cannot be the gate            can be the gate
```

The reason this harness has a separate eval role at all is that a model's
self-report is the least reliable signal in the system — it ends with "all
tests pass" because that's how such text usually ends. If the coder's
structured self-report became the completion signal, we would have rebuilt
exactly the thing the eval role exists to prevent, only now in JSON, which
*looks* more trustworthy than prose while being precisely as trustworthy.

**So: not as a gate.** But there is a genuinely useful version.

### The useful version: a claim, cross-checked

A coder `slice_status` tool would be worth having as **input to the judge**, not
as a verdict:

- coder calls `slice_status(S1, "done", files=[...])`
- harness records the claim, does **not** act on it
- the claim is handed to eval as evidence: *"the coder claims S1, S2 complete;
  verify independently"*
- **a claim that the judge contradicts is itself a signal** — a coder that says
  done on something that fails is a measurably different failure from a coder
  that says nothing

That gives you the per-slice measurement you're after without moving the gate
to the party being measured. It also composes with the evidence block from Q18:
claims go in the same harness-supplied frame as the diff.

Filed as a candidate slice. Not in S15.

---

## Part 4 — Did we abandon measuring slices? No. Here's the actual conclusion.

Two different decisions, both settled, easy to conflate:

### Q-op1 — slice *granularity* (settled, plan line 368)

> before-gate once at slice entry; one edit packet per edit; after-gate +
> harness verification once before the commit. **One S# below = one commit.**

That's the *hybrid* option you chose. It governs how work is chunked and
committed. Unchanged.

### Q16 — does a per-slice FAIL block completion? (settled: yes, option (a))

This is the "do we measure slices" question, and it is **already implemented and
live**. Verified by running it:

```
judge said top-level PASS but marked S2 FAIL
  final verdict : REPAIR_REQUIRED
  route         : return_to_coder
```

A judge can no longer wave a run through while carrying a failing slice. The
per-slice result overrides the headline verdict.

So the measurement ladder as it now stands:

| Question | Status |
|---|---|
| Are slices chunked and committed one-per-`S#`? | settled Q-op1 (hybrid) |
| Does a slice marked FAIL block the run? | **live** (Q16 = a) |
| Does a slice nobody judged block the run? | **your Q17 answer** — re-ask once, then halt |
| Are slice IDs checked against the plan? | live (S12) |
| Is the judge shown the plan and diff? | live (S13), default `enforce` per your Q18 |

Nothing was abandoned. Q17 closed the last hole: FAIL was caught, *silence* was
not.

---

## Part 5 — Why this can't be measured "per current plan suggestions" yet

You asked whether we can measure slice completion if everything currently
planned works as intended. Short answer: **the plumbing will exist, the
measurement won't be trustworthy yet** — because of the parser.

The full gate you chose depends on recognising which slice IDs the judge
reported. Today that recognition is a regex, and it is brittle in a way that
interacts badly with a full gate:

```
plain markdown  parsed=['S1','S2']  unreported=[]
bolded IDs      parsed=[]           unreported=['S1','S2']
markdown table  parsed=[]           unreported=['S1','S2']
```

A judge that reviewed **every slice correctly** but wrote `**S1**` reads as a
judge that reviewed nothing — and under your full gate that halts the run and
calls you over for nothing. Two false halts and the gate stops being believed.

This is why S15d ships **normalisation** (strip `**`, accept tables, numbered
lists, `PASSED`, `Step ` prefix) as mandatory, not optional. It doesn't make
parsing sound; it removes the failure modes a competent model actually produces.

**The honest sequencing:**

| Stage | What you get |
|---|---|
| after S15d | slice measurement that works, resting on normalised regex |
| after adapter `tool_choice` + `submit_verdict` | slice measurement that rests on an enforced schema |

The second is the right destination. The first is worth shipping because it is
small and unblocks the gate now — but it should be understood as a stopgap with
a known ceiling, not as the finished contract.

---

## Part 6 — What I'd ask you to decide (nothing blocking)

1. **`tool_choice` adapter work** — worth its own slice after S15? It's the
   piece that makes any structured contract enforceable rather than advisory.
2. **Coder `slice_status` as evidence** (Part 3) — want it, or leave the coder
   silent and let the judge derive everything from the diff?

Neither blocks S15. S15c (the unmasked-secret fix) is next and needs nothing
from you.
