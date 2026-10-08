# Adversarial production review — I01, roadmap, I02 handoff (2026-10-06)

Scope: `roadmap.md`, `increments/increment-01-plan-grammar-and-extractor.md` (SLICE1b onward),
`notes/i02-handoff-verify-gate.md`. Posture: assume the plan is wrong and try to prove it, using
the live parser rather than reading. Baseline commit `2f6b8c1`.

Everything below is either **CONFIRMED** (reproduced against code or measured output) or
**SUSPECTED** (argued, not proven). All CONFIRMED items have been fixed in this commit; the
fixes are listed with each. Suspicions are recorded, not acted on.

The probe used throughout: load `src/fa/inner_loop/plan_ids.py` via `importlib` (system Python
3.11 cannot import the package — `fa.inner_loop.loop:17` uses `typing.override`) and run
`extract_plan_ids` over the real increment file.

---

## 1. CONFIRMED — CT4c was false, and false in the dangerous direction

**Evidence.** `increment-01` @ 2f6b8c1: flat `.commands` = **10**; concatenation of
`SliceRecord.commands` over all slices = **12**. Not equal.

**Cause.** `_ordered_unique` (`plan_ids.py:169–177`) is applied **globally** at `:280` and
**per-section** at `:249`. SLICE1 and SLICE2 both run
`uv run pytest tests/test_plan_ids.py -q` and `uv run ruff check src/fa/inner_loop/plan_ids.py
tests/test_plan_ids.py`; the flat field collapses those two pairs, the per-slice records keep
them. The relation is superset, never equality — and it is not even "concat minus duplicates",
because the flat field also contains prologue and increment-level blocks no slice owns.

**Why this is the most serious finding.** CT4c was classed `PRESERVATION`. A preservation
contract is read as *a statement of current behaviour that must not change*. An agent
implementing SLICE2/STEP3 ("Assert the flat `.commands` is unchanged. (exit: CT4c green.)")
writes the assertion, watches it fail, and concludes the **code** is wrong. The cheapest way to
make it pass is to re-derive `.commands` from the slice records — which changes the field's real
behaviour, drops the prologue commands, and does so while the test suite reports success. The
contract would have caused the regression it was written to prevent.

**Fix.** CT4c restated as the true superset relation, with the measurement inline and an explicit
prohibition: *no test may assert that equality*. SLICE2/STEP5 now pins the relation **and**
asserts non-equality on this very file, so the misunderstanding cannot recur silently.
Schema §7's `# retained (flat = concat of all slices')` comment carried the same false claim and
was corrected. Ledger E70.

---

## 2. CONFIRMED — CT4b specified a destination that does not exist

**Evidence.** `PlanIds` fields are exactly `slices, gaps, contracts, tests, commands,
slice_records` (`plan_ids.py:138–146`). `_slice_sections` (`:198–209`) starts at the first slice
heading, so the prologue is excluded by construction. A `verify` block placed before any slice
heading was confirmed reachable from the flat field and from **no** `SliceRecord`.
`SliceRecord.slice_id` is typed `str` (`:115`), so no `None`-keyed sentinel record is available
either.

CT4b said the block "goes to a plan-level bucket (`commands_for(None)`)" and SLICE2/STEP2 said
"implement the plan-level bucket" — neither named where it lives. The implementer must invent a
schema change mid-slice, which is precisely the decision the plan exists to have already made.

**Fix.** `PlanIds.plan_commands: tuple[str, ...]` specified in schema §7 and in CT4b, with
"`SliceRecord` is not widened and no sentinel slice id is invented" stated as a constraint so the
other two tempting designs are closed off. STEP ordering changed so the field exists before the
accessors are written. Ledger E71.

---

## 3. CONFIRMED — CT16's "same or shallower level" invites a hardcoded, wrong terminator

**Evidence.** `_SLICE_RE = re.compile(r"^#{2,4}\s+SLICE(\d+[a-z]?)\s*:", re.M)`
(`plan_ids.py:58`). Probed with `##`, `###` and `####` slice headings: all three match.

So "same or shallower level" has no fixed value. The obvious implementation — terminate on
`^#{1,2}\s` because slices in *this* increment are `##` — is correct for this file and wrong for
any increment that nests slices one level deeper, and it fails silently (the slice simply
swallows its own subsections).

**Fix.** CT16 now states the rule relative to the matched heading's own depth and names the
hardcoding as the defect to avoid, citing `plan_ids.py:58`. Schema §4's boundary rule got the
same treatment, since the schema is the specification the parser conforms to (SD-A). Ledger E72.

---

## 4. CONFIRMED — a three-way interface mismatch that silently deleted the rationale

**Evidence.** `_section_contracts` (`plan_ids.py:234`) builds contract text as
`line.split("]:", 1)[1]` — one line. Extracted from the live file:

```
CT23 [CONSTRAINT] text='every `CONSTRAINT`-class contract carries one rationale line naming the'
```

