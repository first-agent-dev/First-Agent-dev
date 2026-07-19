# Critical Reassessment: Did the Rewrite Actually Improve the Skill?

> **Created:** 2026-07-19
> **Question:** The user is second-guessing. Did the universality pass make
> the skill better or worse for its intended function?

---

## The Honest Answer: The Gap Fixes Made It Better. The Universality Pass Made It Worse.

### What the rewrite got RIGHT (unambiguous improvement)

The 10 gap fixes address real failure modes that caused 6 bugs in PR #53:

| Gap | Before | After | Impact |
|-----|--------|-------|--------|
| Kill-check on producer | "production call site" (ambiguous) | "PRODUCER emit call" (specific) | Prevents consumer-only kill-check |
| Existence pre-check | None | Must verify emit site EXISTS | Prevents vacuous pass |
| Two-sided contract | No concept | §8: producer + consumer verification | Prevents "not wired" gaps |
| Path inventory | No concept | §9: enumerate all emit paths | Prevents single-path coverage |
| Matrix coverage gate | "name the matrix" | "≥1 test per combo" | Prevents declared-but-not-covered |
| Dual-write consistency | No concept | §10: verify both write paths | Prevents one-sided writes |
| C0 theater trap | Weak warning | Explicit rule + §12 | Prevents false confidence |
| 6 new invariants | I-TW-1..13 | I-TW-14..19 | CI-enforceable gates |

These are genuine, battle-tested improvements. They would have prevented every
bug in PR #53. The rewrite is WORTH DOING for these alone.

### What the rewrite got WRONG (the universality pass)

The universality pass replaced FA-specific language with abstract language.
Let me trace through what this does to the AGENT that reads the skill.

**BEFORE (FA-specific):**
> "For every EventType, BOTH the producer (emit call) and the consumer
> (handler) must be verified."

Agent reads this. It knows exactly what to do:
1. Grep for EventType literals in output.py
2. For each, check output.emit() exists (producer)
3. For each, check _handle_X() exists (consumer)
4. Write tests for both sides

**AFTER (universal):**
> "For every observable signal (event, message, API call, metric emission),
> BOTH the producer (code that creates the signal) AND the consumer (code
> that handles it) must be verified."

Agent reads this. It now has to:
1. Figure out what "observable signal" means in THIS codebase
2. Map "producer" to the specific code pattern in THIS codebase
3. Map "consumer" to the specific handler pattern in THIS codebase
4. Then do steps 1-4 from the FA-specific version

**The universal version adds a TRANSLATION STEP** that the FA-specific version
doesn't need. For the PRIMARY use case (FA development), this is pure overhead.

---

## The Deeper Problem: Abstraction Hurts LLM Actionability

LLM agents work best with **concrete, specific instructions** — the same
principle the skill itself teaches (rank 1 oracles: structured fields > free
text). The universal rewrite does exactly what the skill warns against: it
replaces structured, specific guidance with abstract, ambiguous language.

Consider the ranked oracles section:

**BEFORE:** "Event `kind`+fields → `SessionOutcome` → tool trajectory →
provider `call_count`/payload/`call_count`/token band → FS → full deny dataclass"

**AFTER:** "Structured side effects (event type + fields) → outcome codes
(exit code, stop reason, status) → trajectories (action sequence + arg shapes)
→ call counts / payload shapes / resource bands → filesystem → free text"

The BEFORE version is immediately actionable: the agent knows to assert
`event.kind` and `event.data` fields first, then `outcome.stop_reason`,
then tool names, then `mock_chain.request.call_count`. The AFTER version
requires the agent to translate "structured side effects" into "what does
that mean in FA?" every single time.

This is not a theoretical concern. I watched the PR #53 agent fail to apply
the EXISTING skill's rules because they were already somewhat abstract. Making
them MORE abstract makes this worse, not better.

---

## The Universality Question: What Happens When You Build a Webapp?

Let me trace through the actual scenario. The user builds a webapp with FA.
An LLM agent is writing tests for the webapp. It loads this skill.

### Scenario A: Universal skill (current rewrite)

Agent sees: "For every observable signal, BOTH the producer and consumer must
be verified."

Agent thinks: "OK, so in this webapp... what's an observable signal? HTTP
responses? Database writes? Log messages? All of them?"

