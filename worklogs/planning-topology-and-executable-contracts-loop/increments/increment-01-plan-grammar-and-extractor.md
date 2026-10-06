---
Increment-ID: RM-planning-topology-I01
Roadmap-ID: RM-planning-topology
status: IN PROGRESS
slices: 6
shipped: SLICE1
---

# INCREMENT I01: Plan grammar & extractor

**Shippable when:** `extract_plan_ids` parses `## SLICE<n>:`, `CT<n> [CLASS]:`, `TESTS:`,
`STEPS: prescriptive|outcome`, and per-slice records; and the pre-check lints an increment
plan before any coder runs.

**Ground truth (re-verified @ 2f6b8c1, 2026-10-06 — read these before editing):**
- `src/fa/inner_loop/plan_ids.py` — `_SLICE_RE`, `SliceRecord` and `slice_records` are present
  (SLICE1 shipped in `c0a8f429`). `commands_for`, `section`, `contract_class`, `tests_for` and
  `steps_mode` are absent.
- `src/fa/inner_loop/plan_ids.py` — `_CONTRACT_RE` is `\bCT(\d+[a-z]?)\b`, applied to every line
  of a slice section (see CT17/CT18).
- `tests/test_plan_ids.py` is **367 lines**; the SLICE1/STEP3 migration is complete
  (`grep -nE '### (Step )?S[0-9]' tests/test_plan_ids.py` matches only the legacy-rejection
  assertion at `:367`). Live anchors: `:61`, `:202`, `:213`, `:264`.
- `src/fa/inner_loop/workflow_controller.py:332` and `:461` read `.slices`.
- `grep -c SLICE src/fa/inner_loop/prompt.py` is **0**. The planner emits its own runtime format,
  so a freshly authored plan parses to empty `.slices` and the coverage gate at `:332` no-ops.
  SLICE1b closes this.

**Decisions (do exactly):**
- Recognize `SLICE#` only. Do not keep an `S#` pattern and do not add a dual grammar.
- Retain the flat fields (`.slices/.gaps/.contracts/.tests/.commands`) unchanged.
- Add `slice_records: tuple[SliceRecord, ...]` beside them; do not substitute.
- Pre-rename `S#` plans are archived and parse to empty `.slices`. Accepted.
- **The authoring contract is written before the parser changes.** SLICE1b fixes the grammar in
  `notes/artifact-schema-and-grammar.md` §4 and in the skills and planner prompt; SLICE2 makes
  the parser conform to it; SLICE3 lints it. Never invent a grammar rule inside the parser.
- The planner emits schema §4 **directly**, plus a free-form `## Grounding` block. Code performs
  admission (parse, validate, default and stamp, persist) and **never infers**: anything not
  derivable by rule fails loudly back to the planner.

---

