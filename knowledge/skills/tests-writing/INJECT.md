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

## ORACLE RANKING (prefer the top)

event kind+fields > outcome/exit code > tool trajectory > provider
call_count/tokens > FS effect > deny-reason code > free text (never sole oracle).
