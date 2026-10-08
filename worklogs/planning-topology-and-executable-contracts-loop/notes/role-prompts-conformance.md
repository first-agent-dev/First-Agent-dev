# Role-prompt conformance — exact text to insert (banked, not merged)

**Status: banked (operator decision 2026-09-09); implement per owner** — planner→I01,
coder→I03, eval→I04. Prompts live at `src/fa/inner_loop/prompt.py`; line anchors @ tip
`0e08ece` (re-verify before editing). All inserted text is written in the same
"do this exactly" style the schema §1 requires.

## All roles (insert in each of PLANNER / CODER / EVAL system prompts)

```
## Harness control
- You run inside the harness. Touch only the files your current task names.
- Do not edit increments/*.md, ledger.md, or notes/ unless the task names that file.
- STEP# checkboxes and CT# statuses are updated by the harness. Do not update them.
```

## Planner (PLANNER_SYSTEM_PROMPT, :45) → I01

Replace the `S#`-native step/plan wording with:

```
## Plan grammar
- Write plans in the grammar of notes/artifact-schema-and-grammar.md §4.
- Use `## SLICE<n>:`, `- [ ] STEP<n>:`, `CT<n> [FUNCTIONAL|CONSTRAINT|PRESERVATION]:`,
  `TESTS:`, `STEPS: prescriptive|outcome`, `DEPS:`. Never `S#`.
- Every `CT#` is covered by a test named in its slice's `TESTS:`.
- Every `prescriptive` `STEP#` carries an `(exit: …)`.
- Write steps as exact imperatives with file:line targets. Put rationale in notes/, not in
  the plan.
```

## Coder (CODER_SYSTEM_PROMPT, :533) → I03

Replace the "mark it `[x]`/`[>]`" line (:648) and add:

```
## Scope
- The increment plan (increments/*.md) and ledger.md are not yours. Do not edit them.
- Edit only the files named in your scoped brief (`section(SLICE#)`).
- Report steps completed, checks passed, and deviations in your final message. The harness
  ticks the plan; you do not.
```

## Eval (EVAL_SYSTEM_PROMPT, :685) → behavioral now, ledger wiring in I04

```
## Facts vs judgment
- Exit codes, test counts, and diffs come from the harness. Do not assert an exit code you
  did not observe.
- Judge intent and workmanship on the scoped diff and the contracts; emit the route verdict.
- Do not edit code, the increment, or notes.
```

(I04 only) Eval appends one EVIDENCE entry per slice to `ledger.md` (schema §5). Until the
ledger writer exists, keep the PR-draft review summary as eval's durable record (:854).

## Rule

Prompts state behavior (ownership, scope, harness control). The schema states format.
Rationale lives in notes/. One source of truth each; do not duplicate the schema in prompts.

---

# Addendum — merged from the bridge brief, 2026-10-06

One bank, not two. Owners unchanged (E45/E47): planner grammar → I01, coder behaviour → I03,
eval ledger wiring → I04. Rationale: `notes/decisions-qa-2026-10-06.md`.

## Planner → I01 (lands with SLICE1b)

- Emit schema §4 sections directly: `## SLICE<n>:`, `STEPS:`, `DEPS:`, `INTENT:`,
  `CONTRACTS:` with `CT<n> [CLASS]:`, `TESTS:`, a verify fence, `- [ ] STEP<n>: … (exit: …)`.
- Emit a `## Grounding` block for conventions, scope-outs, assumptions and risks. It is prose
  and is never parsed. Its first line states what you understood the request to be and what you
  deliberately excluded.
- Give every `CONSTRAINT` contract one rationale line naming the wrong implementation it
  catches.
- The mechanical self-checks move out of the prompt into the pre-check. Do not restate them.

## Coder → I03

- Do not tick `STEP#` boxes; the harness owns them (E44 — `prompt.py:648` currently says
  otherwise and must change *in I03*, not before).
- Recon budget and stop conditions as drafted in the bridge brief.
- **Delivery condition, not a blocker:** the line *"the harness runs the acceptance checks; you
  do not re-run them"* is correct only once the I02/I03 gate exists. Ship it in the same
  change-set as the gate. The operator's harness sees changes only during live e2e runs, so e2e
  is the designated place this would surface if the order were wrong.
- Retry context: a clean context plus a typed attempt record, **built mechanically** — parse the
  test and lint output, extract the assertion diff, the failing test id and one `file:line`.
  Never an LLM summary of the transcript: a hallucinating summariser makes the coder repair a
  defect that never happened. No fixed line cap as a rule; truncation is a last resort. Per E60
  the record is a `BlackboardEntry`, not a new type. Carry `tree_hash` and the test version, and
  sanitise tracebacks and fenced blocks before sending — provider WAFs reject raw ones, and the
  rejection looks like a model failure.

## Eval → I03 / I04

- The `S#` token in `prompt.py` (`- S1: PASS`) is overloaded **three** ways: the planner's step
  vocabulary, the controller's slice vocabulary via `validate_slice_ids`, and the eval's verdict
  vocabulary. Whoever implements this must disambiguate all three, not two.
- L2 verdicts cite **test ids**, not diff hunks — hunks rot on rebase.

---

## Banked for I04 — pinned invariants re-injected on every call

Drafted on 2026-10-06 as I01/SLICE5 from bridge R2, then moved out: the roadmap has scheduled
"pinned invariants" under I04 since it was written, the work edits prompt composition rather than
plan grammar, and it consumed `contract_class` before I02 — that accessor's first named consumer —
exists, which is exactly the inversion SD-B forbids (ledger E79). Nothing below is lost; it is
banked so I04's planner starts from it instead of rediscovering it.

**Intent.** The contracts the coder must not violate survive context compaction, because they are
re-injected rather than remembered.

**Contracts, as drafted** (renumber when I04 is planned — these ids are released back to the pool):

- `[FUNCTIONAL]` a pinned-invariants block is registered in `INJECTION_SPECS` and appears in every
  composed coder prompt, behind a `FeatureFlags` field.
- `[CONSTRAINT]` the assembled block is capped at roughly 1.5K tokens; past the cap the oldest
  non-`CONSTRAINT` entries drop first and each drop is logged. Catches: an insurance mechanism
  quietly eating the context budget it exists to protect.
- `[PRESERVATION]` the cacheable prompt prefix is byte-identical before and after, proven by a
  golden-file snapshot rather than by inspection. Catches: a silent prompt-cache miss that
  surfaces only as a cost regression weeks later.

**Two dependencies I04 must honour, both discovered after the slice was drafted:**

1. The block is populated with the current slice's `CONSTRAINT`-class contracts **verbatim**. That
   requires contract text to be the *whole* entry, not its first line — I01/CT18 now delivers
   that, but at 2f6b8c1 `_section_contracts` truncates at the first line and the rationale that
   makes a constraint reviewable is exactly what would have been dropped (ledger E73). Do not
   build this before I01 lands.
2. `contract_class` must have shipped **and** have a live consumer in I02 first. If I04 is the
   accessor's only reader, SD-B says the accessor should not have been built in I01.
