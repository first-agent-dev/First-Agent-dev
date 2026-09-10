---
Increment-ID: RM-planning-topology-I01
Roadmap-ID: RM-planning-topology
status: READY
slices: 4
---

# INCREMENT I01: Plan grammar & extractor

**Shippable when:** `extract_plan_ids` parses `## SLICE<n>:`, `CT<n> [CLASS]:`, `TESTS:`,
`STEPS: prescriptive|outcome`, and per-slice records; and the pre-check lints an increment
plan before any coder runs.

**Ground truth (verified @ tip 0e08ece — read these before editing):**
- `src/fa/inner_loop/plan_ids.py:55` — `_SLICE_RE` matches `### S<n>:` / `### Step S<n>:`.
- `src/fa/inner_loop/plan_ids.py:92-104` — `PlanIds` is a frozen dataclass of flat tuples.
- `src/fa/inner_loop/plan_ids.py:61` — `_CONTRACT_RE` is `\bCT(\d+[a-z]?)\b`.
- `tests/test_plan_ids.py` (279 lines) exists and uses `### Step S<n>:` fixtures.
- `src/fa/inner_loop/workflow_controller.py:332` and `:461` read `.slices`.

**Decisions (do exactly):**
- Recognize `SLICE#` only. Do not keep an `S#` pattern and do not add a dual grammar.
- Retain the flat fields (`.slices/.gaps/.contracts/.tests/.commands`) unchanged.
- Add `slice_records: tuple[SliceRecord, ...]` beside them; do not substitute.
- Pre-rename `S#` plans are archived and parse to empty `.slices`. Accepted.

---

## SLICE1: New grammar tokens + per-slice records (+ migrate the existing test)
STEPS: prescriptive
DEPS: —
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
- [ ] STEP1: Edit `plan_ids.py:55`. Do exactly: set `_SLICE_RE` to match `## SLICE<n>:`;
      add `_STEP_RE` for `STEP<n>:`; delete the `S#` pattern.
      (exit: a `SLICE#` fixture yields `slices=("SLICE1","SLICE2")`; an `S#`-only string
      yields `()`.)
- [ ] STEP2: Add the contract-class capture and define `SliceRecord`; populate
      `slice_records` with intent, classed contracts, test_paths, steps_mode, the slice's
      verify commands, and the section span. (exit: CT2/CT5/CT6/CT7 fixtures green.)
- [ ] STEP3: Migrate `tests/test_plan_ids.py`. After it, `grep -nE '### (Step )?S[0-9]'
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
- [ ] STEP4: Add a regression test that `workflow_controller.py:332` and `:461` resolve
      `.slices` for a `SLICE#` plan. (exit: CT11 green.)
- [ ] STEP5: Add a test pinning CT13. (exit: CT13 green.)

---

## SLICE2: Per-slice accessors over the records
STEPS: prescriptive
DEPS: SLICE1
INTENT: expose the read API I02 and I03 consume, over `slice_records`.
CONTRACTS:
  CT3 [FUNCTIONAL]: `commands_for("SLICE2")` returns only SLICE2's ```verify commands.
  CT4 [FUNCTIONAL]: `section("SLICE2")` returns exactly SLICE2's block (heading through the
    line before the next `## SLICE` heading).
  CT4b [CONSTRAINT]: a ```verify block before any slice heading goes to a plan-level bucket
    (`commands_for(None)`); it is never dropped or attributed to SLICE1.
  CT4c [PRESERVATION]: the flat `.commands` equals the concatenation of all slices'
    commands.
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

---

## SLICE3: Plan pre-check (static lint, pure code)
STEPS: prescriptive
DEPS: SLICE1, SLICE2
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
  CT10b [FUNCTIONAL]: the pre-check WARNS (never fails) when the slice count is outside 4–7,
    or a `verify` command references a file path that does not exist. The command is never
    executed here.
TESTS: tests/test_plan_precheck.py  (NEW — author it; absent at tip 0e08ece)
```verify
uv run pytest tests/test_plan_precheck.py -q
uv run ruff check src/fa/inner_loop/plan_ids.py tests/test_plan_precheck.py
```
- [ ] STEP1: Build a runner of pluggable assertions returning pass/fail/warn, aggregated.
      (exit: an empty plan passes; results aggregate.)
- [ ] STEP2: Implement CT8/CT9/CT10, parsing `STEP#` as a multi-line block. (exit: each
      fails its seeded bad plan and passes the good fixture.)
- [ ] STEP3: Implement the CT10b warnings. (exit: CT10b green.)

---

## SLICE4: Migrate the planning skills + conformance fixture
STEPS: outcome
DEPS: SLICE1, SLICE2, SLICE3
INTENT: `feature-planning` and `plan-authoring` emit the new grammar so a planner-authored
  plan parses and pre-checks clean.
CONTRACTS:
  CT14 [FUNCTIONAL]: a sample increment authored strictly from the migrated skill text
    parses via `extract_plan_ids` and passes the SLICE3 pre-check with zero failures.
  CT15 [PRESERVATION]: the skills' other ID grammar (`GAP#`, `CT#`, `T#`, `Q#`, `RK#`) is
    unchanged; only the slice/step anchors and new fields are added.
TESTS: tests/test_skill_conformance.py  (NEW — author it; absent at tip 0e08ece)
```verify
uv run pytest tests/test_skill_conformance.py -q
uv run ruff check knowledge/skills tests/test_skill_conformance.py
```
- [ ] STEP1: Update both skills' plan skeletons and ID sections to the new grammar.
      (exit: a fixture written from the skill text parses.)
- [ ] STEP2: Add authoring guidance for contract classes, `TESTS:`, and `STEPS:` mode. Write
      the skill's instructions as exact imperatives with file:line targets and runnable exit
      checks (schema §1 authoring rule); no rationale inline.
      (exit: the fixture pre-checks clean, including CT8.)
- [ ] STEP3: Add a migration note: pre-rename (`S#`) plans are archived, not parsed.
      (exit: CT15 green; the note exists.)

---

## Increment definition of done

- [ ] Every `CT#` is satisfied: its slice's `verify` command exits 0. (`VERIFIED` is not
      claimed here; it additionally requires I02 and I03.)
- [ ] `tests/test_plan_ids.py` is green and no `S#` assertion survives.
- [ ] The SLICE3 pre-check runs clean on this increment file.
- [ ] A skill-authored sample plan parses and pre-checks clean (CT14).
- [ ] `workflow_controller` `.slices` readers unbroken (CT11).
- [ ] Full suite: no regression against a stash-measured baseline.

## Out of scope (moved, not dropped)

- **EVIDENCE ledger parser** — moved to I04. Do not build it here. The ledger format is in
  `notes/artifact-schema-and-grammar.md` §5.

## Hand-off to I02 (banked context, not a plan)

I01 delivers the interface I02 consumes: `commands_for`, `section`,
`SliceRecord.test_paths`, and the `TESTS: … (NEW)` marker. Do not build the gate here.
Context for the I02 review lives in:
- `notes/verify-block-design.svg` and `notes/verify-block-design.md`.
- `notes/i02-handoff-verify-gate.md` — grounded facts and the open questions.
Do not pre-resolve them in I01. If one becomes a blocker mid-implementation, stop and
promote it to a question.
