---
name: tests-writing-inject
description: Test-class ladder, producer/edge kill-checks, and anti-theater minimum.
---

Derived from `SKILL.md` §1–§3; that file is SSOT.

## CLASS LADDER (Pyramid A)

- **C0 Unit:** isolation; pure helpers/parsers/estimators; incomplete alone.
- **C0p Property:** many inputs; thresholds/containment/parse robustness; pair with C1.
- **C1 Composition-root:** real factories; default for product behavior; kill-check producer.
- **C2 CLI smoke:** `fa`/`_cmd_*`; argv→factory and exit codes; sufficient for CLI-only claims.
- **C3 Security:** gate plus adversarial inputs; security boundaries need an adversarial case.
- **C4 Mutation:** follow `mutation-clearing`; adequacy layer after C1.

Choose C1 for session/product/loop claims (C2 if CLI-only), C0/C0p for pure helpers, and C3 for security boundaries. Mock LLM and external I/O, not roots; exercise the real registry, hooks, budget, and prompt assembly under test.

## PRODUCER AND EDGE KILL-CHECKS

Target the production producer call site, never only its consumer handler: removing it must fail the named test. A missing production call means L0—not wired or shipped. Producer proof says “works if called,” not “is called”; remove the caller call/composition binding as a separate `EDGE mutant` and require failure.

- A unit whose only caller is its test is L1, not L3. Before L3, grep for a production caller outside its package; empty means test the caller or state the gap.
- Every new port/Protocol names its production supplier (constructor/injection). Test construction alone is not integration.
- Never delete working code with its replacement unless the same change binds the replacement at a real composition site: expand → prove → contract.

## DOUBLES DO NOT IMPLEMENT PRODUCT LOGIC

A double must not reimplement its algorithm (writer, lock, CAS, validator, renderer). If it must, production lacks a real consumer: report the gap; do not hide it behind a mock and call the suite green.

## ANTI-THEATER MINIMUM (all apply to C1)

1. Existence pre-check: grep proves the production producer; a vacuous kill-check is not shipped.
2. Producer kill-check: removing it fails this test.
3. Observable effect: event kind+fields, outcome, exit code, provider call count, or filesystem effect—never “no exception.”
4. Live-path proof: exercise the real composition root; constructing a class alone is incomplete.

## TWO-SIDED LAW

Name and test both producer and consumer for every observable signal. Either side missing is an incomplete contract: complete it or explicitly defer the missing side.

## E2E LIVE-RESULT AUTHORITY

Planner records cases, local/live oracles, host prerequisites, evidence paths, and run sheet before coding. Coder supplies only source-backed handoff facts/proposals; planner finalizes host instructions from actual deployment facts; independent reviewer completes the manual checklist before fixture/helper work. No test, harness, evaluator, or coder assigns live `PASS`; local evidence is not deployed evidence.

## ORACLE RANKING (prefer higher)

event kind+fields > outcome/exit code > tool trajectory > provider call_count/tokens > filesystem effect > deny-reason code > free text (never sole oracle).