The agent has to DECIDE what counts as an "observable signal" before it can
apply the rule. This is an unguided decision. Different agents will make
different choices. Some will skip the rule entirely because it's too vague.

### Scenario B: FA-specific skill with concrete examples

Agent sees: "For every EventType, BOTH the output.emit() call and the
_handle_X() handler must be verified."

Agent thinks: "This webapp doesn't have EventType or output.emit(). But the
PATTERN is clear: for every signal my system produces, I need to verify both
the code that produces it and the code that handles it. My webapp has HTTP
endpoints — so I need to verify the route handler (producer) and the client
response processing (consumer)."

**The agent in Scenario B makes the SAME deduction but with MORE confidence.**
The concrete FA example provides a template that the LLM can instantiate.
The abstract universal rule provides a principle that the LLM has to
interpret.

LLMs are excellent at analogical reasoning. They don't need abstract language
to transfer patterns across domains. They need CONCRETE EXAMPLES that
demonstrate the pattern in one domain, from which they can generalize.

---

## The Cookbook Analogy

A good cookbook doesn't say: "Apply heat to protein until coagulation occurs."
It says: "Cook the chicken until the internal temperature reaches 165°F."

The first is universal (applies to all proteins). The second is specific
(applies to chicken). But the second is VASTLY more useful because:
1. You know exactly what to do
2. You can generalize the pattern (apply to fish → 145°F)
3. The abstract version requires domain knowledge to interpret

The rewritten skill reads like the first version. The original reads like
the second. The second is better for EVERY user of the skill.

---

## What I Should Have Done

The gap fixes are essential. The universality pass was a mistake. The correct
approach:

1. **Keep FA-specific language as the NORMATIVE text.** The rules should speak
   directly to the FA codebase. This is the primary use case. The skill should
   be immediately actionable without translation.

2. **Add brief universal-principle PREFIXES** — one line before each FA-specific
   rule that states the universal pattern. This gives the webapp agent a hook
   for pattern matching without diluting the FA-specific guidance.

3. **Add an "Adaptation Guide" at the end** — a short section that explicitly
   maps FA-specific concepts to their universal counterparts, with example
   translations for common project types (webapp, data pipeline, CLI tool).

Format per section:

```text
UNIVERSAL: For every observable contract, verify both producer and consumer.

FA RULE: For every EventType literal in output.py, verify BOTH:
  - output.emit(OutputEvent(type="X")) exists in production code (producer)
  - _handle_X() exists in ConsoleRenderer (consumer)
Consumer-only test is theater — it proves a dead handler works.
```

This way:
- FA agent reads the FA RULE and acts immediately (no translation)
- Webapp agent reads the UNIVERSAL prefix, understands the pattern, and maps
  it to its own domain using analogical reasoning from the FA example
- Both agents get value without cognitive overhead

---

## Verdict

| Aspect | Before rewrite | After gap fixes | After universality pass |
|--------|:---:|:---:|:---:|
| Kill-check correctness | ❌ ambiguous | ✅ targets producer | ⚠️ correct but abstract |
| Two-sided contract | ❌ missing | ✅ added | ⚠️ correct but abstract |
| Path inventory | ❌ missing | ✅ added | ⚠️ correct but abstract |
| Matrix coverage | ⚠️ declared only | ✅ enforced | ⚠️ correct but abstract |
| Immediate actionability | ✅ FA-specific | ✅ FA-specific | ❌ requires translation |
| Webapp adaptability | ⚠️ needs inference | ⚠️ needs inference | ⚠️ needs inference |
| Length | 542 lines | ~600 lines | 825 lines |

**The gap fixes are a clear improvement. The universality pass is a regression
for the primary use case and a marginal improvement for other use cases.**

The webapp agent benefits MORE from seeing a concrete FA example it can
generalize than from seeing an abstract principle it has to interpret.
LLMs transfer patterns through analogical reasoning, not through abstraction.

---

## Recommended Action

Revert the universality pass. Rewrite the skill with:
1. All 10 gap fixes intact (two-sided contract, path inventory, etc.)
2. FA-specific language as the normative text (immediately actionable)
3. Universal-principle prefixes (one line per section, for pattern matching)
4. Adaptation guide at the end (explicit concept mapping for other projects)
5. FA invariants kept as-is (user confirmed this decision)

This gives the best of both worlds: concrete actionability for FA development
AND transferable patterns for other projects, without the cognitive overhead
of abstract language.
