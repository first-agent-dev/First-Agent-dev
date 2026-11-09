---
name: feature-planning-inject
description: Per-slice ceremony: before-edit gate, edit packet, after-edit gate, stop rule.
---

Derived from `SKILL.md` §9–§12; that file is SSOT.

## BEFORE EDITING GATE

Before editing, state: source-verified behavior; plan/gap IDs; exact allowed files; and blocking questions (`none` or `Q#: ...`). If blocked, STOP, append the full Q# to the active plan artifact, and report it.

## EDIT PACKET `E# / SLICE#`

One packet per edit; do not bundle unrelated contracts. Record:

- Idea implemented now; Concrete intent: user/system outcome; AS-IS → TO-BE, both source-verified and machine-checkable.
- Exact files allowed; exact code mechanism (`file:symbol` branch/call/schema/route).
- Degree of freedom closed: `<variation/risk>`; Deterministic mechanism: `<gate>`; Production best practice: minimal safe mechanism, reuse/stdlib rationale.
- Failure behavior: errors, deny/fallback, rollback, idempotency, cleanup.
- Definition of Done: observable state/artifact/contract.
- Delivery: root command; support (`rooted-by: CT#/STEP#`); user-visible outcome; cutover `none` or old producer → supplier bound at `file:symbol`, delete at `STEP<n>`.
- Tests-writing class: `C0 | C0p | C1 | C2 | C3 | C4`.
- Producer kill-check target: exact production call/branch/write/gate; removing it must fail the named test.
- Edge kill-check target: exact caller call/composition binding; removing it must fail the named test.

A unit whose only caller is its test is L1, not shipped. A port only test-constructed has no supplier: do not delete the code it should replace; expand → prove real binding → contract.

## AFTER EDIT GATE

Run and report actual output, not summaries:

- Target tests; static checks for changed files; `git diff -- <files>`.
- Reachability: `grep -rn "<new symbol>" src/ | grep -v "<own package>"`; empty means L1—name the rooting step or say SUPPORT.
- Supplier: `grep -rn "<PortName>(" src/` minus its own module; empty means no production construction—do not delete what it replaces.
- For cutovers, prove old path until delete and supplier binding before it.
- Map each `GAP#`/`CT#`/`T#` to PASS/FAIL with evidence.

Never mark complete from “no exception.” State the positive oracle and negative-proof target. Classify failures: implementation bug, test/oracle bug, plan mismatch, stale preflight, or new blocking Q#.

## MUTATION / KILL-CHECK

After a major chunk and before claiming shipped, remove the producer call or invert its key branch, rerun the named tests, confirm failure, and restore. A survivor means strengthen the oracle before ship.

## E2E EVIDENCE ROLES

Before coding, the planner records case IDs/owners, local-vs-live oracles, host
prerequisites, evidence paths, and run-sheet obligations. The coder appends only
source-verified seams/proofs/limitations and labelled proposals; it does not alter
the oracle, ownership, or live result. The planner finalizes the host run sheet
from actual host facts. An independent reviewer completes the manual checklist before
fixture/helper implementation. No harness, evaluator, or coder assigns live
`PASS`; preserve generic `READY` semantics.

## STOP RULE

If implementation reveals a new policy choice, STOP and promote it to a `Q#` with explanation. Do not decide it silently.
