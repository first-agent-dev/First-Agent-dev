# I02 — planning readiness, 2026-10-07

Written after I01's DoD walk. Purpose: say what is *ready*, what is *stale*, and what must be
**decided before a line of I02 is planned**. This is not the I02 plan; `increments/` stays
empty for I02 until the decision backlog below is cleared.

Companion documents, unchanged and still authoritative:
[`i02-handoff-verify-gate.md`](i02-handoff-verify-gate.md) (context bank, §3 design, §5
guardrails, §7 the live gate), [`verify-block-design.md`](verify-block-design.md) + the SVG
(four-phase ritual, seven-row truth table).

---

## 1. Ready: the contract boundary is live, and was executed today

Handoff §2 was written before SLICE2–SLICE4 shipped, so it described an intended interface.
Every item is now **measured against the shipped code**, not assumed:

| Handoff §2 promise | Measured result |
| --- | --- |
| `commands_for("SLICEn")` | `('uv run pytest tests/test_plan_precheck.py -q', 'uv run ruff check …')` |
| `commands_for(None)` | `()` — total ownership; nothing unowned in this plan |
| `section("SLICEn")` | `'## SLICE3: Plan pre-check (static lint, …'` |
| `tests_for("SLICEn")` | `('tests/test_plan_precheck.py',)` |
| `contract_class("CT40")` | `'FUNCTIONAL'` |
| `SliceRecord.tests_note` | `'(NEW — author it; absent at 2f6b8c1)'` — the raw annotation survives (CT33) |
| `SliceRecord.test_paths` | `('tests/test_skill_conformance.py',)` |

`SliceRecord` fields as shipped: `slice_id, intent, contracts, test_paths, steps_mode,
commands, section, tests_note`.

## 2. Two spec defects found and fixed while checking that boundary

Both were documentation, both would have misled I02's planner:

1. **`plan.steps_mode("SLICE2")` never existed.** Schema §7 wrote it as a method on `PlanIds`;
   it is a **field on `SliceRecord`**, reached as `plan.slice_records[i].steps_mode`.
   Corrected, with the old form quoted so the correction is auditable (ledger E116).
2. **`parse_slice_id` was exported but unspecified** — absent from the schema document
   entirely, as was `canonical_slice_id` from §7. Both now specified *with the reason they
   differ*: strict inside a plan, lenient only at the eval-report boundary (ledger E115).

A guard against recurrence is registered as **D8**, deliberately not built in I01.

## 3. Decision backlog — what blocks *planning* vs what blocks *implementation*

The handoff says "resolve at the I02 review, not before". That review is now.

### Blocking the plan's shape (must answer before writing slices)

| id | Question | Why it shapes slices |
| --- | --- | --- |
| **H4** | Result shape + home: new `verify.py` vs `plan_ids.py` | `plan_ids.py` is pure, stdlib-only, and a subprocess runner violates that. This decides the module boundary, so it decides the slices. |
| **H2** | `NEW` semantics: prose marker, machine token, **or derive from `HEAD`** | The third option removes the marker from the trust path entirely and changes what the fail-before filter even reads. |
| **H1** | Granularity: run each NEW test file alone for fail-before? | Decides whether the gate has one runner or two phases with different invocations. |
| **Q43** | Are the accessors allowed to be lenient? (new, from the DoD walk) | I02 is the first external caller of `commands_for`/`tests_for`/`section`. If leniency is wrong, it is cheapest to fix before there is a caller. |

### Blocking implementation only (can be planned around)

**H3** baseline storage path + lifetime · **H5** per-command timeout budget · **H7**
regression attribution scope (per-run baseline) · **CT10b** path-existence rule, already
moved here by Q39 with its three-case truth table drafted in handoff §8.

### External risk, not a question

**H6 — the S16 collision.** The tip proposes removing `.commands` as having "no consumers".
Measured today: `commands_for` still has **zero production call sites** (register row D4), so
that argument is currently *correct on its face*. I02 is the consumer that makes it wrong. If
S16 lands first, this must be re-justified against I02 rather than silently reverted (E37).

## 4. Verification rows I02 owns

From [`deferred-verification-register.md`](deferred-verification-register.md):

- **D1 — the coverage gate actually sees slices.** The highest-priority row in the register.
  It is the original defect's own failure mode: an unparseable plan made
  `workflow_controller.py:332` no-op **silently** for the whole life of I01.
- **D3 — the skill → prompt → plan → parser chain**, end to end through the real loop.
- **D4 — the read API gets its first production reader.** Every accessor stops being a typed
  promise the moment I02 calls it.
- **D5 — the prompt blocks reach the provider.** Assert at the mocked `ProviderChain.request`
  boundary that the grammar block is in the composed payload.
- **D8 — exported surface vs schema §7** guard.

## 5. Guardrails carried forward (handoff §5) — do not relitigate

No DSL for verify blocks · no fence-depth parsing · no mutation/failure-injection in the core
(that is I06) · **no `VERIFIED` from I02 alone** — it additionally needs I03's eval L2.

And the one that outranks the rest: handoff §7 specifies the **live gate I02 owes** in full —
boot `drive_session`, mock only `ProviderChain.request`, assert the slice's own commands ran
*and a different slice's did not*, and name the deletion of the `commands_for` call site as
the kill-check. A kill-check aimed at `extract_plan_ids` instead does not count: it stays
green with the gate unwired, which is exactly the condition it exists to detect.

## 6. Recommended next action

Answer the four plan-shaping decisions (H4, H2, H1, Q43) in one pass, then draft I02 against
the handoff's §3 ritual and §7 live gate. Everything else is already banked and does not need
rediscovery.

⚠️ Do not start I02 by re-reading the research note. The adoption decisions are already made
in `RESEARCH-ADOPTION-PLAN.md`, and §5 of it — "more structure is not more success" — applies
directly to a verify gate, which is the most over-engineerable component in this roadmap.
