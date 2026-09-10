---
Ledger-for: RM-planning-topology
type: EVIDENCE
append-only: true
---

# EVIDENCE ledger — planning-topology & executable-contracts loop

Append-only. Never rewrite an entry; supersede it with a new entry carrying
`supersedes:`. Entry types: `FACT` (carries a verification ref) · `DERIVED` ·
`LOOKUP` · `GUESS` (an `ASK#` candidate) · `FAILED` · `GAP` · `PRESERVE` ·
`DECIDED`. The planner reads this at increment start; the eval appends per slice.

Format: `E<n>  <TYPE>  <statement>  [<provenance>]`

---

## Verified facts about the current system

E1  FACT  `plan_ids.py` exposes `PlanIds{slices,gaps,contracts,tests,commands}` plus
    `extract_plan_ids` / `extract_plan_id`; commands are read from fenced ```verify
    blocks.  [verified: plan_ids.py:92-167 @ arena/01a0762b]
E2  FACT  `_extract_commands` returns a FLAT tuple — verify commands are NOT attributed
    to slices, so "did SLICE# pass?" is not expressible today.  [verified:
    plan_ids.py:123-138 @ arena/01a0762b]
E3  FACT  `PlanIds.commands` has zero readers; only `.slices` is read, at
    `workflow_controller.py:332` and `:461`.  [verified: grep @ arena/01a0762b]
E4  FACT  `workflow_controller._run_adaptive` loops on the WHOLE plan (route
    return_to_coder / return_to_planner, budgeted) — the loop unit is the plan, not the
    slice.  [verified: workflow_controller.py:913 @ arena/01a0762b]
E5  FACT  `_git_output` (`workflow_controller.py:401`) is git-only, list-argv, and
    collapses every failure to `None` — advisory shape, NOT reusable as a fail-loud
    verification runner.  [verified: workflow_controller.py:401-432 @ arena/01a0762b]
E6  FACT  The judge prompt mandates per-slice prose (`### Step results`, `- S1: PASS`)
    AND asserts command results in prose (`Focused: PASS/FAIL — <command>`).
    [verified: prompt.py:865-880 @ arena/01a0762b]
E7  FACT  `plan-authoring` writes `### Step S#`, conflating slice and step — the root of
    the SLICE/STEP ambiguity.  [verified: plan-authoring SKILL @ arena/01a0762b]
E8  FACT  The superseded plan absorbed the F6 adversarial review (F-1 verify grammar,
    F-4 honest L3, F-5a no private-function reuse) and stalled at S15 (eval verification
    mechanism + complexity).  [verified: monster plan rev log + §27 @ arena/01a0762b]

## Derived

E9  DERIVED  Because commands are flat (E2) and unread (E3), the deterministic per-slice
    gate needs (a) per-slice command attribution and (b) a reader — both are I01/I02
    work, not config.  [from E2 + E3]
E10 DERIVED  The verify runner must be NEW (fail-loud, shell-capable, timeout +
    scrubbed env), not `_git_output`; `_git_output`'s advisory degrade-to-None is the
    wrong failure philosophy for a gate.  [from E5]

## Decisions (this roadmap)

E11 DECIDED  Adopt the four-tier topology + rolling wave + planner-authors-steps.
    [PLANNING-TOPOLOGY-EXPLAINED.md; research §5 rates all six "supported"]
E12 DECIDED  Artifact schema = roadmap.md + ledger.md + increments/ + notes/; pure-slug
    folder; created: in frontmatter; zero-padded increments.  [operator, this session]