## SLICE1: New grammar tokens + per-slice records (+ migrate the existing test)
STEPS: prescriptive
DEPS: —
SHIPPED: c0a8f429 (PR #69, merged 2026-09-10)
INTENT: `plan_ids.py` parses the new grammar and builds `slice_records`, without breaking
  the flat fields or the two `.slices` callers.
CONTRACTS:
  CT1 [FUNCTIONAL]: `extract_plan_ids` populates `.slices` from `## SLICE<n>:` headings.
  CT2 [FUNCTIONAL]: `CT3 [CONSTRAINT]: …` parses with class `CONSTRAINT`; an absent bracket
    defaults to `FUNCTIONAL`.
  CT5 [FUNCTIONAL]: a slice's `TESTS:` line parses to its test path(s).
  CT6 [FUNCTIONAL]: a slice's `STEPS: prescriptive|outcome` parses; absent defaults to
    `prescriptive`.
  CT7 [FUNCTIONAL]: `PlanIds` gains `slice_records: tuple[SliceRecord, ...]`; `SliceRecord`
    is a frozen dataclass `{slice_id, intent, contracts: tuple[(id, cls, text)],
    test_paths: tuple[str], steps_mode, commands: tuple[str], section: str}`. Flat fields
    unchanged.
  CT11 [PRESERVATION]: `workflow_controller.py:332` and `:461` resolve `.slices` for a
    `SLICE#` plan; the migrated `tests/test_plan_ids.py` is green.
  CT12 [PRESERVATION]: `tests/test_plan_ids.py:202`, `:212`, `:258` pass against the live
    artifacts (increment-01), not the superseded plan.
  CT13 [CONSTRAINT]: a ```verify fence inside a ````text wrapper is extracted as a real
    command. Do not change this behavior; any doc that shows the grammar uses the ````text
    wrapper, and the pre-check is never run on such a doc.
TESTS: tests/test_plan_ids.py
```verify
uv run pytest tests/test_plan_ids.py -q
uv run ruff check src/fa/inner_loop/plan_ids.py tests/test_plan_ids.py
```
- [x] STEP1: Edit `plan_ids.py:55`. Do exactly: set `_SLICE_RE` to match `## SLICE<n>:`;
      add `_STEP_RE` for `STEP<n>:`; delete the `S#` pattern.
      (exit: a `SLICE#` fixture yields `slices=("SLICE1","SLICE2")`; an `S#`-only string
      yields `()`.)
- [x] STEP2: Add the contract-class capture and define `SliceRecord`; populate
      `slice_records` with intent, classed contracts, test_paths, steps_mode, the slice's
      verify commands, and the section span. (exit: CT2/CT5/CT6/CT7 fixtures green.)
- [x] STEP3: Migrate `tests/test_plan_ids.py`. (Anchors below are **pre-migration** and kept
      verbatim as the shipped record; the file is now 367 lines.) After it, `grep -nE '### (Step )?S[0-9]'
      tests/test_plan_ids.py` returns nothing and the file is green. Do exactly:
      - `:34` and `:38` — `PLAN_FIXTURE` headings → `## SLICE<n>:`.
      - `:63` — `test_slices_include_lettered_suffix` expects `("SLICE1","SLICE5a")`.
      - `:159` and `:181` — inline `### Step S<n>:` strings → `## SLICE<n>:`.
      - `:212` — `test_this_plan_is_conforming`: point it at
        `worklogs/planning-topology-and-executable-contracts-loop/increments/
        increment-01-plan-grammar-and-extractor.md`; assert `"SLICE1" in ids.slices` and
        `"CT1" in ids.contracts`. Do not edit the superseded plan.
      - `:202` — `test_extraction_is_total_over_repo_plans`: extend the glob to also cover
        `worklogs/*/increments/increment-*.md`.
      - `:258` — `test_real_plan_yields_its_own_verification_commands`: repoint as at `:212`;
        narrow the `real = [...]` filter to exclude only `plan_ids.py` commands; keep
        `any("ruff" in c for c in real)`.
      (exit: the grep above is empty and the file is green.)
- [x] STEP4: Add a regression test that `workflow_controller.py:332` and `:461` resolve
      `.slices` for a `SLICE#` plan. (exit: CT11 green.)
- [x] STEP5: Add a test pinning CT13. (exit: CT13 green.)

---

## SLICE1b: The authoring contract (schema, skills, planner prompt)
STEPS: prescriptive
DEPS: SLICE1
INTENT: the grammar is defined once, in schema §4 and the text that teaches it, so the planner
  emits increment sections directly and the parser has a specification to conform to.
CONTRACTS:
  CT21 [FUNCTIONAL]: schema §4 states normatively that a slice section runs from its heading to
    the next heading of the same or shallower level, that increment-level sections may follow
    the last slice, that a contract is declared only inside the `CONTRACTS:` block, and that one
    entry declares one contract with its ID and class on the entry's first line.
  CT22 [FUNCTIONAL]: the planner prompt and both planning skills emit schema §4 sections plus a
    `## Grounding` block, documented as prose and never parsed. Its mandatory first line names
    what the planner understood the request to be and what it deliberately excluded.
  CT23 [CONSTRAINT]: every `CONSTRAINT`-class contract carries one rationale line naming the
    wrong implementation it catches. Catches: a constraint nobody can review because its intent
    was never written down.
  CT24 [PRESERVATION]: the skills' other ID grammar (`GAP#`, `CT#`, `T#`, `Q#`, `RK#`) is
    unchanged; only the slice and step anchors and the new fields are added.
TESTS: tests/test_skill_grammar_emit.py  (NEW — author it; absent at 2f6b8c1)
```verify
uv run pytest tests/test_skill_grammar_emit.py -q
uv run ruff check knowledge/skills tests/test_skill_grammar_emit.py
```
- [ ] STEP1: Write the four boundary rules into `notes/artifact-schema-and-grammar.md` §4 as
      normative sentences. (exit: CT21 green.)
- [ ] STEP2: Add the `## Grounding` block to §4 and to both skills, marked "prose, not parsed",
      with its mandatory understood-and-excluded line. (exit: CT22 green.)
- [ ] STEP3: Edit `knowledge/skills/plan-authoring/SKILL.md` and
      `knowledge/skills/feature-planning/SKILL.md` so the plan skeletons and ID sections emit
      `## SLICE<n>:`, `CT<n> [CLASS]:`, `TESTS:`, `STEPS:`, `DEPS:` and the verify fence. Write
      them as exact imperatives with file:line targets and runnable exit checks (schema §1); no
      rationale inline. (exit: a fixture authored strictly from the skill text parses via
      `extract_plan_ids` with non-empty `.slices`.)
- [ ] STEP4: Edit `src/fa/inner_loop/prompt.py` so the planner's plan section emits schema §4,
      routing the Evidence, Assumptions and Risks content into `## Grounding`. (exit:
      `grep -c SLICE src/fa/inner_loop/prompt.py` is non-zero and a generated plan fixture
      yields non-empty `.slices`.)
- [ ] STEP5: Add the authoring rules that are prose, not checks: the `STEPS:` mode defaults from
      the TRIVIAL/STANDARD/LARGE classifier and the planner may override it with a one-line
      reason; `N <= 7` slices per increment, and a decomposition needing more means the
      increment is mis-scoped and must be split into smaller increments; keep a slice brief
      under roughly 1.5-2K tokens. (exit: each sentence is present in both skills.)
- [ ] STEP6: Add the rationale-line rule for `CONSTRAINT` contracts. (exit: CT23 green.)

---

## SLICE2: Per-slice accessors over the records
STEPS: prescriptive
DEPS: SLICE1b
INTENT: the parser implements the SLICE1b authoring contract and exposes the read API I02
  consumes, over `slice_records`.
CONTRACTS:
  CT3 [FUNCTIONAL]: `commands_for("SLICE2")` returns only SLICE2's ```verify commands.
  CT4 [FUNCTIONAL]: `section("SLICE2")` returns exactly SLICE2's block (heading through the
    line before the next heading of the same or shallower level).
  CT4b [CONSTRAINT]: a ```verify block before any slice heading goes to a plan-level bucket
    (`commands_for(None)`); it is never dropped or attributed to SLICE1.
  CT4c [PRESERVATION]: the flat `.commands` equals the concatenation of all slices'
    commands.
  CT16 [CONSTRAINT]: a slice section ends at the next heading of the same or shallower level,
    not at the next `SLICE` heading, so the last slice does not absorb the increment-level
    sections that follow it. Catches: the final slice silently acquiring the document tail and
    every contract id mentioned in it.
  CT17 [CONSTRAINT]: a contract is declared only inside the `CONTRACTS:` block, which runs from
    the `CONTRACTS:` line to the first later line matching `^(TESTS|STEPS|DEPS|INTENT):`, a
    fence, a `- [ ]` item, or a heading; indented continuation lines stay inside it. Catches: a
    stray contract id typed in step text becoming a contract of the slice.
  CT18 [CONSTRAINT]: one entry declares one contract, and its id and class are read from the
    entry's first line only; later lines of the entry are prose. Catches: CT2's illustrative
    example giving SLICE1 a second, differently-classed `CT3`.
  CT19 [FUNCTIONAL]: `contract_class("CT3")` returns the class declared under CT17 and CT18; an
    id declared nowhere returns `None`. Consumer: I02.
  CT20 [FUNCTIONAL]: `tests_for("SLICE2")` returns that slice's `TESTS:` paths. Consumer: I02.
TESTS: tests/test_plan_ids.py
```verify
uv run pytest tests/test_plan_ids.py -q
uv run ruff check src/fa/inner_loop/plan_ids.py tests/test_plan_ids.py
```
- [ ] STEP1: Implement `commands_for(slice_id)` and `section(slice_id)` over
      `slice_records`. An unknown id returns `()` / `""`. (exit: CT3/CT4 green.)
- [ ] STEP2: Implement the plan-level bucket for pre-heading verify blocks. (exit: CT4b
      green.)
- [ ] STEP3: Assert the flat `.commands` is unchanged. (exit: CT4c green.)
- [ ] STEP4: Change the section span in `_slice_sections` to end at the next heading of the same
      or shallower level. (exit: CT16 green — this increment's last slice excludes the
      increment-level sections that follow it, and its contracts lose `CT8` and `CT11`.)
- [ ] STEP5: Restrict `_section_contracts` to the `CONTRACTS:` block and read id and class from
      each entry's first line only. (exit: CT17 and CT18 green — SLICE1's contracts no longer
      include a `CONSTRAINT`-classed `CT3`.)
- [ ] STEP6: Implement `contract_class(contract_id)` and `tests_for(slice_id)`. (exit: CT19 and
      CT20 green.)

---

## SLICE3: Plan pre-check (static lint, pure code)
STEPS: prescriptive
DEPS: SLICE2
INTENT: lint an increment plan in code before the controller loop; plan errors cost an
  assertion, not a burned slice.
CONTRACTS:
  CT8 [CONSTRAINT]: the pre-check FAILS a slice that declares ≥1 `CT#` and has no `TESTS:`
    line.
  CT9 [CONSTRAINT]: the pre-check FAILS a `prescriptive` slice containing a `STEP#` block
    with no `(exit: …)`. A `STEP#` block is the `- [ ] STEP<n>:` line plus its indented
    continuation lines.
  CT10 [CONSTRAINT]: the pre-check FAILS on a cyclic `DEPS:` graph or a reference to an
    undefined `SLICE#`/`CT#`.
  CT10b [FUNCTIONAL]: the pre-check WARNS (never fails) when a `verify` command references a
    file path that does not exist. The command is never executed here. Slice count is an
    authoring rule in SLICE1b, not a check.
  CT25 [FUNCTIONAL]: the pre-check returns every violation in one pass, each naming `file:line`
    and a rule id; it never stops at the first failure.
  CT26 [FUNCTIONAL]: a line matching `^#{2,4}\s+SLI?CE?\s*\d` that does not parse as a slice
    heading produces a near-miss diagnostic naming the line and the intended form.
  CT27 [FUNCTIONAL]: a contract id referenced anywhere in the increment but declared in no
    `CONTRACTS:` block produces a WARN naming the referencing line.
