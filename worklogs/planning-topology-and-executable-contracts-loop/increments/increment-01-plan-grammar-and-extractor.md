---
Increment-ID: RM-planning-topology-I01
Roadmap-ID: RM-planning-topology
status: IN PROGRESS
slices: 6
shipped: SLICE1
---

# INCREMENT I01: Plan grammar & extractor

**Shippable when:** the three emitters (schema §4, both planning skills, the planner prompt)
produce `## SLICE<n>:`, `CT<n> [CLASS]:`, `TESTS:`, `STEPS: prescriptive|outcome`;
`extract_plan_ids` parses them into per-slice records; and the pre-check lints an increment
plan before any coder runs. Emission is in scope because `workflow_controller.py:332` returns
early on an empty `.slices`, so a parser with no emitter changes nothing observable (E52).

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

## SLICE1b: The authoring contract (schema + planning skills)
STEPS: prescriptive
DEPS: SLICE1
INTENT: the grammar is defined once, in schema §4, and §4 carries a worked example the parser
  must reproduce, so the specification and the code cannot drift apart unnoticed.
CONTRACTS:
  CT21 [FUNCTIONAL]: schema §4 ends with a fenced ```example block — a miniature two-slice
    increment exercising every boundary rule — and `extract_plan_ids` over that block returns
    exactly the slice ids, section spans and contract set §4 documents beside it. Consumer:
    SLICE2 conforms the parser to this fixture; SLICE4 reuses it.
  CT22 [FUNCTIONAL]: each planning skill embeds a fenced ```skeleton block, and that block
    parses via `extract_plan_ids` with non-empty `.slices`, a `TESTS:` path and an explicit
    `STEPS:` mode on every slice.
  CT23 [CONSTRAINT]: every `CONSTRAINT`-class contract carries a rationale naming the wrong
    implementation it catches, on the entry's continuation lines. Catches: a constraint nobody
    can review because its intent was never written down.
  CT24 [PRESERVATION]: the skills' other ID grammar (`GAP#`, `CT#`, `T#`, `Q#`, `RK#`) is
    unchanged; only the slice and step anchors and the new fields are added.
TESTS: tests/test_skill_grammar_emit.py  (NEW — author it; absent at 2f6b8c1)
```verify
uv run pytest tests/test_skill_grammar_emit.py -q
uv run ruff check knowledge/skills tests/test_skill_grammar_emit.py
```
- [ ] STEP1: Read the four boundary rules already normative in
      `notes/artifact-schema-and-grammar.md` §4 "Section boundaries" — section span by relative
      heading depth, increment-level sections after the last slice, `CONTRACTS:`-block scope by
      indentation, one-entry-one-contract with whole-entry text — and restate each as one
      assertion over the §4 example. Do not reword the rules; if one is wrong, stop and raise a
      question rather than edit the parser to match. (exit: four assertions exist, one per
      rule.)
- [ ] STEP2: Append the ```example block to §4 and document its expected parse beside it.
      (exit: CT21 green — the test reads the fence out of the `.md` and compares against the
      documented result, so editing §4 without editing the parser turns the test red.)
- [ ] STEP3: Add the `## Grounding` block to §4, marked "prose, never parsed", with its
      mandatory first line naming what the planner understood the request to be and what it
      deliberately excluded. (exit: parsing the §4 example, whose slices each carry a
      `## Grounding` subsection, yields no contract, test or command from that subsection.)
- [ ] STEP4: Add a §4 subsection "Authoring guidance (not checked)" holding the rules that are
      judgement, not lint: `STEPS:` defaults from the TRIVIAL/STANDARD/LARGE classifier and the
      planner may override it with a one-line reason; `N <= 7` slices per increment, and a
      decomposition needing more means the increment is mis-scoped and must be split; keep a
      slice brief under roughly 1.5-2K tokens. (exit: the subsection exists and is titled so
      that no pre-check rule may key on it.)