The sentence that follows on the continuation line — "Catches: a constraint nobody can review
because its intent was never written down" — is gone.

Three parts of the plan depended on each other and could not all hold:

| Where | What it required |
|---|---|
| SLICE1b / CT23 | every `CONSTRAINT` contract carries a rationale **on a continuation line** |
| SLICE2 / CT18 | id, class **and text** read from the entry's **first line only** |
| SLICE5 / STEP2 | inject `CONSTRAINT` contracts into the coder prompt **verbatim** |

CT18 and CT23 together guarantee the rationale is never in `contract.text`; SLICE5 then injects
"verbatim" text that is missing exactly the sentence that makes a constraint reviewable. Nothing
fails — the feature ships, degraded, and the degradation is invisible.

**Fix.** CT18 split the two concerns that were wrongly fused: **id and class** come from the
entry's first line (which is what prevents the real CT2/CT3 bug), **text** is the whole entry
with continuations joined. Schema §4 updated identically, naming `line.split("]:", 1)[1]` as the
specific thing not to do. Ledger E73.

---

## 5. CONFIRMED — CT17's terminator allowlist was already incomplete

CT17 ended the `CONTRACTS:` block at `^(TESTS|STEPS|DEPS|INTENT):`, a fence, a `- [ ]` item, or a
heading. SLICE1 in this same file carries a `SHIPPED:` field, added earlier in this session and
**not in the list** — a contracts block followed by `SHIPPED:` would have run on past it.

The allowlist is also redundant: every terminator it enumerates begins at column 0, and every
line that must stay inside the block is indented. One rule covers all of them and cannot go
stale.

**Fix.** CT17 and schema §4 now read: the block ends at the first non-blank line beginning at
column 0. The allowlist is explicitly rejected in the schema text with the `SHIPPED:` case as the
reason, so nobody reintroduces it. Ledger E74.

---

## 6. CONFIRMED — I01 destroyed the only datum I02 is specified to consume

**Evidence.** `_test_paths` (`plan_ids.py:212–219`) breaks out of its loop at the first token
starting with `(`. The `(NEW — author it; absent at 2f6b8c1)` annotation never leaves the parser.

`notes/i02-handoff-verify-gate.md` §2 lists `TESTS: <path> (NEW)` as part of the I01→I02 contract
boundary and states that I02's fail-before filter keys on it. No other source for NEW-ness is
named anywhere in the handoff. Taken literally, the entire non-vacuity gate — the reason I02
exists — had no input.

**Fix.** CT33: `SliceRecord.tests_note` preserves the annotation verbatim; I01 assigns it **no**
semantics, keeping the decision inside I02's remit where the handoff put it. The handoff's §2 row
and open question 2 were corrected, and a third option added that the binary framing was hiding:
derive NEW-ness from the repository (a path absent from `HEAD` is new) and treat the annotation as
an authoring hint the pre-check cross-checks — which takes the marker out of the trust path
altogether. Ledger E75.

---

## 7. CONFIRMED — nothing enforced `CT#` uniqueness, though the schema required it

Schema §4: "`CT#` IDs … are unique per increment." Pre-check CT10 covers references to
**undefined** ids; no rule covered the same id **declared twice**, and `contract_class`'s
behaviour on a duplicate was undefined — meaning its answer would depend on parse order.

Measured on `increment-01` @ 2f6b8c1: ten ids are declared more than once, three of them with two
different classes (`CT3` as both `CONSTRAINT` and `FUNCTIONAL`, likewise `CT8` and `CT11`).

Those particular duplicates are artefacts of defects 3 and 5 and will vanish when SLICE2 lands.
That is exactly why the gap is easy to miss: the symptom disappears for an unrelated reason while
the hole stays open for the next plan.

**Fix.** Pre-check CT34 (FAIL, naming both `file:line`s), a determinism clause in CT19 (first
declaration in document order wins), a drift-corpus fixture in SLICE3/STEP6, and a DoD line
stating that if any duplicate survives SLICE2 the **plan** is wrong, not the lint. Ledger E76.

---

## 8. CONFIRMED — SLICE1b's verify block did not cover the files its steps edited

SLICE1b/STEP4 edited `src/fa/inner_loop/prompt.py`. The slice's `TESTS:` was
`tests/test_skill_grammar_emit.py` and its verify block ran that file plus
`ruff check knowledge/skills`. Neither touches `prompt.py`. The step's exit check —
`grep -c SLICE src/fa/inner_loop/prompt.py` is non-zero — is satisfied by a comment containing
the word.

So the slice could be marked green with the production change unexecuted and unverified. A slice
whose verify block does not cover the files its steps edit is not a slice.

