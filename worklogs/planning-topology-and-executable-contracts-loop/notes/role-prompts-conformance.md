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