E13 DECIDED  Rename S# → SLICE#, steps → STEP#.  [operator, this session]
E14 DECIDED  Contracts get classes (FUNCTIONAL/CONSTRAINT/PRESERVATION); planner authors
    the test file; harness proves non-vacuity (fail-before/pass-after). Landed in I02.
    [research #1/#11; SWE-Gate 34.3% false-accept]
E15 DECIDED  Verify exit code = fact; eval verdict = judgment; eval on a different model
    family, blind to authorship.  [research #8; self-preference bias 2410.21819]

## Assumptions / open (ASK# candidates)

E16 GUESS  4–7 slices per increment is the right sizing prior for this codebase.
    [assumed — confirm from I06 telemetry]
E17 GUESS  Per-slice eval is affordable (N cheap calls beat 1 overwhelmed call).
    [assumed — re-check at I03]
E18 LOOKUP  Whether the existing injection machinery (InjectionSpec / `fa inject`) can
    carry the pinned-invariants preamble unchanged, or needs a new channel.  [I04]

## To preserve

E19 PRESERVE  The two doc-gate reds (`test_doc_links`,
    `test_historical_workspace_docs_have_top_level_superseded_banner`) are deliberate S7
    bait and STAY RED — do not "fix" them in any increment.  [operator, standing]
E20 PRESERVE  `pr_prepare` stays registered for `coder` (conformance baseline
    `tests/data/windows-baseline-2026-08-02.txt` must not change).  [monster S8 / D10]

## Gaps carried

E21 GAP  The monster plan's on-hold slices S6a/S6b/S7/S8 (ceremony, scope, draft, chat
    pr_prepare) are unmapped to concrete new slices until I05 is planned.  [→ I05]

## Plan review of I01 — findings folded (this session)

E22 FACT  `tests/test_plan_ids.py` (279 ln) already exists; its `PLAN_FIXTURE` uses
    `### Step S1:`/`### Step S5a:` and asserts `ids.slices == ("S1","S5a")` + a flat
    `ids.commands`. The SLICE# rename breaks both.  [verified: tests/test_plan_ids.py:34-110 @ arena/01a0762b]
E23 FACT  `workflow_controller.py:332` early-returns when `.slices` is empty, so an
    unparseable (old `S#`) plan makes the coverage gate silently no-op.
    [verified: workflow_controller.py:332-334 @ arena/01a0762b]
E24 DECIDED  The extractor recognizes `SLICE#` only; pre-rename `S#` plans are archived and
    parse to empty `.slices` (accepted silent no-op). No dual grammar.  [I01/SLICE1]
E25 DECIDED  `PlanIds` flat fields are retained; per-slice data is added as `slice_records:
    tuple[SliceRecord,…]`, not substituted — backward-compat for the two callers + the
    migrated test.  [I01/SLICE1-2]
E26 DECIDED  The EVIDENCE-ledger parser moves from I01 to I04 (build beside its consumers);
    the ledger format stays specified in notes/.  [supersedes the I01 v1 SLICE3]
E27 GAP  Per-`CT#` test attribution (`CT# (test: …)`) is deferred to I02; I01 enforces only
    the slice-level "has a TESTS: line" rule.  [→ I02]
E28 GAP  Adoption items #10/#16/#18 were unaccounted in the roadmap; now recorded in the
    roadmap's "Deferred — explicitly not scheduled" section.  [roadmap.md]

## Second readiness pass on I01 (pre-implementation gate, 2026-09-09)

Tip verified: 0e08eceab8ee5aefedde83466d43304be94f407d (2026-09-07).

E29 FACT  `tests/test_plan_ids.py:212 test_this_plan_is_conforming` parses the committed
    superseded `worklogs/implementation-plans/PLAN-slice-ceremony-harness-enforcement.md`
    and asserts `"S1" in ids.slices`. A SLICE#-only extractor fails it.  [verified @ tip]
E30 FACT  `tests/test_plan_ids.py:202` globs `worklogs/implementation-plans/*.md` and
    asserts the glob is non-empty; `:258` repoints at the same plan and asserts
    `any("ruff" in c ...)`.  [verified @ tip]
E31 FACT  `tests/test_plan_reference.py:45-49 _PLAN_BODY` uses `### Step S1:` but feeds only
    `plan_identity()`/`plan_path` — slice-independent. NOT a blocker.  [verified @ tip]
E32 FACT  `_CONTRACT_RE = r"\bCT(\d+[a-z]?)\b"` (plan_ids.py:61). Hyphenated contract IDs
    (`CT-DATA`) are invisible to the extractor.  [verified @ tip]
E33 FACT  Skills live at `knowledge/skills/`; `.claude/skills` does not exist. Plan-grammar
    owners: `plan-authoring` (44 KB), `feature-planning` (23 KB + INJECT.md).  [verified @ tip]
E34 DECIDED  CT IDs renumbered: `CT-DATA`→`CT7`; SLICE4's `CT12/CT13`→`CT14/CT15`. IDs are
    unique across the increment and must match `\bCT(\d+[a-z]?)\b`.  [I01]
E35 DECIDED  `SliceRecord.tests` renamed `test_paths` — the retained flat `PlanIds.tests`
    holds `T#` IDs, so the shared name invited a real conflation bug.  [I01/SLICE1]
E36 DECIDED  The bare `STEPS:` list header is removed from the grammar; `STEPS:` is reserved
    for the mode token.  [notes/ §8]
E37 GAP   Tip commit proposes "S16: PlanIds.commands has no consumers". I01 CT4c retains the
    field because I02 consumes it. If S16 lands first, CT4c must be re-justified, not
    silently reverted.  [tip commit msg, 2026-09-07]

## Verify-gate design folded in as banked I02 context (2026-09-09)

E38 DECIDED  The verify-gate design (four-phase ritual + seven-row truth table + two
    postures) is grounded in `notes/verify-block-design.{svg,md}`; research sources F8/F11/
    F12/§4E/§7.1&5. It is banked, not planned — I02 is reviewed when I01 lands.
E39 FACT  The gate does not exist at tip 0e08ece: `.commands` has zero readers; the only
    external `extract_plan_ids` callers (workflow_controller.py:332,461) read `.slices`.
    `_git_output:401` collapses failure→None (not fail-loud).  [verified @ tip]
E40 GAP   Open for the I02 review (banked in notes/i02-handoff-verify-gate.md §4): per-command
    vs per-test granularity; `(NEW)` marker machine-readability; baseline storage path;
    three-state result shape/home; per-command timeout; the S16 `.commands` collision (E37).

## Operator feedback round — schema/prompt conformance (2026-09-09)

E41 DECIDED  Increment frontmatter `title:` removed (redundant with the `# INCREMENT I0N:`
    heading + `Increment-ID`); schema §3 and increment-01 updated.
E42 DECIDED  Schema §8 ("rules added by review") deleted; its load-bearing rules now live as
    exact positive statements in §1 (skills path) and §4 (three-class rationale, CT-id regex,
    STEPS-mode-only, sub-steps-are-prose, ````text wrapper).
E43 DECIDED  Schema §1 gains a "who writes what" ownership table: increment plan body =
    planner; increment status ticks = harness only; ledger appended by eval (+harness FACTs);
    code/tests = coder. Roles under harness control, scoped to named files.
E44 FACT  `prompt.py:648` (coder) currently tells the coder to mark steps `[x]` — conflicts
    with harness-owned tracking (schema §6). Delta banked, not merged.  [verified @ tip]
E45 DECIDED  Role-prompt deltas banked in notes/role-prompts-conformance.md, mapped by owner:
    planner grammar→I01, coder behavior→I03, eval ledger wiring→I04. Prompts state behavior;
    schema states format — one source of truth each.
E46 FACT  Schema §5 ledger grammar existed but was thin; strengthened with a worked example +
    explicit ownership (eval appends EVIDENCE, harness appends FACTs, planner reads).
E47 DECIDED  (operator) Role-prompt conformance deltas stay BANKED, implemented in the owning
    increment: planner grammar→I01, coder behavior→I03, eval ledger wiring→I04. No src churn
    before I01 lands.  [ask_user 2026-09-09]
E48 DECIDED (operator) Agent-executable text = exact imperatives; high signal/low noise; no
    citations/history/rationale inline. increment-01 rewritten as the exemplar (18 CTs /
    4 slices / verify blocks preserved; dogfood PASS). Schema §4 token rules rewritten as
    imperatives; §1 and the roadmap carry the authoring rule as a standing decision.