TESTS: tests/test_plan_precheck.py  (NEW — author it; absent at 2f6b8c1)
```verify
uv run pytest tests/test_plan_precheck.py -q
uv run ruff check src/fa/inner_loop/plan_ids.py tests/test_plan_precheck.py
```
- [ ] STEP1: Build a runner of pluggable assertions returning pass/fail/warn, aggregated.
      (exit: an empty plan passes; results aggregate.)
- [ ] STEP2: Implement CT8/CT9/CT10, parsing `STEP#` as a multi-line block. (exit: each
      fails its seeded bad plan and passes the good fixture.)
- [ ] STEP3: Implement the CT10b warnings. (exit: CT10b green.)
- [ ] STEP4: Make the runner aggregate every violation before returning, each carrying
      `file:line` and a rule id. (exit: CT25 green — a plan seeded with three distinct
      violations reports three.)
- [ ] STEP5: Add the near-miss heading diagnostic and the undeclared-contract warning. (exit:
      CT26 and CT27 green.)
- [ ] STEP6: Create `tests/data/plan-drift-corpus/`, one file per observed drift mode: a space
      in the slice heading, a lower-case heading, a wrong-level heading without a colon, a
      contract declared outside the `CONTRACTS:` block, and a slice followed by an
      increment-level heading. (exit: every corpus file produces at least one named diagnostic
      and none parses silently to empty.)

