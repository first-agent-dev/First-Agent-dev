---
compiled: 2026-05-25
applies_to:
  - "knowledge/skills/pr-creation/SKILL.md (FIX intent + anti-shallow-fix gate — operational rule)"
  - "AGENTS.md PR Checklist rule #12 (load-directive for the skill)"
  - "knowledge/project-overview.md §1.2.5 (compliance-by-construction — declarative principle)"
  - "Any future FIX-class PR touching `src/fa/**` where the LLM had a degree of freedom on a spec-bearing decision"
status: accepted
---

# AP-003 — Shallow fix without named mechanism

> Catalog entry for the *prospective* anti-pattern that
> [`knowledge/skills/pr-creation/SKILL.md`](../skills/pr-creation/SKILL.md)
> (loadable skill carrying the operational rule, loaded via
> [`AGENTS.md` §Loadable skills (PR-creation load-directive)](../../AGENTS.md#loadable-skills))
> + [`project-overview.md` §1.2.5 anti-shallow-fix gate](../project-overview.md#125--compliance-by-construction-failure-observable)
> are forcing-against. AP-001 captures a backward-looking worked
> incident; AP-003 is the **forward-acting** companion — fires on
> every PR with `INTENT: FIX` before the diff lands. Evidence-block
> is **synthetic** at file-compile date (2026-05-25); replace with
> the first real escalation captured by the hook in PR B.

## Symptom

A module M emits **wrong-shape outputs in case C** (a category of
inputs, classifier outcomes, or downstream consumers' assumptions).
An LLM-driven session observes the failing test or the user-visible
mis-behaviour and proposes a **call-site guard** that filters /
clamps / normalises the wrong-shape output **at the consumer side**.
The fix passes every quick check — failing test now green, no other
test regresses, diff is one line × one file — but silently leaves M
**still emitting wrong-shape outputs**, because:

- The producer-site **degree of freedom** (which spec-bearing
  decision the LLM had freedom on) is **not named**.
- The **deterministic mechanism** (the function / type / constant /
  schema / exit-code contract closing that degree of freedom) is
  **not cited**.
- Every other consumer of M's outputs that the patch did NOT touch
  still sees the wrong-shape values; the next failing test reads as
  «a different bug», when it is the same bug surfacing at a
  different consumer.

The PR description carries `INTENT: FIX / CLASS: REPAIR / INVARIANT:
M emits well-shaped outputs in case C` — three correctly-filled
lines, all true individually, none of which catches that M itself
still emits the wrong shape.

## Wrong shape (synthetic)

> **Synthetic example.** No real incident has been catalogued yet —
> AP-003 lands as the prospective sibling of AP-001 so the
> `prepare-commit-msg` / `commit-msg` hook in PR B has a real
> anti-pattern target on day one. The first real escalation captured
> by the hook will replace the synthetic block below. Synthesised
> from the same producer-vs-consumer-site pattern AP-001 §Right
> shape rejects (R-8 «smoke `.fa/` relocation»).

**Hypothetical scenario.** ADR-7 §5 declares: «`ToolRegistry.dispatch`
returns `ToolResult.fail("invalid_params", ...)` on JSON-Schema
validation failure with `retryable=true`». A new tool `fs.move_file`
ships with an `overwrite: bool` parameter mistakenly typed in the
schema as `string` (`{"type": "string"}`). At runtime,
`fs.move_file({"path": "...", "overwrite": "yes"})` passes validation
(string is a string) but the handler then does `if params["overwrite"]
== True:` which is always `False` for any string — so `overwrite=yes`
is silently treated as `overwrite=false`. The tool succeeds
visibly but writes nothing.

**The wrong-shape fix.** The contributor adds at the handler's first
line:

```python
def handler(params: Mapping[str, object]) -> ToolResult:
    if params.get("overwrite") in ("yes", "true", "1", True):
        params = {**params, "overwrite": True}
    ...
```

PR description:

```text
INTENT: FIX
CLASS: REPAIR
INVARIANT: Affects: ADR-7 §5 fs.move_file overwrite semantics
DEGREE-OF-FREEDOM CLOSED: handler now coerces string-ish overwrite values to bool
DETERMINISTIC MECHANISM: in-tuple membership check at src/fa/inner_loop/tools/move_file.py:42
```

Both anti-shallow-fix gate fields filled. `path:line` citation
resolvable. Hook passes. Test passes. Looks fine.

**What actually broke.** The producer-site degree of freedom is **the
schema typing**, not the handler's coercion. The wrong-shape fix has:

- Named «coerce string-ish overwrite values to bool» as the
  degree-of-freedom-closed — but that **moves** the freedom from
  consumer (the handler) to a slightly-different consumer (the
  coercion list). The schema still permits ANY string; tomorrow's
  contributor invents a new truth-string and the bug returns.
- Named `src/fa/inner_loop/tools/move_file.py:42` as the
  deterministic mechanism — but the `path:line` cited IS the call-
  site guard itself. The mechanism cites the diff that introduced
  it; the citation is **tautological** (string-equal modulo
  whitespace with `DEGREE-OF-FREEDOM CLOSED`'s wording).
- Every other tool with a similar schema bug (untyped boolean
  parameter mis-typed as string) still has the same shape; the
  fix does NOT touch the JSON-Schema validation invariant.

The PR mechanism-check passes presence and `path:line` resolution but
the **tautology check** catches it: the reviewer or the hook's
post-PR-open audit notices `path:line` points back at the same line
the diff added, and the PR is downgraded to `CLASS: WORKAROUND`
+ AP-003 catalogue.

## Right shape (synthetic)

**The right-shape fix** moves the discipline to the producer site
(the schema) and makes the bug structurally impossible:

```python
# src/fa/inner_loop/tools/move_file.py
input_schema={
    "type": "object",
    "required": ["path", "overwrite"],
    "properties": {
        "path": {"type": "string"},
        "overwrite": {"type": "boolean"},   # was "string"; the wrong-shape fix
    },                                       # never touched this line.
},
```

PR description:

```text
INTENT: FIX
CLASS: REPAIR
INVARIANT: Affects: ADR-7 §5 fs.move_file overwrite type contract
DEGREE-OF-FREEDOM CLOSED: schema accepted any string for overwrite; handler had
  to choose between truth-string sets, which is a spec-bearing decision the
  LLM should not make.
DETERMINISTIC MECHANISM: input_schema.overwrite.type == "boolean"; JSON-Schema
  Draft 2020-12 validator rejects non-booleans at registry.dispatch boundary
  before the handler runs. src/fa/inner_loop/tools/move_file.py:38
```

Why this is right-shape:

- `DEGREE-OF-FREEDOM CLOSED:` names the **producer-site** decision
  (schema typing) the LLM previously had freedom on. The previous
  wrong-shape fix had freedom on «which truth-strings to accept»;
  this fix removes the freedom entirely (no string is acceptable).
- `DETERMINISTIC MECHANISM:` cites the **schema clause** that closes
  the freedom — a single line; reviewer can verify in three
  seconds that `move_file.py:38` is the schema typing, not the
  coercion-list line.
- The mechanism is **distinct** from the degree-of-freedom-closed
  text (no tautology); the citation resolves at a producer-site
  line, not a consumer-site guard.

## Why the wrong shape dominates

A **cost-asymmetry trap**, sibling to AP-001's. There are three
shapes for any FIX-class diff:

1. **REPAIR with named mechanism** — close the producer-site degree
   of freedom; cite the type / schema / constant / contract that
   makes the bug structurally impossible. Hard. Requires
   understanding the failure mode at the producer site; multi-line
   diff with named anchor.
2. **REPAIR with tautological mechanism** — name a degree of freedom
   you didn't actually close, cite a `path:line` that's the same
   diff. Cheap. PR description LOOKS correct; the tautology is
   visible only on a careful re-read.
3. **No-mechanism repair** — add a guard / coerce / clamp / filter
   at the call-site and don't bother naming the degree of freedom
   or the mechanism. Caught by the hook's structural check on
   non-empty + non-`<fill me>` fields.

An LLM without a forcing function defaults to **shape 2** on FIX
PRs, because:

- Shape 2 looks like shape 1 locally — both have «two filled fields
  with a `path:line` citation».
- The consequence (producer-site freedom still open, bug still
  latent in other consumers) is invisible unless the agent re-reads
  the producer-site code.
- Heuristics that any reasonable session uses — minimal-diff,
  one-test-flips-green, no-other-test-regresses — all reward
  shape 2.

The asymmetry the gate exploits: shape 1's `path:line` is **distinct
from the diff's own added line** (cites the producer-site type /
schema / constant); shape 2's `path:line` is **the diff's own
added line** (cites the call-site guard). The two are visually
distinguishable in two seconds — the tautology check is the cheap
catch.

Adding rule #N+1 to [`AGENTS.md`](../../AGENTS.md) («don't paper
over producer-site bugs with consumer-site guards») fixes nothing —
it competes for attention with rules 1..N. **Action-count drift
dominates rule-count drift in weaker LLMs**; the structural fix
mechanises the discipline in the `prepare-commit-msg` hook (the
agent fills placeholders; the citation requirement makes content-
meaningless mechanism strings structurally impossible).

## Detection

Three layers, ranked by leverage-per-token. Layer 1 + Layer 2 land
with PR B (`src/fa/hygiene/pr_intent.py` + git hooks); Layer 3 is
documentary and review-time.

1. **`prepare-commit-msg` skeleton (Layer 1, deepest).** For
   `INTENT: FIX` PRs, the hook pre-populates the commit-msg buffer
   with:

   ```text
   INTENT: FIX
   CLASS: REPAIR | RELAX | WORKAROUND   <fill me — pick one>
   INVARIANT: Affects: <fill me — one sentence citing ADR-N §X>
   DEGREE-OF-FREEDOM CLOSED: <fill me — one sentence>
   DETERMINISTIC MECHANISM: <fill me — one sentence ending with `repo/file.ext:line`>
   ```

   Cognitive load drops from «remember the anti-shallow rule» to
   «fill the placeholders». Mechanism: pure A15 «loader IS the
   rule» — the hook's pre-population IS the policy.

2. **`commit-msg` validator (Layer 2, structural check).** Before
   the commit lands, the validator runs four checks and returns
   ALL violations in one pass (A21 «all violations, not first»):

   - `DEGREE-OF-FREEDOM CLOSED:` is non-empty, not `<fill me>`, not
     blank-after-trim.
   - `DETERMINISTIC MECHANISM:` is non-empty, not `<fill me>`, not
     blank-after-trim.
   - `DETERMINISTIC MECHANISM:` ends with a `repo/file.ext:line`
     reference that resolves against the staged tree OR is
     explicitly `n/a (reason)`.
   - The two fields are NOT string-identical modulo whitespace
     (tautology check).

   A violation hard-fails the commit. Compliance-by-construction at
   the structural level; semantic correctness is reviewer concern.

3. **Review-time prompt (Layer 3, semantic catch).** Single question
   in the PR review carrier (Agent Review prompt, PR template,
   self-review checklist):

   > «Does `DETERMINISTIC MECHANISM:` cite the **producer site**
   > (type / schema / constant / contract that makes the failure
   > impossible) or the **consumer site** (a guard / coerce / clamp
   > that the diff just added)? If consumer-site, escalate to
   > `CLASS: WORKAROUND` and link AP-003.»

   Catches what Layer 2's structural check missed. One sentence, no
   implementation cost.

## Linked-ADR / Linked-rule

- [`knowledge/skills/pr-creation/SKILL.md`](../skills/pr-creation/SKILL.md)
  — `INTENT: FIX` clause + anti-shallow-fix gate clause (relocated
  from AGENTS.md §PR Intent Classification 2026-05-26 — PR A';
  load-directive lives at [`AGENTS.md` §Loadable skills (PR-creation load-directive)](../../AGENTS.md#loadable-skills)).
  AP-003 is
  the catalogued anti-pattern the gate is forcing-against.
- [`project-overview.md` §1.2.5 anti-shallow-fix gate](../project-overview.md#125--compliance-by-construction-failure-observable)
  — declarative principle. AP-003 is the operational worked-history
  for the gate.
- [`ADR-10` §1 I-1 single-source-of-truth classifier](../adr/ADR-10-deterministic-harness-invariants.md#1-the-invariants-i-1i-5)
  — the structural form of the anti-shallow-fix gate is itself an
  I-1-compliant classifier (the `path:line` citation IS the rule;
  no LLM judgement on whether the citation is meaningful).

## Evidence

> **Status: synthetic — no real worked-history at file-compile date.**
> Forward-acting placeholder per AP-001 evidence-block convention.
> First real escalation captured by the `prepare-commit-msg` /
> `commit-msg` hook in PR B (`src/fa/hygiene/pr_intent.py`) will
> replace the synthetic example above with a verifiable commit SHA /
> PR number / worked-history paragraph.

- **Synthetic wrong-shape example:** the `fs.move_file` schema-vs-
  handler-coercion scenario above (§Wrong shape). No commit SHA;
  the example exists only in this file.
- **Synthetic right-shape repair:** the corresponding schema-typing
  fix in §Right shape above. Again, no commit SHA — illustrative.
- **External anchor (independent rediscovery):** «producer-site
  vs consumer-site fix» is a long-running discipline in OSS agent
  stacks; AP-003's specific shape (mandatory `repo/file.ext:line`
  citation that resolves against the staged tree, with a tautology
  check against the degree-of-freedom-closed field) is novel to FA
  as far as the 2026-05 nine-repo synthesis in
  [`research/fa-abc-synthesis-deep-dive-2026-05.md`](../research/fa-abc-synthesis-deep-dive-2026-05.md)
  has surveyed.
- **Pre-existing FA anchor:**
  [`AP-001` §Why the wrong shape dominates](./AP-001-spec-bypassing-workaround.md#why-the-wrong-shape-dominates)
  lines 92–119 — the action-count argument AP-003 inherits. AP-001
  is the backward-looking worked incident; AP-003 is the
  forward-acting prospective sibling.
- **Decision trail (chosen vs rejected branches for AP-003 itself):**
  [`exploration_log.md` Q-15](../trace/exploration_log.md#q-15--how-does-fa-classify-the-intent-of-a-pr-and-how-does-it-enforce-the-anti-shallow-fix-gate-2026-05-25)
  §Rejected — «PR-description-only enforcement (no hook)»;
  «standalone §1.2.6 anti-shallow principle»; «keep §Change
  Classification + add ADR-CREATE exception clause»; «single-intent
  no-sub-classifier (delete REPAIR/RELAX/WORKAROUND entirely)»;
  «7-intent taxonomy with separate ADR-CREATE / ADR-AMEND».
