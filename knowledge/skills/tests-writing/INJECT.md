---
name: tests-writing-inject
description: Test-class ladder, producer kill-check, and the anti-theater minimum for one slice.
---

Derived from `SKILL.md` §1-§3. `SKILL.md` is SSOT; this is the injected subset.

## CLASS LADDER (Pyramid A)

| Class | Boots | Use when | Product proof? |
| :--- | :--- | :--- | :--- |
| **C0 Unit** | Isolation | Pure helpers, parsers, estimators | Incomplete alone |
| **C0p Property** | Many inputs | Thresholds, containment, parse robustness | Pair with C1 |
| **C1 Composition-root** | Real factories | **Default for product behavior** | Yes (kill-check on PRODUCER) |
| **C2 CLI smoke** | `fa` / `_cmd_*` | Argv->factory wiring, exit codes | Yes for CLI-only claims |
| **C3 Security** | Gate + adversarial inputs | Sandbox, secrets, permissions | Yes with adversarial cases |
| **C4 Mutation** | Per `mutation-clearing` | After survivors | Adequacy layer after C1 |

Pick: session/product/loop claim -> C1 (C2 if CLI-only). Pure helper -> C0/C0p.
Security boundary -> at least one C3 adversarial case.

**Split rule:** mock LLM I/O; exercise the real registry, hooks, budget, and
prompt assembly under test. Mock external I/O, not roots.

## PRODUCER KILL-CHECK (the load-bearing rule)

Kill-check targets the **PRODUCER** call site, never the consumer handler.
Removing the producer must make the named test **fail**. If the producer call
does not exist in production code, the feature is L0 — not wired, not shipped.
A dead handler proves nothing.

## EDGE KILL-CHECK (the second load-bearing rule)

The producer mutant proves *works if called*. It never proves *is called*.

```text
BODY mutant    remove the unit's own producer call/branch   -> test fails
EDGE mutant    remove the caller's call into the unit, or the composition
               line that binds the port to its implementation -> test fails
```

- A unit whose only caller is its own test is **L1**, not L3 — the test is a
  consumer of the unit, not the root that ships it.
- Before claiming L3, grep for a production caller outside the unit's own
  package. Empty result = write the test against the caller, or state the gap.
- Every new port/Protocol must name its **production supplier**: the function
  that constructs and injects it. A port only tests construct is not integrated.
- Never delete working production code in the same change that introduces its
  replacement unless that change also binds the replacement at a real
  composition site (expand → prove → contract).

## DOUBLES DO NOT IMPLEMENT PRODUCT LOGIC

A double must not re-implement the algorithm it stands in for (writer, lock,
CAS, validator, renderer). If the double has to re-derive the logic, the
production path has no real consumer: report that as a finding, do not hide it
behind a mock and call the suite green.

## ANTI-THEATER MINIMUM (all apply to a C1)

1. **Existence pre-check** — grep proves the producer call site exists in
   production code. Vacuous kill-check = not shipped.
2. **Kill-check on producer** — removing it fails this test.
3. **Observable side effect** — event `kind`+fields, outcome, exit code,
   provider `call_count`, or FS effect. **Never "no exception".**
4. **Live-path proof** — exercise the real composition root; constructing the
   class alone is incomplete.

## TWO-SIDED LAW

For any observable signal, name and test BOTH producer and consumer. A
producer with no consumer (or the reverse) is an incomplete contract: complete
it, or defer the missing side explicitly.

## E2E LIVE-RESULT AUTHORITY

The planner records cases, local/live oracles, host prerequisites, evidence paths,
and the run sheet before coding. The coder supplies only source-backed handoff
facts/proposals; the planner finalizes host instructions from actual deployment
facts; an independent reviewer completes the manual checklist before
fixture/helper work. No test, harness, evaluator, or coder assigns live `PASS`;
local evidence is not deployed evidence.

## ORACLE RANKING (prefer the top)

event kind+fields > outcome/exit code > tool trajectory > provider
call_count/tokens > FS effect > deny-reason code > free text (never sole oracle).