---

## SLICE4: End-to-end conformance + historical migration note
STEPS: outcome
DEPS: SLICE1b, SLICE3
INTENT: prove the whole path — a plan authored strictly from the migrated skill text parses and
  pre-checks clean — and tell a human what happened to the old grammar.
CONTRACTS:
  CT14 [FUNCTIONAL]: a sample increment authored strictly from the migrated skill text parses
    via `extract_plan_ids` and passes the SLICE3 pre-check with zero failures.
TESTS: tests/test_skill_conformance.py  (NEW — author it; absent at 2f6b8c1)
```verify
uv run pytest tests/test_skill_conformance.py -q
uv run ruff check knowledge/skills tests/test_skill_conformance.py
```
- [ ] STEP1: Author the end-to-end conformance fixture from the SLICE1b skill text and run it
      through the SLICE3 pre-check. (exit: CT14 green.)
- [ ] STEP2: Add a migration note for humans: pre-rename plans are archived, not parsed, and no
      compatibility shim is provided. (exit: the note exists and names the three conditions,
      recorded in the ledger, under which zero-deprecation removal was acceptable.)

---

## SLICE5: Pinned invariants re-injected on every call
STEPS: prescriptive
DEPS: SLICE1
INTENT: the contracts the coder must not violate survive context compaction, because they are
  re-injected rather than remembered.