**Fix.** Split into **SLICE1b** (schema §4 + both planning skills; docs) and **SLICE1c** (the
planner prompt; code, with `tests/test_planner_emits_schema4.py` and ruff over `prompt.py`). The
`grep` exit is replaced by rendering the prompt, extracting its skeleton and parsing it, with the
reason stated inline so it is not re-weakened. SLICE4's `DEPS:` repointed to SLICE1c. Ledger E77.

---

## 9. CONFIRMED (trajectory) — SLICE5 was scope creep against this project's own roadmap

`roadmap.md:50` has scheduled **"Evidence ledger, pinned invariants, retry hygiene"** under I04
since the roadmap was written. The pinned-invariants slice was added to I01 earlier in this
session from bridge R2 without checking that row. It fails I01's own "Shippable when" (it edits
prompt composition, not plan grammar), and it consumed `contract_class` before I02 — that
accessor's first named consumer — exists, which is the inversion SD-B was created to prevent.

It also carried the last remaining `DEPS:` defect: `DEPS: SLICE1` while its STEP2 consumed
`contract_class`, delivered by SLICE2.

**Fix.** Moved to I04, contracts banked verbatim in `notes/role-prompts-conformance.md` with the
two dependencies that were discovered after it was drafted (CT18's whole-entry text; a live I02
consumer). I01 returns to six slices. The `DEPS:` defect disappeared with it rather than needing
a patch. Ledger E79.

---

## 10. CONFIRMED (method) — prose-assertion exits were testing the wrong thing

SLICE1b/STEP5's exit was "each sentence is present in both skills"; CT21's was that schema §4
"states normatively" four rules. Both are `grep`s for prose. They pass when a sentence has been
pasted, which is not evidence that the grammar the sentence describes is the grammar the parser
implements — the only property anyone cares about. They also go red on the first reword, training
the next agent to weaken them.

**Fix.** Schema §4 gains a fenced ```example increment and each skill a fenced ```skeleton; the
tests read those fences out of the Markdown, parse them with `extract_plan_ids`, and compare
against the documented result. Editing §4 without editing the parser now turns a test red. The
authoring rules that genuinely are judgement rather than lint (`STEPS:` default, `N ≤ 7`, brief
size) move into one §4 subsection titled "Authoring guidance (not checked)" that both skills link
to, so there is one copy and the pre-check is told not to key on it. Ledger E78.

---

## Suspicions — all closed 2026-10-07

> **Closure note.** Every entry below was walked with the operator and resolved; the text is
> left unedited as the record of what was suspected and why. S-a is obsolete (E104), S-b is
> CT36 (E105), S-c is CT37 (E106), S-d is CT38 and supersedes part of E78 (E107), S-e is CT39
> (E108). S-c and S-e turned out to be live defects rather than tidiness questions, and S-e's
> fix generalised into a conservation rule instead of the authoring line it was filed as.


- **S-a. SLICE2 now carries ten contracts.** Cohesive (one module, one test file) but at the top
  of the range. If I02's review finds it unwieldy, the natural cut is boundary rules
  (CT16/CT17/CT18) versus accessors (CT3/CT4/CT4b/CT19/CT20/CT33). Not split now: the accessors
  are only correct *because* of the boundary rules, and separating them invites shipping
  accessors over a parser that still mis-slices.
- **S-b. `_STEP_RE` admits `- [>]`** as a step marker; schema §6 defines only `[ ]` and `[x]`.
  Harmless drift today — the harness owns the ticks — but the vocabularies should be reconciled
  when I03 starts writing them.
- **S-c. `canonical_slice_id` maps a bare `S1b` to `SLICE1b`**, which is forgiving in the eval
  path while the plan grammar bans `S#` outright. Deliberate leniency or an escape hatch that
  will keep `S#` alive? Worth one line in I03's plan either way.
- **S-d. The `N ≤ 7` ceiling is now exactly met** (I01 has six slices after the split, and the
  split itself added one). The rule is unenforced guidance by decision; it is nonetheless worth
  noticing that the first real edit under it consumed the remaining headroom.
- **S-e. No contract covers the interaction of CT16 with a `## Grounding` subsection** placed
  *inside* a slice. Under the depth rule a `##` Grounding heading ends the slice, a `###` one does
  not. Schema §4 shows `## Grounding` as an increment-level section, which is consistent — but the
  SLICE1b/STEP3 exit as written assumes per-slice Grounding subsections. They must be `###`.
  Flagged rather than fixed because it is a one-word authoring decision for the I01 implementer.

---

## What was checked and found sound

- `DEPS:` graph after the edits: acyclic, no undefined references, every slice reachable.
- CT9 simulation (prescriptive slice with a `STEP#` block lacking `(exit: …)`): zero violations
  across all six slices, before and after the rewrite.
- Every slice carries `TESTS:`, an explicit `STEPS:` mode, and a two-command verify block.
- `extract_plan_ids` over all 15 Markdown files in the planning folder: no exceptions
  (totality preserved).
- Bridge §2's factual rows, re-verified earlier this session: all correct.