- [ ] STEP5: Edit `knowledge/skills/plan-authoring/SKILL.md` and
      `knowledge/skills/feature-planning/SKILL.md`: replace each plan skeleton with the
      ```skeleton fence, and replace the duplicated authoring prose with a link to §4
      "Authoring guidance". Write steps as exact imperatives with file:line targets and runnable
      exit checks (schema §1); no rationale inline. (exit: CT22 and CT24 green.)
- [ ] STEP6: Add the rationale rule for `CONSTRAINT` contracts to §4 and both skills. (exit:
      CT23 green.)

---

## SLICE1c: The planner prompt emits schema §4
STEPS: prescriptive
DEPS: SLICE1b
INTENT: the planner is the third emitter; until it emits slices, the coverage gate at
  `workflow_controller.py:332` returns early and every downstream contract is untested in
  production.
CONTRACTS:
  CT31 [FUNCTIONAL]: a plan generated from the planner prompt's plan section parses via
    `extract_plan_ids` with non-empty `.slices`, and every slice carries `TESTS:` and `STEPS:`.
  CT32 [PRESERVATION]: the Evidence, Assumptions and Risks content the prompt asks for today is
    routed into `## Grounding`, not deleted; the planner's other output sections are unchanged.
    Catches: a reformat that silently drops the planner's uncertainty reporting.
TESTS: tests/test_planner_emits_schema4.py  (NEW — author it; absent at 2f6b8c1)
```verify
uv run pytest tests/test_planner_emits_schema4.py -q
uv run ruff check src/fa/inner_loop/prompt.py tests/test_planner_emits_schema4.py
```
- [ ] STEP1: Edit the planner's plan section in `src/fa/inner_loop/prompt.py` to emit schema §4,
      reusing the §4 ```skeleton wording rather than restating it. (exit: CT31 green — the test
      renders the prompt, extracts its embedded skeleton, and parses it; a `grep` for the token
      `SLICE` is not an acceptable check because a comment satisfies it.)
- [ ] STEP2: Route Evidence, Assumptions and Risks into `## Grounding`. (exit: CT32 green.)

## SLICE2: Per-slice accessors over the records
STEPS: prescriptive
DEPS: SLICE1b
INTENT: the parser is conformed to the SLICE1b specification — the §4 example is the oracle —
  and exposes the read API I02 consumes, over `slice_records`.