CONTRACTS:
  CT28 [FUNCTIONAL]: a pinned-invariants block is registered in `INJECTION_SPECS` and appears in
    every composed coder prompt, behind a `FeatureFlags` field.
  CT29 [CONSTRAINT]: the assembled block is capped at roughly 1.5K tokens; past the cap the
    oldest non-CONSTRAINT entries drop first and each drop is logged. Catches: an insurance
    mechanism quietly eating the context budget it exists to protect.
  CT30 [PRESERVATION]: the cacheable prompt prefix is byte-identical before and after this
    slice, proven by a golden-file snapshot rather than by inspection. Catches: a silent
    prompt-cache miss that surfaces only as a cost regression weeks later.
TESTS: tests/test_pinned_invariants.py  (NEW — author it; absent at 2f6b8c1)
```verify
uv run pytest tests/test_pinned_invariants.py -q
uv run ruff check src/fa/inner_loop tests/test_pinned_invariants.py
```
- [ ] STEP1: Add the injection spec and the feature flag. (exit: CT28 green.)
- [ ] STEP2: Populate the block with the current slice's `CONSTRAINT`-class contracts verbatim,
      read via `contract_class` from SLICE2. (exit: a fixture slice's constraint text appears
      verbatim in the composed prompt.)
- [ ] STEP3: Implement the size cap and its drop log. (exit: CT29 green.)
- [ ] STEP4: Add the golden-file snapshot of the cacheable prefix. (exit: CT30 green.)

---

## Increment definition of done

- [ ] Every `CT#` is satisfied: its slice's `verify` command exits 0. (`VERIFIED` is not
      claimed here; it additionally requires I02 and I03.)
- [ ] `tests/test_plan_ids.py` is green and no `S#` assertion survives.
- [ ] The SLICE3 pre-check runs clean on this increment file.
- [ ] A skill-authored sample plan parses and pre-checks clean (CT14).
- [ ] `workflow_controller` `.slices` readers unbroken (CT11).
- [ ] `grep -c SLICE src/fa/inner_loop/prompt.py` is non-zero and a planner-generated plan
      yields non-empty `.slices`, so the coverage gate at `workflow_controller.py:332` no longer
      silently no-ops.
- [ ] Every name in schema §7 has a call site outside tests, or is marked pending with a named
      consumer increment.
- [ ] Full suite: no regression against a stash-measured baseline.

## Out of scope (moved, not dropped)

- **EVIDENCE ledger parser** — moved to I04. Do not build it here. The ledger format is in
  `notes/artifact-schema-and-grammar.md` §5.

## Hand-off to I02 (banked context, not a plan)

I01 delivers the interface I02 consumes: `commands_for`, `section`, `contract_class`,
`tests_for`, `SliceRecord.test_paths`, and the `TESTS: … (NEW)` marker. Do not build the gate here.
Context for the I02 review lives in:
- `notes/verify-block-design.svg` and `notes/verify-block-design.md`.
- `notes/i02-handoff-verify-gate.md` — grounded facts and the open questions.
Do not pre-resolve them in I01. If one becomes a blocker mid-implementation, stop and
promote it to a question.
