---
name: feature-planning-inject
description: Per-slice implementation ceremony — before-edit gate, edit packet, after-edit gate, stop rule.
---

Derived from `SKILL.md` §9-§12. `SKILL.md` is SSOT; this is the injected subset.

## BEFORE EDITING GATE

State, before any edit:

- Current source-verified behavior: `<file:symbol findings, or "absent after grep">`
- Plan contract and gap IDs addressed by this slice: `GAP#`, `CT#`, `S#`
- Exact files allowed to change: `<paths>`
- Blocking questions: `none`, or `Q#: <question> blocks S# because <reason>`

If blocking: STOP. Do not edit. Append the `Q#` with full explanation to the
active plan artifact and to your response.

## EDIT PACKET `E# / S#`

One packet per edit. Do not bundle unrelated contracts.

- What idea is implemented now: `<one concrete idea>`
- Concrete intent: `<user/system outcome>`
- Current behavior -> target behavior: `AS-IS:` `<source-verified>` / `TO-BE:` `<machine-checkable>`
- Exact code mechanism: `<file:symbol branch/call/schema/route>`
- Degree of freedom closed: `<what could vary before and cause the bug/risk/scope leak>`
- Deterministic mechanism: `<code/schema/gate that makes the bad state impossible or observable>`
- Production best practice: `<minimal safe mechanism; reuse/stdlib rationale>`
- Failure behavior: `<errors, deny, fallback, rollback, idempotency, cleanup>`
- Definition of Done: `<observable state/artifact/contract>`
- Negative proof: `removing <producer> makes <T#> fail`
- Tests-writing class: `C0 | C0p | C1 | C2 | C3 | C4`
- Producer kill-check target: `<exact production call site/branch/write/gate>`

## AFTER EDIT GATE

Run and report actual output, not a summary:

- Targeted tests: `$ <command>` + real output
- Static checks on changed files: `$ <command>` + real output
- Diff inspection: `$ git diff -- <files>`
- Contract status: `GAP#`/`CT#`/`T#` -> PASS/FAIL because `<evidence>`

Never mark complete from "no exception". State the positive oracle and the
negative-proof target. If tests fail, classify: implementation bug, test/oracle
bug, plan mismatch, stale preflight, or new blocking `Q#`.

## MUTATION / KILL-CHECK

After a big chunk, or before declaring shipped: remove the producer call or
invert the key branch, rerun the named tests, confirm they fail, restore.
A surviving mutation means a weak oracle — strengthen before ship.

## STOP RULE

If implementation reveals a new policy choice, STOP and promote it to a `Q#`
with explanation. Do not decide it silently.