CONTRACTS:
  CT3 [FUNCTIONAL]: `commands_for("SLICE2")` returns only SLICE2's ```verify commands, in
    document order, de-duplicated within the slice.
  CT4 [FUNCTIONAL]: `section("SLICE2")` returns exactly SLICE2's block, spanning its heading
    through the line before the next heading at the same or shallower depth (CT16).
  CT4b [CONSTRAINT]: a ```verify block before the first slice heading is stored in a new
    `PlanIds.plan_commands: tuple[str, ...]` field and returned by `commands_for(None)`;
    `SliceRecord` is not widened and no sentinel slice id is invented. Catches: a prologue
    verify block that is reachable from the flat field but from no record, so a per-slice
    consumer silently never runs it.
  CT4c [PRESERVATION]: `.commands` keeps returning every ```verify command in the document, in
    document order, de-duplicated **globally** — prologue and increment-level blocks included.
    It is therefore a superset of, and not equal to, the concatenation of `commands_for(s)` over
    all slices, which de-duplicates per slice. No test may assert that equality. Catches: a
    reader "preserving" the flat field by re-deriving it from the slices, which changes the
    behaviour its name promises. Measured on this file at 2f6b8c1: flat 10, concatenation 12.
  CT16 [CONSTRAINT]: a slice section ends at the first later line that is a heading of depth
    less than or equal to the depth of that slice's own heading, or at end of document. The
    depth is read from the matched heading, never hardcoded: `_SLICE_RE` admits `##` to `####`,
    so a fixed `^#{1,2}` terminator is wrong for a `###` slice. Catches: the final slice
    silently absorbing the increment-level sections that follow it, and every contract id
    mentioned in them.
  CT17 [CONSTRAINT]: the `CONTRACTS:` block runs from the `CONTRACTS:` line to the first later
    non-blank line that begins at column 0, or to the end of the section. Indentation is the
    only terminator — no allowlist of field names, because a new column-0 field (`SHIPPED:`)
    would silently extend the block. Catches: a stray contract id typed in step text becoming a
    contract of the slice.
  CT18 [CONSTRAINT]: one entry declares one contract. An entry starts at an indented line
    matching `CT<n>[a-z]? [[CLASS]]:` and continues through every following line indented more
    deeply. The id and class are read from the entry's first line only; the contract **text is
    the whole entry**, continuation lines joined with single spaces. Catches two defects at
    once: CT2's illustrative example giving SLICE1 a second, differently-classed `CT3`; and
    `line.split("]:", 1)[1]` truncating every contract at its first line, which would silently
    discard exactly the CT23 rationale that SLICE1b mandates.
  CT19 [FUNCTIONAL]: `contract_class("CT3")` returns the class declared under CT17 and CT18; an
    id declared nowhere returns `None`. If one id is declared more than once the function is
    still deterministic — first declaration in document order wins — and the pre-check reports
    it (CT34). Consumer: I02.
  CT20 [FUNCTIONAL]: `tests_for("SLICE2")` returns that slice's `TESTS:` paths. Consumer: I02.
  CT33 [FUNCTIONAL]: the trailing annotation on a `TESTS:` line — the `(NEW — …)` note that
    `_test_paths` discards at the `(` — is preserved on the record as
    `SliceRecord.tests_note: str`. I01 preserves it and assigns it no meaning; I02 decides what
    `NEW` licenses. Consumer: I02, whose fail-before filter keys on it
    (`notes/i02-handoff-verify-gate.md` §2) and which has no other source for it.
TESTS: tests/test_plan_ids.py
```verify
uv run pytest tests/test_plan_ids.py -q
uv run ruff check src/fa/inner_loop/plan_ids.py tests/test_plan_ids.py
```
- [ ] STEP1: Change the section span in `_slice_sections` (`src/fa/inner_loop/plan_ids.py:198`)
      to end at the next heading of depth ≤ the slice heading's own depth, taking the depth from
      the match. (exit: CT16 green against the schema §4 example, and this increment's last
      slice no longer absorbs the increment-level sections.)
- [ ] STEP2: Restrict `_section_contracts` (`:234`) to the `CONTRACTS:` block by the
      indentation rule, group each entry with its continuation lines, read id and class from the
      first line, and join the entry for the text. (exit: CT17 and CT18 green — SLICE1's
      contracts no longer include a `CONSTRAINT`-classed `CT3`, and CT23's "Catches:" sentence
      survives into `contract.text`.)
- [ ] STEP3: Add `PlanIds.plan_commands` and populate it from ```verify blocks before the first
      slice heading; make `commands_for(None)` return it. (exit: CT4b green.)
- [ ] STEP4: Implement `commands_for(slice_id)` and `section(slice_id)` over `slice_records`.
      An unknown id returns `()` / `""`. (exit: CT3/CT4 green.)
- [ ] STEP5: Pin the flat-field behaviour with a test that asserts the documented superset
      relation and asserts the two are **not** equal on this increment file. (exit: CT4c green.)
- [ ] STEP6: Implement `contract_class(contract_id)`, `tests_for(slice_id)`, and carry
      `tests_note` onto `SliceRecord`. (exit: CT19, CT20 and CT33 green.)

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
  CT34 [CONSTRAINT]: the pre-check FAILS when one `CT#` is declared in more than one
    `CONTRACTS:` block, naming both `file:line`s. Schema §4 requires ids unique per increment
    and nothing enforced it: CT10 covers undefined references, not duplicate declarations.
    Catches: two slices each believing they own `CT11`, so `contract_class` answers for one of
    them and the other's class is unreachable.
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
- [ ] STEP5: Add the near-miss heading diagnostic, the undeclared-contract warning and the
      duplicate-declaration failure. (exit: CT26, CT27 and CT34 green.)
- [ ] STEP6: Create `tests/data/plan-drift-corpus/`, one file per observed drift mode: a space
      in the slice heading, a lower-case heading, a wrong-level heading without a colon, a
      contract declared outside the `CONTRACTS:` block, a slice followed by an
      increment-level heading, and one `CT#` declared in two slices. (exit: every corpus file produces at least one named diagnostic
      and none parses silently to empty.)

---

## SLICE4: End-to-end conformance + historical migration note
STEPS: outcome
DEPS: SLICE1c, SLICE3
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
- [ ] STEP1: Author the end-to-end conformance fixture from the SLICE1b skill text — not from
      the schema §4 example, which SLICE2 already conforms the parser to — and run it through
      the SLICE3 pre-check. (exit: CT14 green.)
- [ ] STEP2: Add a migration note for humans: pre-rename plans are archived, not parsed, and no
      compatibility shim is provided. (exit: the note exists and names the three conditions,
      recorded in the ledger, under which zero-deprecation removal was acceptable.)

---

## Increment definition of done

- [ ] Every `CT#` is satisfied: its slice's `verify` command exits 0. (`VERIFIED` is not
      claimed here; it additionally requires I02 and I03.)
- [ ] `tests/test_plan_ids.py` is green and no `S#` assertion survives.
- [ ] The SLICE3 pre-check runs clean on this increment file — including CT34. Parsed with the
      2f6b8c1 extractor this file reports ten duplicate ids, because SLICE4 absorbs the
      document tail (CT16) and step prose is read as declarations (CT17). Every one of them is
      an artefact of those two defects and must disappear once SLICE2 lands. If any survives,
      the plan is wrong, not the lint.
- [ ] A skill-authored sample plan parses and pre-checks clean (CT14).
- [ ] `workflow_controller` `.slices` readers unbroken (CT11).
- [ ] A planner-generated plan yields non-empty `.slices`, so the coverage gate at
      `workflow_controller.py:332` no longer silently no-ops (CT31). A `grep` for the token
      `SLICE` in `prompt.py` is not evidence — a comment satisfies it.
- [ ] Every name in schema §7 has a call site outside tests, or is marked pending with a named
      consumer increment.
- [ ] Full suite: no regression against a stash-measured baseline.

## Out of scope (moved, not dropped)

- **EVIDENCE ledger parser** — moved to I04. Do not build it here. The ledger format is in
  `notes/artifact-schema-and-grammar.md` §5.
- **Pinned invariants re-injected on every call** — moved to I04, where the roadmap already
  schedules "pinned invariants". It was drafted as an I01 slice this session and that was scope
  creep: it edits prompt composition, not plan grammar, and it consumed `contract_class` before
  I02 — its first real consumer — exists. Banked with its contracts in
  `notes/role-prompts-conformance.md` §"Banked for I04"; ledger E70/E71.

## Hand-off to I02 (banked context, not a plan)

I01 delivers the interface I02 consumes: `commands_for`, `section`, `contract_class`,
`tests_for`, `SliceRecord.test_paths`, and `SliceRecord.tests_note` — the preserved `(NEW — …)`
annotation (CT33). I01 preserves that string and gives it no meaning; open question 2 in the
hand-off note (prose marker vs machine token) stays I02's to answer, but it is now answerable,
because the text reaches I02 instead of being discarded at the `(`. Do not build the gate here.
Context for the I02 review lives in:
- `notes/verify-block-design.svg` and `notes/verify-block-design.md`.
- `notes/i02-handoff-verify-gate.md` — grounded facts and the open questions.
Do not pre-resolve them in I01. If one becomes a blocker mid-implementation, stop and
promote it to a question.
