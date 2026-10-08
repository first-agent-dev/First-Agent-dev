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
E49 FACT  I01/SLICE1 shipped in c0a8f429 (PR #69, merged 2026-09-10): `_SLICE_RE`, `SliceRecord`
    and `slice_records` are live; `tests/test_plan_ids.py` is 367 lines and carries no `S#`
    fixture except the legacy-rejection assertion at `:367`. supersedes: E1, E22, E29, E30 —
    those describe pre-migration code.  [verified @ 2f6b8c1, 2026-10-06]
E50 FACT  `increment-01` said `status: READY` with every `STEP#` box unticked while SLICE1 was
    merged. Plan-vs-reality drift, closed this session.  [verified @ 2f6b8c1]
E51 DECIDED (operator) Until the I03 harness exists, the **operator** ticks shipped `STEP#`
    boxes and sets `shipped:` in the increment frontmatter; the model never ticks them. Schema
    §6 carries the exception and its expiry.  [ask_user 2026-10-06]
E52 FACT  `grep -c SLICE src/fa/inner_loop/prompt.py` is 0. The planner emits
    Class/Goal/Evidence/Scope/Assumptions/Constraints/Plan/Verification/Risks with `S1.` steps,
    so a freshly authored plan parses to empty `.slices`, `workflow_controller.py:332` returns
    early and the coverage gate no-ops **silently**. Live defect, not archival.
    [verified @ 2f6b8c1, 2026-10-06]
E53 FACT  The planner's `S1.` items are step-sized (one mechanical `accept:` each), so the
    honest mapping is `S#` → `STEP#`. The runtime format has **no source for the `SLICE#` tier
    at all**: grouping steps into commit-sized slices is a judgement, not a transform. Any
    runtime→increment compiler would have to invent that tier.  [verified @ 2f6b8c1]
E54 DECIDED (operator) ASK#-01 resolved as (b′): the planner emits schema §4 directly plus a
    free-form `## Grounding` block; code performs admission (parse → validate → default and
    stamp → persist) under a no-inference rule. Rejected: a runtime→increment compiler, per
    E53. supersedes: the `assumed:` roadmap row on plan-format translation.  [ask_user
    2026-10-06]
E55 FACT  `_slice_sections` ends a section at the next `SLICE` heading or EOF, so the last
    slice absorbs the increment tail. Reproduced on the 2026-10-06 rewrite of increment-01:
    SLICE5 acquires `CT14` and `CT11` from the definition-of-done and hand-off sections.
    Addressed by CT16.  [verified by dogfooding plan_ids.py @ 2f6b8c1]
E56 FACT  `_section_contracts` scans every line of a section for `\bCT(\d+[a-z]?)\b`, so prose
    references become declarations: SLICE1 acquires a `CONSTRAINT`-classed `CT3` from CT2's
    illustrative text while SLICE2 declares `CT3` as `FUNCTIONAL`. One id, two classes, so
    `contract_class("CT3")` is undefined. Addressed by CT17 and CT18.  [verified by dogfooding]
E57 DECIDED (operator) The A3/A4 fixes land as parser conformance to a written authoring
    contract, in that order: schema §4 states the rule (SLICE1b), the parser implements it
    (SLICE2 CT16/CT17/CT18), the pre-check warns on undeclared references (SLICE3 CT27).
    Rejected: convention-plus-pinning-test, the CT13 precedent — there the correct behaviour was
    genuinely ambiguous; here it is not.  [ask_user 2026-10-06]
E58 DECIDED (operator) **The prompt is primary; the parser conforms to it.** For any grammar
    question the order is: authoring contract (schema §4 + skills + planner prompt) → parser →
    pre-check. The prompt sets the mental model the plan's quality depends on. I01's slice order
    is rebuilt on this: SLICE1 → SLICE1b → SLICE2 → SLICE3 → SLICE4, with SLICE5 independent.
    [ask_user 2026-10-06]
E59 DECIDED (operator) No accessor ships without a named consumer increment and a wiring step in
    that consumer. Grounded in E2/E3/E5: the flat `.commands` shipped with zero readers and has
    none today. Schema §7 now carries `consumer:` on every name; `steps_mode` is marked pending
    and is **not** built in I01.  [ask_user 2026-10-06]
E60 FACT  `src/fa/blackboard/blackboard.py` (389 lines) provides typed durable entries with
    `content_hash` (sha256 over sorted-key JSON), `parent_id` lineage, `read_set`/`write_set`,
    `assumptions`, `version_dependencies`, `toolchain_digest` and `run_id`, plus
    `detect_conflict` with write/write, read/write and write/read overlap detection and
    `_assumption_violated`. `TelemetryLogger` provides an append-only event log with secret-key
    detection and value elision. `EventBus` (`fa/output.py`) is a console renderer bus, not a
    durable log. **The planning loop touches none of it.**  [verified @ 2f6b8c1, 2026-10-06]
E61 FACT  E60 makes several proposed mechanisms redundant before they are built: a typed
    attempt record (`BlackboardEntry(type="attempt")` chained by `parent_id`), a failure
    signature canonicalisation spec (`content_hash` already canonicalises), hash-link
    provenance, the `tree_hash`/`HEAD` freshness stamp (`version_dependencies`), stale-fact
    detection for ledger FACTs (`assumptions` + `detect_conflict`), syntactic parallel-slice
    safety (`read_set`/`write_set`, deferred item #11) and record redaction. The gap is
    **integration, not design** — the same shape as E2/E3/E5.  [verified @ 2f6b8c1]
E62 DECIDED (operator) Markdown stays the authoring substrate as a staged decision. The
    strangler's destination is named concretely: project slice records into the existing
    `Blackboard` (E60), not a new store. Taken now: the golden drift corpus and the near-miss
    heading lint (SLICE3), which double as the fixtures for CT16/CT17/CT18. Deferred: the
    silent-mis-parse counter and the first-pass-rate SLI — no runs, no baseline, so the numbers
    would be decoration. Declined: ARCH's Phase-0-substrate-first build order.  [ask_user
    2026-10-06]
E63 DECIDED (operator) Test non-vacuity: one scoped mutation run per slice, **as a gate**, with
    appeal — the planner may dismiss a survivor with a one-line reason appended here via the
    existing `GUESS→decided:` flow. No exceptions for refactor-only slices: a refactor claims
    behaviour is preserved, so a survivor there is signal, not noise. Rejected as over-built: a
    findings format, a routing mechanism, a top-K cap, a shadow phase and a pre-registered
    graduation rule. An arid list, if ever needed, derives from repeated dismissals.
    [ask_user 2026-10-06]
E64 DECIDED (operator) Authorship-vs-acceptance (principle 8) separates into two failure modes.
    Weak acceptance — a test that does not enforce its stated contract — is closed by E63.
    A wrong specification is irreducibly human, because any check derived from the plan inherits
    the plan's error. The control is the operator's review, recorded as such, plus two readback
    mechanisms: the mandatory understood-and-excluded line in `## Grounding`, and one rationale
    line per `CONSTRAINT` contract. Eval-authored held-out tests are **rejected as specified** —
    the eval reads the same plan and inherits the same misunderstanding.  [ask_user 2026-10-06]
E65 GAP  Schema §6 defined `VERIFIED` as pass^k for stochastic gates without stating what resets
    k, so passes could accumulate across different code states. Closed: any change to the diff,
    the test file, the verify command or the model family resets k to zero.  [verified @ 2f6b8c1]
E66 GAP  `notes/verify-block-design.md` specifies baselines as "run the slice's commands once on
    the untouched tree", which is O(slices × suite-time). Baselines must be hermetic and
    **affected-path scoped**. Recorded against I02 before the design is built.
E67 GAP  The schema has **no `RISK` vocabulary**, so a rule-based risk floor (auth, crypto,
    permissions, billing, migrations ⇒ at least elevated) has no field to raise. It is a new
    concept, not a rider. Banked for I05 with this dependency stated.  [verified @ 2f6b8c1]
E68 FACT  Citation audit of the research note: MAST's FM-2.2 is **6.80%** in v3 (1642 traces),
    not the 11.65% of v1/v2 that the note cites, so the justification for the clarifying-question
    item is roughly 1.7× weaker than written. The architecture census transcribes a superseded
    version whose current data **reverses** its conclusion — in this project's favour, since a
    code-owned scripted pipeline is the group that now leads. `2206.10498` is PlanBench, not
    LLM-Modulo. Root cause of both consequential errors: arXiv ids cited without versions or
    retrieval dates.  [verified against primary sources, 2026-10-06]
E69 DECIDED (operator) The research note is corrected **in place** rather than superseded, since
    `knowledge/research/` is a working reference the planner reads. The provenance trail is
    preserved here instead: one ledger line per correction with the old value, the new value and
    the source. E15's citation is swapped 2410.21819 → 2404.13076 — the cited paper attributes
    the bias to perplexity, not self-generation, so it does not support the different-family
    rule. E14's SWE-Gate 34.3% is exact; no action.  [ask_user 2026-10-06]
E70 GAP  Adversarial review of I01 found **CT4c is false as written and false by construction**.
    It claims the flat `.commands` equals the concatenation of the slices' commands. Measured on
    `increment-01` with the 2f6b8c1 extractor: flat **10**, concatenation **12**. Cause:
    `_ordered_unique` (`plan_ids.py:169`) dedupes globally at `:280` but per-section at `:249`,
    and SLICE1/SLICE2 share two identical verify commands. A PRESERVATION contract that misstates
    current behaviour is the worst kind — it instructs the implementer to *change* behaviour to
    satisfy a wrong spec. Restated as the true superset relation, with the measurement inline and
    an explicit ban on asserting equality.  [measured 2026-10-06 @ 2f6b8c1]
E71 GAP  CT4b ("a pre-heading verify block goes to a plan-level bucket") had **no data structure
    to land in**. `PlanIds` has no plan-level command field and `SliceRecord.slice_id` is typed
    `str`, so no sentinel record can key one; `_slice_sections` (`:198`) deliberately excludes the
    prologue. Confirmed: a pre-heading block reaches the flat field and **no** `SliceRecord`.
    Closed by specifying `PlanIds.plan_commands` in schema §7 and ordering it before the
    accessors in SLICE2.  [measured 2026-10-06 @ 2f6b8c1]
E72 GAP  CT16's "same or shallower level" was under-specified in a way that invites a latent bug.
    `_SLICE_RE` is `^#{2,4}\s+SLICE(\d+[a-z]?)\s*:` (`:58`) and all three depths parse, so the
    terminator must be computed **relative to each slice's own matched heading depth**; a
    hardcoded `^#{1,2}` is wrong for a `###` slice. Fixed in CT16 and in schema §4.
    [measured 2026-10-06 @ 2f6b8c1]
E73 GAP  Three-way interface mismatch across SLICE1b/SLICE2/SLICE5. `_section_contracts` (`:234`)
    takes contract text as `line.split("]:", 1)[1]` — **first line only** — while CT23 requires the
    `CONSTRAINT` rationale on a continuation line and the pinned-invariants slice required
    `CONSTRAINT` text **verbatim**. Confirmed by extraction: CT23's own text truncates before its
    "Catches:" sentence. Closed by making the contract text the whole entry (CT18, schema §4);
    id and class stay first-line-only.  [measured 2026-10-06 @ 2f6b8c1]
E74 DECIDED CT17's terminator is the **indentation rule** — the `CONTRACTS:` block ends at the
    first non-blank line beginning at column 0 — replacing the enumerated allowlist
    `^(TESTS|STEPS|DEPS|INTENT):` + fence + `- [ ]` + heading. The allowlist was already
    incomplete: the `SHIPPED:` field added to SLICE1 this session is not in it, so the block would
    have silently swallowed it. One total rule instead of a list that must be maintained.
E75 GAP  I01 destroyed the one datum I02 is specified to key on. `_test_paths` (`:212`) stops at
    the first `(`, discarding the `(NEW — …)` annotation, while `notes/i02-handoff-verify-gate.md`
    §2 states I02's fail-before filter keys on exactly that marker and names no other source for
    it. Closed by CT33: `SliceRecord.tests_note` preserves the string verbatim; I01 assigns it no
    meaning, so the handoff's open question 2 (prose vs machine token) stays I02's to answer but
    becomes answerable.  [verified @ 2f6b8c1]
E76 GAP  Schema §4 required `CT#` ids unique per increment and **nothing enforced it**; CT10
    covers references to undefined ids, not duplicate declarations, and `contract_class`'s
    behaviour on a duplicate was undefined. Closed by pre-check CT34 (FAIL, naming both
    `file:line`s) plus a determinism rule in CT19 — first declaration in document order wins — so
    a malformed plan degrades into a reported violation, never a parse-order-dependent answer.
E77 DECIDED (plan) SLICE1b is split into **SLICE1b** (schema §4 + both planning skills) and
    **SLICE1c** (the planner prompt). The single slice edited `src/fa/inner_loop/prompt.py` in
    STEP4 while its `TESTS:` and verify block covered only `tests/test_skill_grammar_emit.py` and
    `ruff check knowledge/skills` — the code change was unverified, and its exit check
    (`grep -c SLICE prompt.py` non-zero) is satisfied by a comment. A slice whose verify block does
    not cover the files its steps edit is not a slice. Supersedes the SLICE1b of E58.
    supersedes: E58 (slice boundary only; the SD-A ordering it records stands)
E78 DECIDED (plan) Prose-assertion exits ("each sentence is present in both skills") are replaced
    by an **executable oracle**: schema §4 carries a fenced ```example increment, each planning
    skill a fenced ```skeleton, and the tests parse those fences with `extract_plan_ids` and
    compare against the documented result. Rationale: a `grep` for a sentence proves the sentence
    was pasted, not that the grammar it describes is the grammar the parser implements, and it
    goes stale on the first reword. The duplicated authoring prose in the two skills collapses
    into one §4 subsection, "Authoring guidance (not checked)", that both skills link to.
E79 DECIDED (operator, self-correction) The pinned-invariants slice is **moved out of I01 to I04**,
    where this roadmap has scheduled "pinned invariants" since it was written. Accepting bridge R2
    as an I01 slice was scope creep: it edits prompt composition rather than plan grammar, it fails
    I01's own "Shippable when", and it consumed `contract_class` before I02 — the accessor's first
    named consumer — exists, which is the inversion SD-B was created to prevent. Its three
    contracts are banked verbatim in `notes/role-prompts-conformance.md`. Moving it also removed
    the last `DEPS:` defect in I01: the slice declared `DEPS: SLICE1` while consuming SLICE2's
    output.  supersedes: E57
E80 FACT  Pre-implementation check of SLICE1b against SLICE1's shipped code found schema §4's
    authoring rule to be **false**. §4 told authors "wrap the example fence in ````text, or it is
    extracted as a real command". Measured: a ````text-wrapped ```verify block still yields its
    command, and a wrapped `## SLICE1:` heading still yields the slice. The shipped test
    `tests/test_plan_ids.py:233-261` asserts precisely this and documents the decision not to fix
    it in code; SLICE1/CT13 pins it. So the wrapper is a marker for humans and the real protection
    is CT13's second clause — the pre-check is never run on a grammar document. §4 corrected, and
    CT21b added so that adding the §4 example cannot leak a phantom slice into the totality corpus
    or a duplicate `CT1` into CT34.  [measured 2026-10-06 @ 2f6b8c1]
E81 FACT  CT12's three pinned tests re-simulated against the rewritten increment-01 after the
    adversarial-review edits: `:212` (SLICE1 in `.slices`, CT1 in `.contracts`) holds; `:202`
    totality holds over 33 files; `:264` holds — 10 commands, all genuine, `ruff` present. The
    inline triple backticks introduced in the new CT21/CT22 prose do **not** open phantom fences.
    SLICE1 and the rewritten plan are compatible; SLICE1b is unblocked.  [measured 2026-10-06]
E82 FACT  The repo's documented bootstrap (`just install` → `scripts/bootstrap/workspace.py
    ensure` → `uv sync --frozen`) **cannot complete in this sandbox**, and the repo instructions
    are not at fault. Two stages fail: `hook_ownership` (`hook_seat_collision`) because the
    platform installs its own `.git/hooks/commit-msg`, and then `uv_sync` (rc=2) because no
    interpreter ≥3.13 is obtainable. Every distribution channel is blocked by egress policy —
    `astral.sh` (TLS reset), GitHub release assets via `objects.githubusercontent.com`,
    `www.python.org`, anaconda, `raw.githubusercontent.com`, and `deb.debian.org` (so no apt and
    no openssl/zlib/ffi headers, which also rules out building CPython from source). PyPI and
    `codeload.github.com` are reachable, which is why `uv` itself installs fine.
    [measured 2026-10-06]
E83 FACT  A substitute environment at `.venv` gives a usable gate: CPython 3.11.2 plus two
    `.pth` files — one putting `src/` on the path (what an editable install does; `uv pip
    install -e .` is refused by `requires-python >=3.13`), one shimming `typing.override`, which
    is the **only** 3.12+ construct in `src/` (7 files; no PEP 695 anywhere) and is a no-op
    decorator at runtime. Result: **4008 passed, 3 failed, 15 skipped, 1 xfailed** in 3m33s, and
    `ruff check src tests` clean. The three failures are fully accounted for: two are the
    deliberately-red doc gates E19 must never "fix"
    (`test_doc_links::test_repo_has_no_broken_internal_file_links`,
    `test_deploy_scripts::test_historical_workspace_docs_have_top_level_superseded_banner`), and
    the third,
    `test_cli_ergonomics::test_workflow_per_role_overrides_parse`, is a CPython version artifact
    — reproduced in 12 lines of stdlib `argparse` with no project code: 3.11 cannot reclaim a
    positional that follows an optional, 3.13 can. **Zero unexplained failures.** Treat this as
    the regression baseline for I01; it is not a substitute for the real 3.13 gate, and any
    result that depends on interpreter version must be re-run by the operator.
    [measured 2026-10-06]
E84 FACT  I01/SLICE1b implemented. Schema §4 now carries a marker-delimited worked example and a
    machine-readable expectation beside it; `tests/test_skill_grammar_emit.py` slices both out of
    the `.md`, parses the example and compares, so §4 and `plan_ids.py` can no longer drift in
    silence. Both planning skills embed a `PLAN-SKELETON` block that the same test parses, which
    retires the `### Step S#:` anchor the parser stopped accepting in SLICE1 (E52's emitter half,
    for the skills). Result: **16 passed, 4 xfailed**; ruff and pyrefly clean.
    The four xfails are deliberate and `strict=True`: CT16 section spans, CT17 declaration scope
    and CT18 whole-entry text are SLICE2's to implement, so the assertions encode SLICE2's
    acceptance criteria today and will XPASS — and therefore fail the suite — the moment SLICE2
    lands, forcing the marker to be removed rather than letting a silent pass accumulate.
    Omitting them instead would have left SLICE2 with no executable oracle.  [measured 2026-10-06]
E85 FACT  I01/SLICE1c implemented: the planner prompt is now the third emitter of schema §4.
    `PLANNER_SYSTEM_PROMPT`'s plan template, its worked example and its Delta Plan template all
    emit `## SLICE<n>:` with `STEPS:`, `DEPS:`, `INTENT:`, `CONTRACTS:`, `TESTS:` and a verify
    fence, and `tests/test_planner_emits_schema4.py` parses those blocks out of the prompt string
    rather than grepping for the token `SLICE` — a comment satisfies a grep, and the property that
    matters is that what the planner is told to emit is what `extract_plan_ids` can read. This
    closes the production half of E52: `workflow_controller.py:332` returns early on an empty
    `.slices`, so until now every per-slice gate silently no-opped against real planner output.
    Evidence, Assumptions and Risks were **rerouted** under `## Grounding`, not deleted (CT32),
    with the mandatory understood/excluded readback line from schema §4.
    Result: 11 passed; ruff and pyrefly clean; full suite 4035 passed with the same three
    baseline failures as E83. The prompt's fenced templates had to move from ```` ```text ```` to
    ```` ````text ````: a plan block now contains a nested ```verify fence, which would otherwise
    close the wrapper early.  [measured 2026-10-06]
E86 GAP  The **evaluator** prompt still speaks the retired `S#` grammar
    (`prompt.py:802` "For each plan step (S1, S2, ...)", `:805` the step's `do:` field, `:905`
    the `- S1: PASS | FAIL` report shape). That is deliberately out of SLICE1c's contract, whose
    CT32 scopes the change to the planner. It is not harmless: `canonical_slice_id` forgivingly
    maps a reported `S1` onto `SLICE1`, so the mismatch is invisible today and will stay invisible
    until something stops being forgiving. Banked against I04 with the other eval-prompt deltas in
    `notes/role-prompts-conformance.md`.
E87 DECISION  Q35 — `plan_commands` holds every command **unowned by a slice**, not merely the
    prologue; `commands_for(None)` means "unowned". Raised while implementing SLICE2: CT4b was
    written before CT16, and CT16 stops the last slice at the increment-level sections, which
    newly orphans any ```verify block sitting in them — a command present in the flat
    `.commands` but reachable from no record, which is verbatim the harm CT4b exists to catch.
    Rejected: prologue-only plus a SLICE3 WARN (more machinery, warns about a legitimate DoD
    verify block, and leaves the command unreachable anyway) and prologue-only plus a recorded
    gap (knowingly shipping a visible defect). The chosen scope satisfies CT4b's letter, since
    the prologue is a subset of the unowned, and makes the partition total so nothing can be
    orphaned by construction rather than by a guard. Second-order benefit: it upgrades CT4c
    from `⊇` — which holds vacuously when `plan_commands` is empty — to the exact identity
    `set(.commands) == set(.plan_commands) | ⋃ set(record.commands)`, an oracle that fails if a
    command is dropped, duplicated into the wrong slice, or misattributed.
    Measured at d2faea4: zero post-last-slice verify blocks in this file, so present behaviour
    is unchanged and the broadening is purely future-proofing.  [operator-confirmed 2026-10-06]
E88 FACT  I01/SLICE2 implemented: the parser now conforms to the SLICE1b specification and
    exposes the read API I02 consumes. `_slice_spans` replaces `_slice_sections` and ends a
    section at the first later heading of depth ≤ the slice's own, reading the depth from the
    match (CT16); `_contracts_block` + `_section_contracts` scope declaration to the
    `CONTRACTS:` block by indentation alone and group each entry with its continuation lines
    (CT17/CT18); `commands_for`, `section`, `tests_for` and `contract_class` land on `PlanIds`
    (CT3/CT4/CT19/CT20); `plan_commands` and `SliceRecord.tests_note` are new fields
    (CT4b/CT33). Red-before was honest: 18 of the 20 new tests failed, and the two that passed
    were the preservation cases, which is what preservation means.
    The four `xfail(strict=True)` markers SLICE1b planted in `tests/test_skill_grammar_emit.py`
    reported XPASS the moment this landed and failed the file, exactly as designed; they were
    removed, not re-marked. Measured: 4079 passed, 3 failed — the E83 baseline trio, unchanged.
E89 FACT  Targeted mutation sweep over `src/fa/inner_loop/plan_ids.py`, mutmut 3.6.0, test
    selection `test_plan_ids.py` + `test_skill_grammar_emit.py` + `test_plan_reference.py`.
    First sweep: 274 mutants, 44 survived. Final: 226 mutants, **225 killed, 1 survived**.
    The sweep paid for itself three times over, and not by demanding more tests:
      * Six survivors were dead initialisers in `_section_contracts` and two no-op guards in
        `_unowned_commands`. The answer was to **delete the code**, not to assert on it — a
        two-pass entry grouping has no running scalars to initialise, and
        `_extract_commands("")` already returns `()`.
      * `_slice_sections` survived as "no tests" because SLICE2 had left it **dead**: every
        caller moved to `_slice_spans`. Removed.
      * Four `stop`-index mutants in `_section_contracts` were NOT equivalent, contrary to first
        reading: `stop` is what keeps a *more deeply indented* `CT<n> [CLASS]:` line from being
        both its own declaration and continuation text of the entry above. Killing them needed
        a fixture with a deeper entry in the middle **and** one at the end — with fewer, the
        off-by-one indices coincide and the mutant is invisible.
      * `canonical_slice_id` had **no direct test anywhere in `tests/`** (15 survivors). SLICE2
        made that matter: `PlanIds._record` canonicalises, so the accessors are now its first
        in-module caller. Pinned.
    The one accepted survivor is equivalent: `extract_plan_id`'s `text or ""` → `text or "XXXX"`
    — `_PLAN_ID_RE` cannot match either, so no observable behaviour differs. It is in
    pre-existing code outside this slice, so no `# pragma: no mutate` was added to code SLICE2
    does not own.  [measured 2026-10-06]
E90 FACT  The repo pins mutmut to 3.6.0 and enforces it: installing 3.8.0 for the sweep turned
    `test_slice_mutmut.py` from 21 skipped into a hard failure reading
    `tool_version_mismatch: expected 'mutmut, version 3.6.0', got '3.8.0'`. Proven to be the
    cause rather than a SLICE2 regression by stashing all three changed files and reproducing
    the failure. Downgrading to 3.6.0 cleared it and, as a side effect, that suite now *runs*
    in this sandbox instead of skipping — 4079 passed against E83's 4008. Recorded because the
    next operator to reach for a mutation sweep will install the newest mutmut by reflex.
E91 FACT  A grammar rule SLICE2 had to settle and the schema does not state: **a blank line
    inside a `CONTRACTS:` block does not terminate an entry** — only indentation does (CT17).
    Visual spacing between clauses is therefore legal. Pinned by
    `test_a_blank_line_does_not_truncate_an_entry` so the choice cannot drift silently.
    Candidate for a one-line addition to schema §4 if the operator wants it written rather than
    merely tested; not escalated to a Q# because it binds no consumer and no contract.
E92 DECISION  Q36 — a continuation line wrapped back to column 0 silently truncates a slice's
    `CONTRACTS:` block, losing that entry's tail **and every contract declared after it**.
    Found by an adversarial prose probe against the shipped parser, not by reading: of eight
    Markdown habits tested (blank line inside an entry, blank line between entries, sub-bullet
    lists, tabs, trailing blanks, a column-0 field, a 4-space block after a blank), seven
    behave as specified and this one deletes data without an error. Measured at 7156c03: a
    two-contract block whose first entry wraps to the margin parses to exactly one contract.
    The risk is not theoretical — the planner is a language model and wrapping prose to the
    left margin is the default Markdown habit.
    Operator chose (c): the parser stays strict, the SLICE3 pre-check FAILS on a declaration
    line whose id is absent from the parsed contracts (CT35), and schema §4 states the hazard
    in the authoring text. Rejected: making the parser tolerant of column-0 continuations,
    which reintroduces the "is this line a field name?" allowlist that CT17 removed on purpose
    — the next new column-0 field would silently extend the block again.
    A second, milder divergence is recorded but not fixed: a blank line followed by a 4-space
    indent *renders* as a Markdown code block while the parser folds it into contract text, so
    reader and harness see different things. Left alone — CT35 does not fire on it and no
    contract depends on it.  [measured + operator-confirmed 2026-10-06]
E93 DECISION  Q37 — the planning folder specified **no live-path test anywhere**. Audited:
    roadmap I02–I06 are one-line outlines that never mention one; increment-01's nine-point DoD
    is entirely static; and SLICE4 was titled "End-to-end conformance" while CT14 only asserts
    that fixture text parses and pre-checks clean — it boots no composition root and runs no
    loop, so the title promised a gate the slice does not deliver. The only live-run language
    in the folder was a Phase-1 exit criterion in `ARCHITECTURE-REVIEW.md` that was never
    carried into the roadmap.
    Operator chose (cb): add standing decision **SD-C** — no increment is DONE without one test
    that boots the real composition root with only `ProviderChain.request` mocked, asserting an
    observable effect and naming the production call site whose deletion fails it — and put the
    first real one in I02, where the verify gate actually executes commands
    (`notes/i02-handoff-verify-gate.md` §7). SLICE4 renamed to "Skill-to-parser conformance".
    I01 ships no live-path test *deliberately* and now says so in its DoD, with I02 named as
    the increment that adds it — the same shape as SD-B's `consumer:` rule.
    Note the asymmetry this corrects: I01's static gates are strong (SD-B, "a grep for the
    token SLICE is not evidence", strict-xfail forcing functions, a mutation sweep) yet every
    one of them answers "does this string parse?" and none answers "does anything call it?".
    Both failure modes SD-C targets have already occurred in this project — E89 and E52.
E94 DECISION  Q38 — CT10 and CT27 assigned the same condition two different severities: CT10
    FAILED on "a reference to an undefined `SLICE#`/`CT#`" while CT27 WARNed on "a contract id
    referenced anywhere but declared in no `CONTRACTS:` block". A contradiction inside the plan
    itself, found while reading SLICE3 before writing code.
    Resolved by splitting the subjects, operator-confirmed: **CT10 owns slice ids and keeps
    FAIL** — an undefined `SLICE#` in `DEPS:` is a broken edge, so the execution order is
    undefined and the plan cannot run at all — while **CT27 owns contract ids and keeps WARN**,
    because a plan legitimately cites a contract owned by a neighbouring increment and a FAIL
    there would force an escape hatch, which then hides the real misses. The genuinely
    dangerous sub-case, a declaration lost to a column-0 wrap, is already a FAIL under CT35, so
    nothing hazardous degrades to a warning.
E95 DECISION  Q39 — CT10b (WARN on a `verify` command naming a non-existent path) contradicted
    the module contract in schema §7: "all functions pure, total, stdlib-only", and
    `plan_ids.py`'s own docstring, "no filesystem access". **Deferred to I02** rather than
    reconciled, and the reason is stronger than the conflict: at pre-check time the check is
    false by construction. The pre-check runs *before* the coder, and a new slice's `TESTS:`
    path is annotated `(NEW — author it)` precisely because it does not exist yet — so CT10b
    would warn on every new test file, which is noise, not signal. The only true positive left
    is a typo in a path, and that fails loudly the first time I02's gate runs the command,
    costing one gate run rather than a burned slice — exactly the trade SLICE3's INTENT names.
    Path existence also belongs to I02 on the merits: that is where the filesystem is already
    in play and where `tests_note` is interpreted by the fail-before filter.
    Rejected: injecting an `exists` probe and splitting out a second impure entry point. Both
    work, both add a seam whose only purpose is to host a check that should not run here.
    `precheck` therefore stays a single pure stdlib-only function. SLICE3 drops to 8 contracts
    and 5 steps.

E96 DECISION  CT26 severity was never stated. Fixed as **FAIL**. The class convention does not
    decide it — CT25/CT26/CT27 are all `[FUNCTIONAL]` and CT27 says WARN explicitly, so the
    contract text is the authority and CT26's was silent. FAIL because a near-miss heading is
    the same failure class as CT35, not a cosmetic one: `## SLICE 1:` declares no slice, so
    every contract, step and test path under it is absent from the plan the harness gates
    against. There is nothing downstream to catch it, because there is nothing downstream.
    The matching regex is also made case-insensitive, which the plan already required of it
    implicitly: STEP5 lists "a lower-case heading" as a drift mode the corpus must cover, and
    the case-sensitive pattern as written in CT26 does not match one.

E97 DECISION  CT35 suppresses CT27 for the ids it claims. Measured on the corpus: a contract
    lost to a margin wrap was reported twice — FAIL `contract-declaration-lost` at the broken
    block, and WARN `contract-reference-undeclared` at an earlier prose mention. The warning
    is both redundant and the misleading one of the pair, since it points at a sentence rather
    than at the block that ate the declaration. One defect, one diagnostic, at the line the
    operator must edit.

E98 CORRECTION  STEP5's drafted corpus listed seven drift modes; one was dropped and inverted.
    "A slice followed by an increment-level heading" was a defect when SLICE3 was planned and
    stopped being one when CT16 shipped in SLICE2 — the parser now ends a slice section at a
    later heading of depth ≤ its own, which is the mandated shape. A corpus entry for it would
    have had to assert a diagnostic against correct grammar. It is now a positive assertion
    instead (`test_a_trailing_increment_section_is_not_a_violation`), so the lint is pinned
    not to re-flag what SLICE2 legalised. Corpus ships six files.

E99 EVIDENCE  SLICE3 implemented red-before-green. `tests/test_plan_precheck.py` was written
    first and failed to collect (`ImportError: cannot import name 'precheck'`), then 42 tests
    green. Full suite **4123P / 3F / 12S / 1X**; the three failures are the E19 baseline trio
    and are unchanged. Rules ship under stable mnemonic ids — `slice-without-tests`,
    `step-without-exit`, `deps-undefined-slice`, `deps-cycle`, `heading-near-miss`,
    `contract-reference-undeclared`, `contract-declared-twice`, `contract-declaration-lost` —
    not `CT#`. Contract ids renumber when an increment is re-planned; a rule id ends up in
    operator muscle memory, commit messages and suppressions, so it has to outlive the plan
    that introduced it. The owning CT is named in each rule function's docstring.
    The live increment artifact pre-checks clean (0 FAIL, 0 WARN), which the increment DoD
    requires and `TestAgainstTheLiveIncrement` asserts.

E100 EVIDENCE  Mutation sweep on `plan_ids.py`, mutmut 3.6.0, three rounds: 44 survivors → 17
    → **11, all equivalent** (602 mutants, 377 rejected by the type checker, 214 killed of 225
    viable). The sweep found four real gaps the hand-written suite missed — a `continue` that
    could become a `break` in three separate scans, and `_line_at`'s off-by-one reachable only
    through the slice-anchored rules rather than the line-scanning ones — and they are now
    pinned in `TestMutationDrivenGaps`.
    Three survivors were answered by deleting code rather than adding tests, per the standing
    preference. (1) `_step_blocks` carried a lookahead to the next `STEP#` that could never
    fire: a step marker is itself unindented, so the "ends at the next unindented line" rule
    already stops there. (2) The same function re-matched `_STEP_RE` on the block it had just
    built, giving an unreachable "a step" fallback name; it now returns the id. (3) The
    hand-rolled colour-map DFS for `DEPS:` cycles was replaced by `graphlib.TopologicalSorter`
    — stdlib, so purity holds — which also fixed a real defect the DFS had: it reported only
    one cycle, while the replacement drops the closing edge and retries, so independent cycles
    are all reported in the single pass CT25 asks for.
    One mutant was *more correct than the code*: it moved the cycle diagnostic's line from
    `cycle[0]` to `cycle[1]`. `cycle[i]` precedes `cycle[i+1]`, so `cycle[1]`'s `DEPS:` line is
    the one declaring the first edge of the printed path — a line the operator can edit to
    break the cycle. Adopted, and pinned by an exact-render assertion.
    The 11 remaining survivors are equivalent, two of them verified by execution rather than
    argument (`_step_blocks` offset base and `_contract_declaration_sites` count base, both
    differing only if a section begins with a newline — impossible, a section begins at its
    `#` heading). `extract_plan_id`'s `text or ""` survivor is the one carried over from
    SLICE2 and sits in code SLICE3 does not own. `pyproject.toml` restored byte-identical
    (`git diff --quiet` verified); `mutants/` and `.mutmut-cache` removed.

E101 EVIDENCE  The repository's own authoring gate caught a real defect in this slice that
    ruff, pyrefly and vulture all passed: `FA-AUTHORING-V2-EXPORTS-COMPLETENESS` flagged the
    public `FAIL`/`WARN` severity constants as missing from `__all__`
    (`tests/test_s10a_cli_coverage.py::test_s10a_authoring_check_runs_on_a_real_workspace`).
    Resolved by exporting them: a consumer cannot filter a report without naming a severity,
    and a bare `"FAIL"` literal at each call site is how a typo becomes a silently empty
    filter. Recorded because it is evidence the gate earns its place.

E102 DECISION  `PrecheckReport` ships `failures` and `ok` but **no** `warnings`, under SD-B:
    nothing consumes a warning list yet, and the one-line comprehension is there when I02's
    gate renderer needs it. Noted so the asymmetry reads as a decision rather than an
    oversight.

E103 EVIDENCE  SD-C, stated not assumed: I01/SLICE3 ships **no live-path test**, because
    `precheck` is pure, total and stdlib-only and no composition root reaches it — there is no
    `drive_session` path to boot. The increment that adds the first live gate is **I02**, spec
    in `notes/i02-handoff-verify-gate.md` §7. SLICE3's classification is C0 throughout.

E104 DECISION  Suspicion S-a closed as obsolete. "SLICE2 now carries ten contracts" asked
    whether the slice was unwieldy; SLICE2 shipped at `7156c03` with all ten green and a clean
    mutation sweep. The question was about a decomposition that no longer has a decision
    pending.

E105 DECISION  S-b — the step marker vocabulary had three disagreeing authorities. Schema §6
    defined `[ ]` → `[x]`; `prompt.py:687` instructed the coder to write `[>]`; the parser
    accepted all three and, measured, rejected `[X]`, `[-]` and `[~]`. Operator decision
    2026-10-07: **three states, ratified in §6**, with markers normalised before matching
    (inner whitespace stripped, case folded) so `[]`, `[ ]`, `[  ]` all mean to do and `[x]`,
    `[X]`, `[✓]`, `[✔]` all mean done. Anything else is a FAIL (CT36), not a third spelling of
    done: a marker outside the vocabulary usually means the author wanted a state the schema
    does not have, and guessing which is the silent mismatch the rule replaces.
    `[>]` kept rather than removed because it is already produced in production; deleting it
    would change coder behaviour for the sake of vocabulary tidiness. The separate defect in
    that prompt line — it tells the *model* to tick, which §1/§6 reserve for the harness —
    remains the unmerged E44 delta in `notes/role-prompts-conformance.md`.
    The real find here was `[X]`: a capital X renders as ticked everywhere and parsed as no
    step at all, so a step marked done with it escaped the lint entirely.

E106 DECISION  S-c — the leniency was mine, introduced in SLICE3, and is reversed. CT37.
    `_declared_deps` resolved `DEPS: S1` to `SLICE1` through `canonical_slice_id`, while
    `## S1:` declares no slice: the same token legal in one position and invisible in the
    other, inside one document. It was even pinned by a test
    (`test_an_em_dash_and_a_legacy_id_both_resolve`), which cemented the contradiction; that
    test is rewritten.
    The operator named the root cause more precisely than the review did: inside a plan `S1`
    is **ambiguous**, because a plan carries both `SLICE#` and `STEP#`. So the rule is not
    "translate carefully" but *never guess* — `parse_slice_id` validates `^SLICE(\d+[a-z]?)$`
    and returns `None` otherwise, and the abbreviation is reported wherever it appears:
    `## S1:` as `heading-near-miss`, `- [ ] S1:` as `step-near-miss`, `DEPS: S1` as
    `deps-undefined-slice`.
    `canonical_slice_id` keeps its leniency and its job at the eval-report boundary
    (`workflow_controller.py:336`), and the reason is now stated rather than assumed: a report
    reconciles against slice ids **only** — one namespace — so `S1` is unambiguous there and
    dropping it would discard a usable verdict. Tolerance is a property of that boundary, not
    of the grammar. Pinned by `tests/test_slice_id_validation.py::test_legacy_s_ids_normalise_to_canonical_space`.
    `parse_slice_id` also *validates* instead of rewriting a prefix, which removes a second
    wart: `canonical_slice_id("slices")` returns `"SLICEs"`, so a junk token used to arrive in
    an error message looking like a plausible id.

E107 DECISION  supersedes: E78 (for the `N ≤ 7` rule only). S-d observed the ceiling was
    exactly met. E78 had placed `N ≤ 7` under "Authoring guidance (not checked)" and told the
    pre-check not to key on it. Operator decision 2026-10-07: **WARN, never FAIL** (CT38).
    The rest of E78 stands — `STEPS:` default and brief size remain unchecked guidance. The
    distinction that justifies splitting them: slice count is a number the parser already has,
    so reporting it costs nothing and cannot be wrong, whereas "is this brief the right size"
    is a judgement a lint can only approximate. WARN and not FAIL because the ceiling is
    admission control (Q16): a gate would convert a planner's judgement into a refusal.
    Reported at 7 rather than 8 because 7 is legal and means the headroom is gone — the moment
    worth knowing before the next split. I01 now declares 7 slices and emits this warning
    against itself, which is the signal working as intended rather than a defect.

E108 DECISION  S-e was a live defect, and the fix generalises past it. Measured: a
    `## Grounding` heading written *inside* a slice ends that slice under CT16's depth rule,
    so the `TESTS:` line below it belongs to no slice and is lost. With contracts present this
    surfaced as CT8 insisting the slice "has no TESTS: line" — actively false, the author wrote
    one — and with no contracts it was completely silent.
    Rather than an authoring rule saying "Grounding must be `###`", CT39 asserts a
    **conservation property**: every grammar-bearing line (a field, a `STEP#`, a contract
    declaration) must sit inside a slice section. This covers drift modes nobody has predicted,
    which an enumeration of forbidden constructs cannot. Measured false positives across every
    real artifact in the repository: zero. The only matches outside increments were in
    `artifact-schema-and-grammar.md` and `prompt.py`, both grammar templates with
    `## SLICE<n>:` placeholders, and both out of scope by CT21b.
    CT8 is suppressed for a slice whose `TESTS:` line CT39 found orphaned — same principle as
    E97, one defect one diagnostic, and here the suppressed message was not merely redundant
    but untrue.

E109 EVIDENCE  SLICE3b red-before-green: 9 failures before implementation, 60 tests green
    after. Mutation sweep on `plan_ids.py`: 770 mutants, 484 rejected by the type checker,
    **274 killed of 286 viable, 12 survivors all equivalent** (the 11 carried from E100 plus
    `_orphaned_tests_owners`' `<` vs `<=`, which cannot differ because a slice's own heading
    line is inside its span and so can never also be an orphan — verified by execution against
    the corpus and the live increment, not by argument). First sweep found 5 real gaps: the
    ceiling diagnostic's line, two unnamed `what` branches in the orphan message, and a
    `continue`→`break` that would have let a non-TESTS orphan abort CT8's suppression.
    `pyproject.toml` restored byte-identical.
    One pre-existing test was rewritten rather than updated: `TestLivePathUndisturbed` had
    hardcoded the live increment's slice list, so it went red merely because the plan gained
    SLICE3b. A snapshot of plan content inside a parser test trains the next agent to edit the
    expectation instead of reading the failure. It now compares `.slices` against an
    independent heading scan — a differential oracle that survives legitimate plan edits and
    still fails if the parser drops a slice.
    Drift corpus extended to nine files. I01 now stands at 7 slices (the ceiling), 40
    contracts, and pre-checks with zero failures and one warning — its own CT38.

E110 EVIDENCE  I01/SLICE4 STEP2 — the human migration note for the `S#` → `SLICE#` rename
    ships at `notes/migration-s-to-slice.md`. It names the three conditions the roadmap
    requires for a zero-deprecation removal, and all three were **re-measured** rather than
    restated. (1) No live consumers: the extractor's authoring glob
    `worklogs/*/increments/increment-*.md` contains zero documents using the old anchors.
    (2) Inert corpus: 31 documents repo-wide still carry `## S<n>:` or `### Step S<n>`, and
    feeding every one to `extract_plan_ids` yields **0 with a non-empty `.slices`** — E24's
    "accepted silent no-op" is confirmed by execution, not assumed. (3) The note itself.
    Two corrections the measurement forced, which restating the roadmap would have hidden:
    the roadmap calls the corpus "archived", but only 16 of the 31 are under
    `worklogs/archive/`; the other 15 sit in `implementation-plans/`, `reviews/`,
    `pr-notes/`, `knowledge/research/` and `HANDOFF.md`. The condition still holds because
    what it needs is **inertness**, not archival — but the word was load-bearing and wrong.
    And of the 32 `implementation-plans/` documents the totality tests already feed to the
    parser, exactly one (`PLAN-complexity-aware-execution-chat-role.md`) emits pre-check
    failures: 9 × `heading-near-miss`, which is CT26 correctly catching a pre-grammar
    document. The note records it as expected so nobody "fixes" a historical plan.
    Doc-links gate unchanged at its 46-link expected-red baseline, measured with and
    without the new file by stash.

E111 DECISION  Live/e2e verification for I01 is **registered, not written** (operator,
    2026-10-07): collect the targets now, write the tests later, distributed across the
    increments that own them; no e2e run before I02 closes. The register is
    `notes/deferred-verification-register.md`, rows D1-D7, each naming the owning increment
    and the kill-check its test must satisfy. Standing rule attached: an increment may not
    be DONE while it owns an unticked row.
    The measurement that motivated it. `precheck` -- the whole 11-rule engine from SLICE3
    and SLICE3b -- has **zero call sites outside `plan_ids.py` and the test suite** (D2).
    SD-B is satisfied, because schema §7:388 names its consumer ("I01 SLICE3 + the I03
    admission step"), but nothing executes it in production, so every rule in it is
    currently unfalsifiable in the live system. Same for the entire read API (D4).
    Also recorded: the skill->prompt chain is live and was traced to source (D3).
    `expansion.py:136` selects the skill, and `coder_loop.py:895` injects it with
    `read_skill_for_injection`'s **default `file_name="SKILL.md"`** -- the full body,
    skeleton included -- from inside `_drive_session_inner`. The coder-stage ceremony at
    `coder_loop.py:247` is a *different* path using `INJECT.md`, and `plan-authoring/` has
    no `INJECT.md` at all; a test assuming one injection path would be wrong.
    Proposed and deliberately NOT built: an executable guard that fails the build when a
    name in `plan_ids.__all__` has neither a production call site nor a register row. It
    would need its own CT# and is a new policy choice.

E112 EVIDENCE  Three open questions raised during I01/SLICE4 and recorded in
    `notes/open-questions-2026-10-07.md`: Q40 (the skill skeleton cannot pre-check clean,
    blocks CT14), Q41 (the planner skills are half-migrated), Q42 (is INJECT.md in CT14's
    conformance scope). Next free question id: Q43.
    The measurement behind Q41, which was not previously recorded anywhere. Counting the
    bare `S#` token against the post-rename ids in every live producer text:
    `plan-authoring/SKILL.md` 10 vs SLICE 4 / STEP 5; `feature-planning/SKILL.md` 8 vs 6/4;
    `feature-planning/INJECT.md` 3 vs 0/0; `tests-writing/INJECT.md` 0; `prompt.py` **0**
    vs 15/5. SLICE1c migrated the prompt completely; SLICE1b added a `SLICE#`/`STEP#`
    skeleton to the skills but left the prose around it on the pre-rename grammar.
    `plan-authoring/SKILL.md:173` still *defines* the tier as "S#  Step / task card", so
    the planner reads one document teaching two incompatible id grammars, and the parser
    rejects the one the id table declares (E106/CT37).
    The measurement behind Q42. `feature-planning/INJECT.md` contains no PLAN-SKELETON and
    not one plan-grammar token; it passes the parser **vacuously** (nothing to parse), so
    "INJECT.md passes the parser" is not evidence of anything. The planner receives
    `SKILL.md`, not `INJECT.md` -- two different injection paths at two different stages
    (`coder_loop.py:895` L2 planning vs `coder_loop.py:247` coder slice entry) -- which
    settles SKILL.md as CT14's conformance target. What stays open is who owns INJECT.md's
    three stale `S#` tokens, since E45/E47 give coder behaviour to I03 while grammar is
    I01's.

E113 DECIDED (operator, 2026-10-07)  Q40 -> (b): the PLAN-SKELETON is a **plan, not a
    template with its own notation**. Alternation notation is removed from every line the
    parser reads as data, and the choice it used to express moves into prose beside the
    block. Q41 -> (i): I01/SLICE4 finishes migrating both `SKILL.md` off the pre-rename
    `S#` tier. Q42 -> (i): I01 fixes the grammar tokens inside the coder-stage `INJECT.md`;
    its behaviour text stays I03's (E45/E47). Contracts added: CT40, CT41, CT42, CT43.
    Rationale carried by the precedent, not by taste: SLICE1b/STEP2 already ruled that the
    schema §4 example must use literal ids "or it does not parse and proves nothing". A
    skeleton has the same job, so it inherits the same rule.
    Migration rule used for the 21 `S#` occurrences, recorded so a reviewer can check the
    judgement rather than trust it: `S#` -> `SLICE#` where the referent is the unit that
    carries CONTRACTS/TESTS/DEPS or owns artifacts (mapping, coverage, ownership, gating,
    and every place the surrounding text says "slice"); `S#` -> `STEP#` only where the text
    literally says "step" (`plan-authoring` I-IP-2 and the "follow steps in ... order"
    line). The id table row was not deleted but split into two rows, one per tier, because
    the single row was the root of the ambiguity E13 removed.

E114 EVIDENCE  I01/SLICE4 implemented. Red-before-green: 5 failures before the change
    (CT40 x2, CT14 pre-check half x2, CT41 x1), 15 passed after, in the new
    `tests/test_skill_conformance.py`. Measured before: both skeletons emitted three
    `deps-undefined-slice` failures from the single line `DEPS: SLICE<a>, SLICE<b> | -`;
    `S#` counts were plan-authoring 10, feature-planning 8, feature-planning/INJECT.md 3,
    and are now 0 across the whole `knowledge/skills/` tree.
    A defect the tests caught in their own helper: the first fence stripper matched three
    or more backticks and so deleted the nested ```verify fence, silently robbing every
    derived sample of its commands. Only the `record.commands` assertion failed, which is
    why that assertion was written; a test that merely checked "it parsed" would have
    shipped the bug.
    CT42 is the anti-theater mechanism: the sample is *computed* from the skill file on
    every run by one documented rule -- every `<...>` placeholder becomes the literal word
    `sample` -- so it cannot be tuned until the lint passes, and a kill-check proves it
    tracks the file rather than being a frozen copy.
    Adequacy layer, in place of a mutmut sweep: SLICE4 adds **no production Python**
    (`git diff -- src/` is empty, so SLICE3b's 770-mutant sweep still covers `plan_ids.py`
    unchanged), so the mutable surface is the producer artifact. Nine realistic corruptions
    of the skill text were applied and reverted byte-identically: drop the TESTS: line,
    strip a STEP exit, point DEPS at a missing slice, break the slice heading, abbreviate
    STEP1 to S1, reintroduce the pre-rename tier, rename the skeleton marker, change a
    contract class, and restore the alternation notation. **9 killed, 0 survivors.**
    Static: ruff format clean, ruff check clean, pyrefly 0 errors. Full suite
    **4156 passed / 3 failed / 12 skipped / 1 xfailed** -- +15 against the 4141 baseline,
    and the three failures re-run individually are the known expected-red trio (E19 x2 plus
    `test_workflow_per_role_overrides_parse`).
    Not done, deliberately: no live-path test. Rows D1 and D3 of
    `notes/deferred-verification-register.md` own it, I02 is the named increment, and the
    chain this slice closes is still only proven over text (SD-C, E93/E103).

E115 EVIDENCE  I01 Definition-of-Done walk, 2026-10-07, recorded in
    `notes/i01-dod-walk-2026-10-07.md`. Eight of nine lines passed on first measurement:
    all 14 verify commands across the 7 slices exit 0; the increment pre-checks clean
    (0 FAIL, 1 WARN -- its own CT38); CT11, CT14 and CT31 green; full suite 4156 passed /
    3 failed / 12 skipped / 1 xfailed, the three being the expected-red trio re-run by
    name; and zero `drive_session` boots across all six I01 test files, which is SD-C's
    "no live-path test, deliberately" confirmed rather than assumed.
    **DoD line 7 failed on measurement.** `parse_slice_id` was in `plan_ids.__all__` and
    absent from the schema document entirely, and `canonical_slice_id` was absent from §7.
    SLICE3b grew the public surface and never grew the spec. Fixed here, documentation
    only: §7 now specifies both, with their consumers and -- the part that matters -- the
    reason they differ, one strict for use inside a plan and one lenient only at the
    eval-report boundary. The DoD line as literally phrased still passed, because it
    polices §7 names lacking consumers while the drift ran the other way; that asymmetry is
    now a registered gap, D8, owned by I02. No guard test was added: I01 is complete, and
    attaching an unowned contract to a closed increment is the drift this project exists to
    prevent.
    Two things recorded rather than silently settled. DoD line 2's wording ("no `S#`
    assertion survives") predates E106 and now reads as if it forbade the four assertions
    that pin the canonicalisation mapping E106 deliberately kept. And **Q43**: E106 scoped
    the surviving leniency to the eval-report boundary, but `commands_for`, `tests_for` and
    `section` canonicalise too -- a second lenient surface the decision never named, which
    I02 is about to build on.
    Verdict: I01 is content-complete -- 7 slices, 42 contracts. `VERIFIED` is not claimed;
    the increment itself says that additionally requires I02 and I03.

E116 EVIDENCE  I02 planning readiness assessed, recorded in
    `notes/i02-planning-readiness-2026-10-07.md`. The handoff's §2 contract boundary was
    written before SLICE2-SLICE4 shipped, so every promise in it was **executed against the
    shipped code** rather than re-read: `commands_for` (slice and `None`), `section`,
    `tests_for`, `contract_class`, `SliceRecord.tests_note`, `.test_paths`. All live.
    `commands_for(None)` returns `()` on increment-01, i.e. ownership is total and no verify
    block in it is unowned.
    Second spec defect found while checking it, and fixed: schema §7 wrote
    `plan.steps_mode("SLICE2")` as a method on `PlanIds`, but `steps_mode` is a **field on
    `SliceRecord`** -- a call that never existed. Corrected in place with the old form
    quoted so the correction is auditable. Together with E115's `parse_slice_id` gap, two of
    the surface spec's entries were wrong in ways a planner building on them would only
    discover at implementation time; both were documentation, neither needed code.
    Decision backlog split by what it blocks, which is the part that was missing. Blocking
    the *shape* of the plan: H4 (result shape and home -- a subprocess runner cannot live in
    the pure stdlib-only `plan_ids.py`, so this decides the module boundary and therefore
    the slices), H2 (`NEW` semantics, including the third option that derives NEW-ness from
    `HEAD` and removes the marker from the trust path), H1 (fail-before granularity), and
    the new Q43. Blocking implementation only: H3, H5, H7, CT10b. Not a question but a live
    external risk: H6, the S16 proposal to delete `.commands` for having "no consumers" --
    measured today, `commands_for` still has zero production call sites, so that argument is
    correct until I02 becomes the consumer that falsifies it.

E117 CORRECTION  H4 ("where does the verify runner live, and what shape is its result?") was
    **never an open question**, and raising it was my process error, not a gap in the plans.
    `roadmap.md:147` already maps the superseded plan's slice **S6** -- "harness runs
    verification (GAP5/GAP13)" -- onto I02. That slice is
    `worklogs/implementation-plans/PLAN-slice-ceremony-harness-enforcement.md` §Step S6,
    line 700, and it specifies the runner in full. I followed the handoff note's open-question
    list without following the roadmap's own pointer to the parent document. Operator caught
    it. Lesson for the I02 review: an "open question" inherited from a context bank must be
    checked against the superseded plan before it is re-asked.
    What S6 already decided, re-verified at the tip 2026-10-07: the module is
    `src/fa/inner_loop/verification.py` with `VerificationResult` + `run_verification`
    (**file still absent**, so it is to be built, not found); the result is typed and carries
    the real integer `exit_code`; reuse the *policy pieces only* from `run_bash.py:233-250`
    (`build_scrubbed_env`, now at `tools/bash_env.py:70`, plus the venv-PATH prepend and the
    timeout/binary-decode handling) and explicitly **not** `_run_subprocess_fallback`, which
    is private, tool-shaped and carries side effects a verifier must not have (F-5);
    per-command `bash_timeout_seconds` plus a run-deadline check between commands via
    `_deadline_exceeded` (`workflow_controller.py:536`); no commands means `skipped: true`
    and no block (G8); and commands come from the plan, never from model output -- which is
    exactly what I01's `commands_for` now supplies.
    Routing was also already settled as **Q10, answered 2026-09-07 option (a)**: a non-zero
    exit must NOT return `REPAIR_REQUIRED`, because nothing branches on that constant. The
    harness synthesises an eval report with `route_decision="return_to_coder"`, marked
    harness-origin, and the `repair_round` cap (`workflow_artifacts.py:277`) governs it so a
    permanently failing command terminates non-DONE instead of looping.
    Consequence: **H4 and H5 are answered and H7 is partly answered.** I02 must re-verify and
    absorb S6, not re-decide it. Remaining plan-shaping decisions: H2, H1, Q43.

E118 DECIDED (operator, 2026-10-07)  The producer+consumer rule (SD-B) is satisfied by a
    *planned* pair, not only by a shipped one. Its origin, stated by the operator: features
    were once shipped to production with dead code behind them, presented as working. The
    rule exists to stop that, so when both the producer and its consumer are scheduled, the
    rule is formally met and work proceeds. The remaining obligation is not to re-litigate
    ownership but to **prove at the end, with e2e tests, that every feature works as planned
    and none was lost** -- which is what `notes/deferred-verification-register.md` exists to
    make unforgettable.
    Applied to H6 / S16: the proposal to delete `.commands` for having "no consumers" is not
    acted on. `commands_for` has zero production call sites today and I02 is its scheduled
    consumer, so the pair is planned and the accessor stays. supersedes: the framing in E116
    that treated H6 as an unresolved external risk; it is now a tracked dependency, with
    row D4 of the register carrying the e2e obligation.

E119 FACT  The missing link between the monster plan and this roadmap is
    `worklogs/reviews/SIMPLIFICATION-the-elegant-path.md` (204 lines). Operator was right
    that one existed; neither the roadmap's `## Sources` nor `i02-handoff-verify-gate.md`
    cites it, which is why two passes of reading missed it. The roadmap's frontmatter
    `supersedes:` the monster plan, and **this note is the document that caused the
    supersession**: it argues that every hard question of the preceding weeks (Q17, Q20, the
    T51 normalisation matrix, `tool_choice` work, Q21) is downstream of one design choice --
    asking a model a question that has a factual answer -- and that `PlanIds.commands` was
    already being extracted and thrown away. "29 GAPs, 46 verification rows" was the price of
    making an unreliable narrator trustworthy.
    So there is **no single latest iteration** of the verify-runner idea; there are three
    layers, none contradicting, none complete on its own:
    (1) MECHANICS -- monster plan §Step S6 line 700 (~2026-09-07): module
    `src/fa/inner_loop/verification.py`, env/timeout policy reuse, and routing settled as
    Q10(a). Nothing later contradicts it.
    (2) RATIONALE AND SCOPE -- `SIMPLIFICATION-the-elegant-path.md`: proposes S16 as "one new
    function, one call site, plus tests", explicitly against the 29-GAP apparatus.
    (3) NON-VACUITY -- `notes/verify-block-design.md` + the I02 handoff (2026-09-09 onward):
    the four-phase ritual and seven-row truth table. This layer is NEW relative to (1) and
    (2) and is where fail-before/pass-after was introduced.

E120 FACT  A design regression found by reading E119's note: SIMPLIFICATION §4 "What it does
    NOT solve" names four boundaries, and the two that matter for test strength were never
    carried into the I02 design. Its answers were (2) a command that does not actually test
    the slice -- `pytest -q` on an empty file exits 0 -- "which is why the *judge stays*,
    reviewing whether the test is honest is exactly the **kill-check discipline the skill
    already mandates**"; and (3) a coder that edits the test to pass -- mitigated by the diff
    reaching the judge. `notes/verify-block-design.md` contains **zero** occurrences of
    "kill-check"; it replaced that answer with fail-before/pass-after, which is a strictly
    weaker proxy.
    The kill-check discipline is already normative in all three skills and is not a new idea
    to be invented: `feature-planning/SKILL.md:332` requires
    `producer-kill-check=<exact producer/write/render/gate removal fails test>`, its §12
    gives a seven-step manual protocol ending "restore code; report which tests failed";
    `tests-writing/SKILL.md:68` makes a kill-check whose call site does not exist VACUOUS;
    `plan-authoring/SKILL.md:62` requires one per product claim. A `mutation-clearing` skill
    exists. ADR-15 already establishes git-worktree isolation, which is where a harness could
    apply a kill-check without touching the operator's tree.

E121 FACT  Handoff §5 and §6.4 contradict each other, and the tie breaks toward §6.4.
    §5 forbids "mutation/failure-injection proof in the core (that is the I06
    verifier-co-evolution story)"; §6.4 mandates "non-vacuity = one scoped mutation run per
    slice, **as a gate**, with appeal" and cites **E63, an operator decision**. Two facts
    decide it: there is **no verifier-co-evolution increment** -- I06 in the roadmap is
    "Telemetry & distillation" -- so §5 defers mutation to an increment that does not exist,
    i.e. to never; and §5's bullet carries no decision id while §6.4 carries E63.
    Mutation-as-gate was therefore already sanctioned, and the operator's choice of the
    declared kill-check is the compliant option, not an exception to a guardrail.
    Recorded so the next reader does not "restore" §5. supersedes: the §5 bullet forbidding
    failure-injection in the core.

E122 DECIDED (operator, 2026-10-07)  Test non-vacuity is proven by **executing a declared
    kill-check**, not by asking whether a test is new. Rejected on the operator's own
    challenge: deriving NEW-ness from `HEAD` is fragile because `HEAD` moves -- an
    intermediate commit inside a slice puts the new test into `HEAD` and the vacuity check
    silently disables itself -- and more fundamentally "is the test new" is a proxy for "is
    the test bound to the production code", and proxies drift and can be gamed. The
    kill-check asks the real question directly, works on pre-existing tests, needs no git
    archaeology, and catches a coder that weakens a test.
    Design drafted in `notes/i02-slice-verification-design.md`, for module
    `src/fa/inner_loop/slice_verification.py` (the operator's `slice-verification.py` is not
    an importable Python name; S6's bare `verification.py` is too broad a bucket).
    Two mechanisms were **executed before being recommended**, not asserted. (1) A `kill:`
    directive written as an indented continuation under its contract rides inside the
    contract body through the shipped parser: all four fields extract with a strict regex,
    `commands` and `test_paths` are unaffected, and `precheck` returns ok=True with zero
    diagnostics -- so **I01 needs no change** and stays closed. (2) An AST `remove-call`
    transformer deletes the producer call and leaves the rest of the file intact, and its
    `hits` counter separates `PRODUCER_ABSENT` (hits==0, the feature was never wired) from
    `VACUOUS` (hits==1 but the test still passes, the test is weak) -- the distinction that
    answers the operator's founding failure mode of dead code shipped as a working feature.
    Deliberately NOT merged with E63's generated-mutant sweep: that is tool-generated,
    minutes per slice, and says "some mutant survived somewhere"; a declared kill-check is
    planner-authored, one extra test run per contract, and says "**this** producer is not
    bound to **this** test". Complementary, not alternatives. Open forks for review: F1
    grammar placement, F2 operator set, F3 appeal on VACUOUS, F4 FUNCTIONAL-only scope.

E123 CORRECTION  F1 was re-examined on operator challenge and **my recommendation was wrong
    in its mechanism**, though right in its placement. (a) as drafted said I02 would extract
    the `kill:` directive from the parsed contract **body**. But `_section_contracts` joins
    continuation lines with single spaces, so the line boundary is destroyed. Measured over
    six cases: a directive followed by trailing prose does **not** match; two directives on
    one contract silently resolve to the last; a typo'd keyword or a missing `::` is
    indistinguishable from "none declared". Four of six degrade to "no kill-check found",
    and that is indistinguishable from "the planner declared none" -- a silently disabled
    gate, the precise failure this project exists to prevent. End-anchoring the regex causes
    the trailing-prose miss; un-anchoring is worse, because with the line boundary gone the
    token class runs on into the prose.
    Fix: placement is unchanged -- the directive stays indented under its contract, which is
    what stops a kill-check and the claim it proves from drifting apart -- but the reader
    becomes **`section()`**, the raw slice text, where newlines survive. Re-measured on the
    same corpus: per-contract attribution is exact, trailing prose is harmless, and a
    PRESERVATION contract correctly yields none.
    Safety does not come from placement, so a fail-loud validator is specified: a soft
    pattern meaning "the planner intended to declare" compared against the strict one, which
    converts every silent case into `kill-directive-missing`, `-malformed` or `-ambiguous`,
    each naming `file:line`, each a FAIL, each raised **pre-coder**. A keyword typo escapes
    the soft pattern and lands as `missing` -- still loud, still blocking, message imprecise
    -- so a near-miss rule in the manner of CT26/CT37 is specified as CT51.
    Option (b), a `KILLS:` block, was measured too: it also passes the shipped pre-check
    cleanly, so it would also not have required an I01 change. Rejected anyway on this
    project's own evidence that two parallel lists drift apart, as the id table did.
    **I01 is not reopened.** supersedes: the F1 recommendation in E122.

E124 FACT  I02 planned in full:
    `increments/increment-02-verify-gate-and-kill-checks.md`. Six slices, **33 contracts
    CT44-CT76**, two verify commands each. Operator decisions carried in: F2 the operator set
    stays closed at two; F3 `VACUOUS` and `PRODUCER_ABSENT` block with no appeal; F4
    kill-checks run on `FUNCTIONAL` contracts only.
    Slices: 1 the command runner, three-state with ERROR never PASS, scrubbed env and
    between-command deadline; 2 kill-directive parse and loud validation; 3 the two AST
    operators with the `hits` counter; 4 worktree isolation including the untracked-file
    trap; 5 verdict assembly; 6 controller wiring plus the SD-C live-path proof, which
    discharges register rows D1, D3, D4 and D5.
    The plan was run through the gates it will itself be judged by, rather than asserted
    ready: shipped `precheck` returns **ok=True**, with three WARNs all of class
    `contract-reference-undeclared` -- CT26 and CT37 cited as precedent for the near-miss
    rule, and CT10b named in Out of scope -- which is exactly the cross-increment case CT27
    is a WARN for. `commands_for(None)` returns `()`, so command ownership is total. The
    SLICE2 validator prototype was run against the plan itself: **20 kill directives, all
    well-formed, every FUNCTIONAL contract carrying exactly one.**
    Six items are explicitly out of scope and named with their owner, chief among them E63's
    generated-mutant sweep, which is a different mechanism from a declared kill-check and
    must not be collapsed into it.

E125 CORRECTION  Adversarial review of the I02 plan at 158b610, recorded in
    `notes/i02-plan-review-2026-10-07.md`. **Seven confirmed defects, three of which would
    have shipped a gate that was inverted rather than broken.** All fixed in the plan.
    **D1, critical.** The kill-check would have been invisible. Executed: with the package
    installed so an absolute path is on `sys.path`, running a test with `cwd` in a mutated
    copy still imports the ORIGINAL module. The plan said nothing about `PYTHONPATH`, so
    every kill-check would have run against unmutated code, every test would have passed,
    and every contract would have been reported VACUOUS -- blocking every correct slice while
    never detecting a weak test. Fixed by `PYTHONPATH=<overlay>/src` plus a **mandatory
    provenance probe** (CT62) that returns ERROR unless the target module provably resolves
    inside the overlay; relying on PYTHONPATH silently is the same fragility that caused the
    bug.
    **D2, critical.** `_run_stage` (`workflow_controller.py:511`) takes a role, not a slice,
    and no per-slice loop exists -- the only slice code is post-hoc `validate_slice_ids`
    (`:281`). CT71/74/75 named "that slice", which an agent could only have satisfied by
    silently building I03's dispatch loop. Rewritten to verify every declared slice after the
    single coder stage, with CT76 now asserting per-slice command attribution instead of the
    vacuous "another slice's commands did not run".
    **D3, critical.** `drive_session` is called BY `_cmd_run` (`cli.py:2408`), which the
    controller receives as `run_stage_fn` (`cli.py:1460`) -- so it sits below `_run_stage`
    and cannot exercise it. The SD-C test as written would have been green and meaningless:
    the VACUOUS class, shipped inside the increment built to detect it. Rewritten onto the
    only existing end-to-end precedent, `tests/test_workflow_global_history.py:123-141`.
    **D4/D5, major.** `remove-call` restricted to bare `ast.Expr` statements saw 1 of 4 real
    call forms (measured), giving false PRODUCER_ABSENT on an assigned producer; now replaces
    every matching `ast.Call` with `None`, re-measured at 4 of 4. And CT55's "byte-identical"
    invariant was false -- `ast.unparse` drops comments and layout -- so it now compares
    against the round-trip baseline.
    **D6, major.** `_run_initial_roles:908-909` keeps the LAST stage's eval report, so a
    synthetic report attached to the coder stage would have been overwritten by the eval
    stage and the route lost entirely: the run finishes green with a failed verification. New
    CT73 stops the role loop, asserted on stage count.
    **D7, minor.** Three stale references corrected: `repair_round` governs at
    `WorkflowProgress`/`:188` and is capped at `:944-957`, not `workflow_artifacts.py:277`;
    `_run_stage` is at `:511`, not S6's `:310`; and `EvalReport` has **no** provenance field,
    so harness origin is carried in `evaluation_id` rather than by widening the dataclass.

E126 DECIDED  The git-worktree sandbox is deleted as premature abstraction and replaced by a
    copy of `src/` alone -- measured at 2.4 MB, 162 files, ~7 ms. It removes `git worktree
    add/remove`, piping `git diff HEAD` into `git apply`, and the separate untracked-file
    copy that existed only because the planner-authored test is new. Beyond simplicity it is
    **more correct**: copying only `src/` makes test files structurally impossible for a
    kill-check to mutate, where a worktree copied them too and left the oracle rewritable;
    git state stops mattering, which matters here because this checkout is shallow; and
    "the operator's tree is unchanged" becomes structurally true instead of asserted.
    Recommendation recorded, not yet decided by the operator: ship SLICE1-3 and SLICE6 as a
    first PR so the plain command gate that closes D1 lands even if the kill-check needs
    another pass, with SLICE4-5 following. supersedes: SLICE4 as written in E124.

E127 FACT  D2 investigated to the bottom at operator request; it is **not an architectural
    break, it is my plan having assumed an execution model that does not exist**. The model
    today: `fa workflow` runs three sequential ROLE sessions. The planner writes a plan file;
    the coder gets one session with the task and `plan_path` and works the WHOLE plan; the
    eval gets one session with the diff plus "Plan slices to judge (N): ..."
    (`workflow_controller.py:461-465`) and judges per slice; `:944` reruns coder+eval while
    `route_decision == "return_to_coder"`, capped by `max_repairs`.
    **Slices are therefore a judging and accounting vocabulary, not an execution unit.** The
    only slice-aware code is `validate_slice_ids` (`:281`), which cross-checks the eval's
    *self-declared* slice ids against the plan and reports `unreported_slices`.
    This makes I02's gate a good fit rather than a compromise, and it is exactly what
    SIMPLIFICATION §5 proposed: read the commands per slice, "a slice is complete iff its
    commands exit 0" -- a completion CHECK, not an execution unit. The win is precise: today
    the harness can only detect what the judge *omitted* from its own claims; after I02 it
    holds a fact per slice. Per-slice DISPATCH -- one coder session per slice, with slice
    selection, DEPS ordering and partial-failure resume -- is a far larger change and is
    I03's, as the roadmap already says.
    One consequence of reading this properly: SIMPLIFICATION's fourth S16 bullet, "feed the
    results into the evidence block the judge already receives", had been dropped from my
    plan. Restored as **CT77** -- verdicts reach `_eval_evidence_block` (`:440-470`) whether
    or not they block, because a gate that only speaks when it fails leaves the judge
    self-declaring coverage on every green run.

E128 FACT  `worklogs/DEPLOYMENT-ANATOMY.md` read at operator instruction, and it decides every
    path in I02. In production the harness's own code is baked at `/opt/first-agent/src` with
    venv `/opt/fa-venv` (`Dockerfile.fa:89-96`); the repo is bind-mounted **read-only** at
    `/repo` and is NOT used for runtime import; the code the coder edits is a per-session
    workspace clone under `/sessions/<id>/`, arriving as `run_workflow(workspace=...)`.
    Consequences, all now in the plan. (1) Every kill-directive path is relative to the
    **workspace**, never to the harness's source tree, and `mutation_overlay` copies
    `workspace/src`. (2) `/repo` being read-only is an independent, deployment-level reason
    the git-worktree sandbox deleted in E126 could never have worked -- it was not merely
    over-built. (3) The mechanism that makes workspace code win over the baked image is
    `PYTHONPATH` precedence and nothing else: `scripts/fa-entrypoint.sh:237` prepends
    `<workspace>/src`, and `docker-compose.fa.yml:220` deliberately withholds it from the
    proxy so that container keeps running the immutable image. The overlay therefore
    **prepends** ahead of the inherited value in the same idiom rather than replacing it.
    (4) Measured and load-bearing: `PYTHONPATH` is on the scrubber's allowlist
    (`tools/bash_env.py:41`), which is the only reason the plain command gate tests the
    coder's edits at all. That single line in an unrelated module is the highest-impact
    silent inversion available in this system -- drop it and every verify command imports the
    baked image, so the gate passes regardless of what the coder wrote. Pinned as new
    **CT49b**, a PRESERVATION contract, because nothing protected it.

E129 CORRECTION  A third instance of the D2/D6 defect class, found by walking the real
    dispatch spine rather than the plan. `_run_linear` (`:1061`) carries the **same**
    `if result.eval_report is not None: eval_report = result.eval_report` idiom as
    `_run_initial_roles`, at `:1078-1079`. CT73's short-circuit, written against
    `_run_initial_roles` alone, would therefore have left `--mode linear` **silently
    ungated** -- the gate would compute a blocking verdict and the run would finish anyway.
    Fixed: the guard goes in both loops; downstream they diverge correctly without further
    work, adaptive into the routing loop at `:944` and linear into `_write_terminal_state`
    ending non-DONE. CT73's kill-check now targets `_run_linear`, the path that would
    otherwise have been forgotten.
    Recorded because the class is now three for three: every defect so far came from writing
    a contract against ONE code path I had read, when the dispatch fans out to four
    (`:897`, `:965`, `:1031`, `:1067`). CT71 now states explicitly why the gate belongs at
    the `_run_stage` choke point -- the same justification the codebase already gives for
    putting the deadline check there (S4b/RK6, `:536`) -- rather than in any loop body.

E130 DECIDED  I02 is split into shipping phases, Phase A being the live-testable system:
    SLICE1 + a command-only verdict + the SLICE6 wiring. It closes D1, is ~150 lines over
    three touch points in one file, and is what the host can exercise. Phase B -- directive
    parse, AST operators, overlay, and the VACUOUS/PRODUCER_ABSENT arms -- carries two thirds
    of the complexity and all the unmeasured risk, and **does not start until Phase A has
    produced a measured per-command cost from a real run**. A Phase A verdict may only be
    PASS, FAILING, ERROR or SKIPPED.

E131 FACT  Three live-contour blockers found by reading the deployment path end to end. Each
    would have wasted a real host session.
    (1) **`DEFAULT_BASH_TIMEOUT_SECONDS = 30`** (`runtime_limits.py:71`). The planner is
    instructed to emit `uv run pytest ...` (`prompt.py:205-207`) and `uv` is on the image
    PATH (`Dockerfile.fa:59-67`), so a verify command may first sync a venv in the session
    workspace. A timeout is ERROR and ERROR blocks, so inheriting a budget sized for
    interactive shell calls would have blocked **every slice on the first live run** for
    purely environmental reasons. Pinned as CT49d: the runner owns its timeout, default 600s.
    (2) **`--plan` is optional and defaults to None** (`cli.py:758-763`) and is an INPUT, not
    something populated from what the planner just wrote. Running
    `fa workflow --roles planner,coder,eval` without `--plan` leaves `plan_text()` None, so
    `extract_plan_ids` never runs and the gate skips: the live test would have exercised
    nothing while appearing to pass. This is the system-level form of the vacuous pass the
    increment exists to detect. Operationally the first live test must therefore be two-step,
    or `--plan` must point at the planner's output.
    (3) **cwd**: commands must run in the session workspace (`/sessions/<id>/`), never the
    harness's own tree. Pinned as CT49c.
    Also added **CT77b**: the run writes `verification.json` beside `eval_report.json` on
    every run, blocking or not, reachable on the host at
    `/srv/first-agent/state/session-log/<run_id>/`. Without it a live run's gate output exists
    only as stderr and cannot be reviewed after the fact, which is precisely how the operator
    intends to evaluate the first real sessions.

E132 DECIDED  The gate ships in **observe mode** first (operator's call). It computes the
    verdict, writes `verification.json` and adds the evidence lines, but returns no synthetic
    report and never routes; enforce mode is a separate operator switch, recorded in the
    artifact. Pinned as CT77c. Rationale is deployment practice, not timidity: a blocking gate
    switched on cold turns the first environmental hiccup into a repair loop and burns a live
    session on noise before anyone has seen one honest run. Enforce is enabled after the first
    real run is reviewed.

E133 FACT  The `uv run` worry is **answered by a system that already exists**, and the operator
    was right to raise it. `workspace_bootstrap.py` (`check_workspace_ready:691`,
    `ensure_workspace_ready:730`) hands the session a built `.venv`, and `cli.py:165-170` tells
    the agent verbatim: "the project venv is at ./.venv -- run tests with `uv run pytest ...`
    (or `.venv/bin/pytest`); never reinstall or rebuild the environment." The comment above it
    records the incident that produced the rule: a session burned 12 of 20 turns on
    `find / -name pytest`. **So verify commands run verbatim** -- the planner emits what the
    agent was told to emit, the env is already correct, and normalising would split the plan
    text from the executed fact for no gain. My earlier fear of a cold venv build was wrong.
    It did expose a real gap of the same class as the PYTHONPATH one: `UV_PROJECT_ENVIRONMENT`
    is pinned by the bootstrap (`workspace_bootstrap.py:243-259`) but is **not** on the
    scrubber allowlist (`tools/bash_env.py:29-50`, which carries `UV_CACHE_DIR` and not this).
    In the gate's env `uv run` is therefore unpinned and resolves `./.venv` by current
    directory instead -- which works **only because cwd is the workspace**, making CT49c
    load-bearing for command resolution and not merely for verifying the right tree. Residual,
    unmeasured: `uv run`'s implicit lockfile sync reaching for a network the container lacks.
    Recommended and NOT yet decided: add `UV_PROJECT_ENVIRONMENT` and a no-sync posture
    (`UV_NO_SYNC`) to the allowlist so the pin survives scrubbing and the gate cannot touch the
    network. Operator decision, because it widens a security-relevant allowlist.

E134 FACT  On requiring a plan, the operator judges `--plan`-optional to be legacy: today the
    no-plan path is `fa chat`, while `fa workflow` is heavy artillery for serious changes. The
    flag's own help preserves the original reason it is never inferred -- "guessing the
    contract is worse than having none". **That argument is against heuristic discovery**
    (globbing for a likely `.md`) and it stands; it is not an argument against **deterministic
    capture**. Persisting the planner stage's final text as the plan is no more a guess than
    the eval stage's final text already becoming `eval_report.json` (`:634-646`), and it is the
    same mechanism. No planner artifact exists today -- the planner's output lives only in its
    transcript, which is precisely why the gate is blind without `--plan`.
    Proposed, pending the operator: the planner stage writes `plan.md` into the run artifact
    directory and that becomes `plan_path` for later stages; `fa workflow` then refuses to
    start with neither `--plan` nor a `planner` role. Flagged as scope: this is a third thing
    beside I01 and I02 and needs an owning increment before it is built.
    Separately recorded, deliberately NOT touched here: the operator observes that the
    linear/adaptive split likely predates the contract and verification system and may also be
    legacy. Out of scope for I02; noted so it is not lost.

E135 DECIDED  Do **not** widen the scrubber allowlist for `UV_PROJECT_ENVIRONMENT` /
    `UV_NO_SYNC`. An allowlist passes AMBIENT state through, so inheriting the name imports
    whatever the parent happened to hold -- including a stale pin from a *different* session's
    workspace, under which `uv run` would silently use another session's venv. That failure is
    silent and cross-session, i.e. worse than having no pin at all. It would also widen a
    security boundary globally, for the agent's shell and not just the gate, to obtain a value
    the gate can compute exactly. And a guarantee that depends on who launched the process is
    not a guarantee: `UV_NO_SYNC` inherited would leave the gate's offline posture at the
    mercy of the caller.
    **The house pattern is already compute-and-inject**: `run_bash.py:233-236` scrubs with
    `build_scrubbed_env`, then SETS `env["PATH"]` to the workspace's `.venv/bin` prepended --
    it does not widen the allowlist to inherit PATH shaping. The gate follows it exactly.
    Pinned as CT49e. Principle, worth keeping: an allowlist is for what you cannot know; a
    computed value is for what you can.

E136 FACT  CT49c needs **no architectural change** -- the operator asked whether the cwd
    requirement forces one, and it does not. `run_bash.py:240` already runs the agent's shell
    with `cwd=root`, the session workspace. CT49c therefore states conformance with existing
    behaviour ("the gate must not invent its own working directory"), not a new requirement,
    and the contract has been reworded to say so. Nothing in the workspace model is proposed
    for change. Continuing as planned.

E137 CORRECTION  My proposal that the planner write `plan.md` into the run artifact directory
    was **wrong and would have created a duplicate surface**. The operator corrected it: the
    planner's artifact is the whole project folder, exactly like
    `worklogs/planning-topology-and-executable-contracts-loop/`. On checking, **this is already
    the canonical spec** -- `notes/artifact-schema-and-grammar.md` §1 defines
    `worklogs/<slug>/` with `roadmap.md`, `ledger.md`, `increments/increment-NN-<slug>.md` and
    `notes/`, and its ownership table already assigns `roadmap.md`, the increment plan body and
    `notes/` to the **planner**. The same section explicitly rules my proposal out: "Ephemeral
    run records (`eval_report.json`, `events.jsonl`, telemetry) do **not** live here -- they
    stay in the session-log root. This folder is the durable, readable planning layer." So no
    new surface is created, and none should be. supersedes: the `plan.md` capture proposed in
    E134.
    The folder also **resolves the autodiscovery question against autodiscovery**. One planner
    run produces a roadmap with N increments; one coder run executes ONE increment. With
    several candidate files present, auto-picking one IS the guess `cli.py:762-766` warns
    against -- "guessing the contract is worse than having none". The two-step invocation is
    therefore not a workaround but the correct shape, and it is how this very project has been
    run all along: plan, then `--plan <one increment file>`.
    Refined rule to replace "workflow requires a plan": **a `fa workflow` invocation that
    includes the `coder` role requires `--plan`**; a planner-only run does not, because it is
    producing one. Small, precise, no new surface.
    Remaining gap, owned by I01 (planner grammar): both planning skills cite the schema as
    normative (`plan-authoring/SKILL.md:655`, `feature-planning/SKILL.md:179`) but neither they
    nor `prompt.py` name `roadmap.md` or `increments/` inline, so the layout reaches the
    planner only if it opens the doc. That is a prompt delta of the kind already banked in
    `notes/role-prompts-conformance.md`, not new machinery.

E138 CORRECTION  Readiness audit of I02 before building: **we were not ready.** Dumping all 27
    kill directives as a table and checking each target against what the code can actually
    express found **three broken ones, and the first was in SLICE1 STEP-range** -- i.e. we
    would have hit it immediately.
    (1) **CT45** named `remove-call _run_one -> TimeoutExpired`. `TimeoutExpired` appears only
    as `except subprocess.TimeoutExpired:` (`run_bash.py:264`) -- an exception handler is not
    a call site, so the operator would find `hits=0` and report PRODUCER_ABSENT against
    working code. Retargeted to `neutralise ::_timeout_result`.
    (2) **CT51** named the compiled regex `_NEAR_MISS_RE` as callee, but a regex is reached as
    `_NEAR_MISS_RE.match(...)`, whose `ast.Call.func` is an Attribute with `attr == "match"`.
    The callee name would never match. Retargeted to a `_near_miss` helper.
    (3) **CT56** named `_Silence -> visit_Call`. Two faults at once: `visit_Call` is dispatched
    by `ast.NodeVisitor.visit` and never called by name, and `_Silence` is a CLASS, which the
    directive grammar `<file>::<symbol>` cannot descend into.
    That third one exposed a **grammar gap**: `<symbol>` could only name a bare top-level
    function, so no contract could ever target a method. Closed as new **CT50b** -- `<symbol>`
    accepts `name` or dotted `Class.method`, and both operators resolve both.
    Also fixed: SLICE1's letter-suffixed contracts were ordered CT49c, CT49e, CT49d, CT49b and
    are now b/c/d/e; CT44 said `root` where CT49c said workspace; CT46 said "the repo's .venv"
    where deployment makes it the **workspace's**; and STEP2's exit check was
    `grep -c ... prints 0`, which **exits 1** when the count is zero -- mechanically the
    opposite of what an `(exit: ...)` check promises. Now `! grep -q ... exits 0`.
    Note for the implementer, not yet a defect: `neutralise` of a timeout-producing function
    (CT49d) removes the bound on the test it then runs, so that kill-check terminates only on
    the runner's own 600 s cap. Correct but slow; worth a narrower target if it bites.

E139 FACT  The artifact-schema folder is a **pure gap in the planner prompt**, confirmed by
    exhaustive search rather than inference. Across `knowledge/` and `src/fa/` there are
    exactly two mentions of the schema -- `feature-planning/SKILL.md:179` and
    `plan-authoring/SKILL.md:656` -- and **both cite §4 only**, the slice-section grammar.
    Neither cites §1, the four artifacts and the ownership table. `knowledge/prompts/
    architect-fa.md`, named at `prompt.py:32` as the source of the planner prompt, contains
    **zero** occurrences of `worklogs`, `roadmap` or `increment`, and its "Step 4 -- Write the
    plan" emits a SINGLE document (`## Class`, `## Goal`, `## Evidence`, `## Scope`, ...).
    The schema doc is injected nowhere at runtime.
    So the mismatch is structural, not cosmetic: the prompt's deliverable shape is one
    document, while the schema's is a folder whose roadmap indexes N increments. Adding the
    layout to the planner prompt is the right fix and the operator's proposal is adopted;
    owner is **I01** (planner grammar), as a delta of the kind already banked in
    `notes/role-prompts-conformance.md`.
    It does **not** block the first live run: the gate needs a file containing `## SLICE#`
    sections with verify fences, and `prompt.py:194-213` already teaches exactly that. The
    folder is a separate improvement, not a precondition.

E140 BUILD SLICE1 of I02 shipped: `src/fa/inner_loop/slice_verification.py` (254 lines) and
    `tests/test_slice_verification_runner.py` (36 oracles, class C0+C0p+C3). All four STEP exit
    checks and both `verify` commands exit 0; CT49's PRESERVATION holds (`plan_ids.py`
    untouched, zero subprocess/os.environ/write hits). Full suite **4192P / 3F / 12S / 1X** --
    the baseline 4156P plus exactly the 36 new tests, with the three deliberately-red doc gates
    unchanged. No C1 test here by design: nothing boots the composition root until SLICE6 wires
    the runner into `_run_stage`, and a composition-root test over an uncalled module would be
    theatre (SD-C's "no live path yet" clause; the owing increment is SLICE6).

E141 EVIDENCE The SLICE1 kill-check battery ran in full and all seven directives are PROVEN,
    each file restored byte-identical: CT44/CT45/CT49d (`neutralise` of `run_commands`,
    `_timeout_result`, `_command_timeout`), CT48/CT49c/CT49e (`remove-call` into
    `_empty_result`, `_workspace_cwd`, `_pin_uv_environment`), and CT49b (`delete-line`
    `bash_env.py:41`). CT49b is the one worth naming: deleting a single `PYTHONPATH` entry from
    an allowlist in an **unrelated** module turns the tests red, which is precisely the silent
    inversion the contract was written to catch.

E142 DEFECT Mutation testing of the new module (165 mutants, scoped `[tool.mutmut]`, config
    restored byte-identical) found a real hole the 29 passing oracles had hidden: **12 mutants
    reported "no tests"**, all of them in `_spawn_failure_result` -- the OSError branch, the
    single place where "the harness could not ask" must not become "the command failed", had
    no oracle at all. Three further survivor classes were genuine: `_tail`'s `errors="ignore"`
    (handler names, unlike codec names, are case-sensitive), the `- started` duration
    subtraction in both the success and spawn-failure paths, and the `'PATH'` key in
    `_build_env`, whose mis-spelling silently swaps the inherited PATH for `os.defpath`.
    Seven oracles added; result **48 killed / 9 survived / 0 uncovered**, and the nine
    remaining are exactly the set classified as equivalent *before* re-running -- stdlib
    defaults written explicitly, case-insensitive codec names, an unreachable float equality,
    and operator-facing prose. All nine are now rows in
    `knowledge/mutation-survivors-workplan.md`'s accepted-equivalent ledger, with rationale.

E143 EVIDENCE Two measurements worth keeping, both of which a guess would have got wrong.
    (a) `/bin/sh` in this container is **dash**, and dash's `printf` does not implement
    `\xHH`: the first invalid-UTF-8 oracle emitted the literal text `ok\xff\xfe`, put no bad
    byte on the pipe, and killed nothing. The octal form `\377\376` does. (b) The first PATH
    oracle asserted only the first entry and so survived the key mutant, because
    `os.defpath` is itself `:/bin:/usr/bin` and satisfied every weaker assertion. Replacing it
    with a **differential** oracle -- measure the PATH with no workspace venv, then assert the
    venv case equals that value with one entry prepended -- kills the mutant without
    restating the implementation.

E144 DEFECT The repository's own `fa authoring check` gate caught a real public-surface defect
    in the new module that ruff, mypy and pyrefly all passed: `TAIL_LIMIT` was defined but
    absent from `__all__` (HARD-BLOCK, `slice_verification.py:62`). It surfaced as a full-suite
    regression in `test_s10a_cli_coverage::test_s10a_authoring_check_runs_on_a_real_workspace`,
    which audits this checkout rather than a synthetic tree. The tell was already in my own
    test file -- it imported `TAIL_LIMIT` from inside a function body, the smell of a symbol
    the author knows is public but has not declared. Fixed in both places.

E145 DEFECT The I02 shipping-order rationale rested on a factual error, found by checking the
    claim instead of repeating it. The plan said Phase A "closes D1 -- the register row this
    whole increment exists for". D1 in fact conflated two claims, and the first was already
    closed by code in the tree: `tests/test_slice_id_validation.py:199`
    `test_live_workflow_persists_the_adjusted_report` boots the real `run_workflow` with a real
    `plan_path` and asserts on the **persisted** `eval_report.json` -- invented `SLICE404`
    absent from disk, `unreported_slices == ["SLICE5","SLICE5a"]` -- neither of which is
    reachable unless `extract_plan_ids(plan_text).slices` was non-empty at
    `workflow_controller.py:332`.
    Verified by executing D1's own named kill-check rather than reasoning about it: replacing
    that line with `declared = ()` yields `6 failed, 7 passed` in that file, the live test
    among them; restored byte-identical. So **D1a is CLOSED and owes I02 nothing.**
    What Phase A actually closes is **D4**: `commands_for` gains its first production reader,
    ending the SD-B violation I01 left standing. Register and plan both corrected.

E146 RISK  Splitting D1 exposed an unproven precondition under the whole verify gate, now
    recorded as **D1b**. Every parser test to date, including the live one above, feeds the
    parser a **fixture** plan. Nothing shows that a plan the *model* writes -- following the
    skeleton injected at `coder_loop.py:895` via `read_skill_for_injection` -- parses into
    slices carrying `verify` fences. SLICE6's gate reads a slice's commands from that plan, so
    if the assumption is false the gate ships as a silent no-op: the exact defect I01 was
    created to kill, one storey up.
    Consequence for sequencing: **D1b/D3 is a precondition of Phase A, not a successor.** It is
    roughly one test file, it retires the remainder of the highest-priority register row, and
    it is strictly cheaper than discovering the no-op after SLICE5 and SLICE6 are wired. The
    dependency-driven order (four leaf slices, then assembly, then wiring) was never the
    constraint -- SLICE1-4 all declare `DEPS: -`, so the order was always a risk choice, and
    this is the risk that was mispriced.

E147 BUILD D1b closed — `tests/test_plan_grammar_live_chain.py`, C1, 5 oracles, the live
    precondition of the whole verify gate. Boots the real `drive_session` with only
    `ProviderChain.request` mocked (SD-C), arms expansion level 2 with a `src/` read, symlinks
    the real skills tree into the workspace because `default_skills_root` resolves it from
    `state.workspace_root`, and reads the bytes that actually crossed the provider boundary.
    Oracle: the `PLAN-SKELETON` on the wire is byte-for-byte the one on disk, and that text
    parses to `SLICE1` carrying `('uv run pytest tests/test_<area>.py -q',)`.
    **Kill-check PROVEN:** neutralising the `read_skill_for_injection` call in `coder_loop.py`'s
    L2 block reddens 3 of the 5 oracles; restored byte-identical. Worth recording what the
    degraded payload becomes — not nothing, but a bare pointer: `Reference:
    knowledge/skills/plan-authoring/SKILL.md`. The model is told where the grammar lives and
    not given it, which is precisely the failure a substring assertion on the skill *name*
    would have missed.
    No mutation sweep: this increment adds **no production code**, so there is nothing new to
    mutate. Saying so explicitly rather than silently skipping the step.

E148 EVIDENCE The live payload does **not** parse, and must not be asserted to. Measured: the
    skill body crosses the wire JSON-escaped — `\n` as a two-character literal, `\u00a7` for §
    — so no `## SLICE` heading ever sits at a line start and `extract_plan_ids` correctly
    returns zero slices. This killed the obvious version of the D1b test before it was written.
    The parser's input is the markdown plan the model *writes*, never the prompt it reads, so
    "feed the payload to the parser" asserts a falsehood. The real risk was always drift
    between the taught grammar and the readable one, so the oracle became identity: encode the
    known-good skeleton the way the transport encodes it, and find it verbatim in what was
    sent.

E149 FACT  Session baseline moved to **4 expected-red**, not 3. `tests/test_cli.py::
    test_fa_run_verify_only_bash_allowed_before_pr_prepare` now fails, and it is **not** a
    regression from this work: proven by removing every file of this increment from `tests/`
    and re-running it in isolation, where it still fails. It is an artifact of this turn's
    fresh `.venv` rebuild (different resolved package versions than the previous build);
    `bash` and `git` are both present on PATH, so it is not a missing-binary skip. Recorded so
    the next session does not mistake it for damage, and does not "fix" it blindly either.

E150 BUILD I02/SLICE2 shipped into `slice_verification.py`: `KillOperator`, frozen
    `KillDirective`, `_split_dotted`, `_scan_directives`, `parse_kill_directives`,
    `_near_miss`, `validate_kill_directives`. Tests `tests/test_kill_directives.py`, 37
    oracles, class **C0/C0p** plus one structural oracle for CT53. All four STEP exit checks
    and both `verify` commands exit 0. Full suite **4233P / 4F / 12S / 1X** -- the E149
    baseline plus exactly the 37 new tests.
    No C1, deliberately and with the operator's agreement: these functions have no production
    caller until SLICE5 assembles the verdict and SLICE6 wires it in. A composition-root test
    over an uncalled function passes whether or not the function exists. The live proof is
    registered instead -- see E155.
    Cross-validation worth keeping: run against the real I02 plan the parser recovers **28
    directives and reports zero diagnostics**, independently matching the readiness audit's
    count (E138); against the I01 plan it reports **19 `kill-directive-missing`**, correct
    because I01 predates the grammar. The second is the non-vacuity proof for the first.

E151 EVIDENCE SLICE2 kill-checks: CT50 (`neutralise parse_kill_directives`) -> 6 failed,
    CT52 (`neutralise validate_kill_directives`) -> 8 failed, CT51 (`remove-call
    validate_kill_directives -> _near_miss`) -> 3 failed. All PROVEN; file restored
    byte-identical by sha comparison against a pre-check snapshot, not against HEAD -- HEAD
    does not yet carry this slice, so `git diff --quiet` would have been the wrong oracle and
    said so.
    **CT50b's kill-check cannot fire in SLICE2 and is deferred, not satisfied.** It names
    `remove-call … ::_resolve_symbol -> _split_dotted`, and `_resolve_symbol` is SLICE3's AST
    concern -- `grep` finds zero occurrences. The *parse* half of CT50b is implemented and
    covered here (`_split_dotted`, plus a dotted symbol surviving the strict regex); the kill
    directive becomes executable when SLICE3 lands. Recorded rather than quietly ticked.

E152 DEFECT Mutation testing found a real defect, not a coverage gap. I01 makes a contract's
    class bracket **optional** and defaults such an entry to `FUNCTIONAL`
    (`plan_ids.py:82-85`), so `  CT1: text` is a legal declaration. SLICE2's contract locator
    required the bracket, which made every unclassed contract invisible: its `kill:` line went
    unattributed, and the contract was then reported as declaring none. A false
    `kill-directive-missing` against a correct plan is worse than a miss -- it teaches the
    operator to distrust the gate. Fixed by mirroring `plan_ids._CONTRACT_ENTRY_RE`, and the
    agreement between the two copies is now pinned by a drift oracle over both real plans.
    Sweep: 348 mutants, **108 killed / 10 survived / 0 uncovered** (from 100/18 before the
    follow-up oracles). Nine survivors are SLICE1's documented equivalents; the tenth is the
    now-unreachable `contract_line.get(cid, 0)` fallback, added to the accepted-equivalent
    ledger with its reasoning.
    The survivor class worth naming: four `continue` -> `break` mutants all survived, each one
    a scan that stops at the first finding. The sharpest is in the exemption loop, where a
    single CONSTRAINT contract would have switched the missing-directive check off for every
    contract after it -- a gate disabling itself, which is the one failure this module exists
    to prevent. Every fixture had held exactly one defect, so stopping was indistinguishable
    from skipping.

E153 FACT  `PlanIds.contracts` is every contract id **mentioned**, not every id declared --
    measured: 44 mentions against 41 declarations in the I02 plan, the difference being
    I01's CT26/CT37/CT10b, which this plan cites in prose. `contract_class` returns `None` for
    a citation and is therefore also the declaration test. SLICE2's missing-directive rule was
    correct only because of that, which was **accidental** -- it iterates `ids.contracts`.
    The reliance is now stated in the code and pinned by a test, because the next reader would
    otherwise have to rediscover it the hard way.

E154 DEFECT The plan's own STEP3 exit check was vacuous. `pytest tests/test_kill_directives.py
    -q -k validate` selected **1 test of 37**, and that one was the purity test, matched on its
    parameter id `[validate_kill_directives]` rather than on any validation behaviour. The step
    would have been ticked green without the validator being exercised at all. Replaced with
    `-k "near_miss or malformed or ambiguous or missing"`, which selects 11. Exactly the class
    of defect the readiness audit (E138) found in the kill directives, now found in the exit
    checks -- worth a sweep of the remaining slices' `-k` filters before they are relied on.

E155 DECISION Operator instruction, 2026-10-08: every producer this plan creates is to be
    marked for a future end-to-end test and verified with fixtures on the **live host**. New
    artifact `notes/e2e-live-verification-register.md` carries one row per producer -- what the
    host fixture must arrange, what it must observe, and a `unit`/`e2e` status. SLICE1's nine
    and SLICE2's four are entered; later slices append. Standing fixture requirements are
    stated once at the top (a real `/sessions/<id>/` workspace rather than `tmp_path`, `--plan`
    supplied because nothing infers it, assertions read from the persisted session-log
    artifacts, observe-mode first). A producer is not finished until its row reads `e2e`.

E156 DECISION Q45 resolved **(B)** by operator ruling, 2026-10-08, overriding the provisional
    Q44(i): source positions move into I01 and I02 keeps no grammar of its own. The ruling's
    reasoning, recorded because it is the standing rule now and not only this fix: a parser
    that turns text into structure and discards where it found it is defective by design;
    making the consumer re-read the file with its own regex to guess where the first parser
    looked breaks Single Source of Truth, and the consumer's copy is guaranteed to degrade as
    soon as planners format a plan slightly differently. The drift oracle shipped in E152 was
    a brace on a crack, acceptable to unblock a slice and not acceptable to keep.
    Implemented as SLICE2b, CT78/CT79/CT80.

E157 BUILD I01 grew source positions: `SliceRecord.start_line`, `SliceRecord.contract_lines`,
    and `PlanIds.contract_line(id)` -- the positional twin of `contract_class`, same
    first-declaration-wins rule, `0` for "this parse has no line for that id". No new scanning
    was needed: `_contract_declaration_sites` was already documented as "the single source of
    truth for which lines declare a contract" and already returned offsets; `_build_record`
    now lifts them into document numbering. The parser had the answer and was throwing it
    away.
    I02 deleted `_CONTRACT_ENTRY_RE` (`grep -c` = 0) and gained `_owner_at`, which only asks
    which supplied declaration most recently preceded a line. `parse_kill_directives` now
    takes the `SliceRecord` rather than loose text, because attribution needs the raw section
    *and* the declaration positions and only I01 can produce both from one parse; CT50's
    signature was amended to match rather than left to drift from the code.
    Kill-checks PROVEN by execution: neutralise `contract_line` -> 7 failed; `contract_lines =
    ()` in `_build_record` -> **27 failed across both test files**; neutralise `_owner_at` ->
    17 failed. The middle one is the one worth keeping: deleting I01's positions reddens I02's
    suite, which is the single-source-of-truth coupling made observable instead of asserted.
    Both files restored byte-identical by sha comparison.

E158 DECISION Q43 resolved **(ii) tighten**, by operator ruling: SLICE and STEP are to be
    distinguished everywhere -- in the skills, in the artifacts, and in the code that parses
    them. `PlanIds._record` no longer canonicalises, so `commands_for("S1")` returns `()`
    instead of SLICE1's commands. E106 had made `parse_slice_id` strict inside a plan for
    exactly this reason and then left the accessors lenient, which meant a caller holding a
    *step* id was handed the like-numbered *slice*'s commands with no way to tell. Leniency
    survives only where E106 scoped it: `canonical_slice_id` at the eval-report boundary,
    which the test now pins alongside the strictness.
    Safe to do now and cheaper than later: the accessors still have no production caller
    (grep: tests only), so the tightening lands before I02/I03 build on the old behaviour.

E159 EVIDENCE Mutation sweeps after the move. `slice_verification.py`: 341 mutants, **102
    killed / 11 survived / 0 uncovered** -- nine SLICE1 documented equivalents plus two new
    ones, both off-by-one boundaries in the new arithmetic, both equivalent for one shared
    reason: a contract entry matches `^\s+CT\d+…` and a directive matches `^\s*kill:`, both
    anchored at line start, so a declaration line can never also be a directive line and the
    `site_line == line` boundary the mutants move is unreachable. The old `contract_line.get(…,
    0)` survivor is gone -- the fallback it mutated no longer exists.
    `plan_ids.py` swept for the first time: 785 mutants, **275 killed / 16 survived / 0
    uncovered**. One survivor was real and was fixed in the code rather than pinned by a test:
    `_build_record`'s `start_line: int = 0` default was unreachable -- every production call
    passes the argument -- so the default was dead surface and is now required (784/274/15).
    Two more are `str.count(sub, 0, end)` -> `count(sub, None, end)`, a language-level
    identity.
    **Recorded for I01, not fixed here:** twelve survivors predate this change and live in
    `extract_plan_id` (4), `_declared_deps` (3), `_step_blocks` (2), `_dependency_cycles`,
    `_orphaned_tests_owners` and `precheck`. I01 shipped without a sweep on this module. They
    are listed in the workplan and belong to whoever reopens I01.

E160 DEFECT (tooling, no product impact) The scoped mutation config must pass
    `--output-format=json --summary=none --progress-bar=no` to `pyrefly`: mutmut parses the
    type checker's JSON and aborts with "type check command did not return JSON" otherwise,
    after printing a wall of legitimate-looking type errors that reads like a code failure.
    Cost an hour of misdirected debugging; recorded so the next scoped sweep copies the flags
    from `[tool.mutmut]` rather than the path list alone.

E161 CORRECTION The regression baseline is **3 expected-red, not 4**. E149 recorded
    `test_cli::test_fa_run_verify_only_bash_allowed_before_pr_prepare` as a fourth; it passes
    whenever `uv` is on `PATH` and fails when it is not, so it was measuring the harness
    rather than the code. Same cause as the three `test_semgrep_pin` / `test_targeted_gates`
    failures seen once this session: `pytest` invoked as `.venv/bin/pytest` without exporting
    `PATH` leaves `uv` unfindable. Export `PATH="$PWD/.venv/bin:$PATH"` and the baseline is
    `test_doc_links`, `test_deploy_scripts::…superseded_banner` and
    `test_cli_ergonomics::test_workflow_per_role_overrides_parse` -- the three that must never
    be "fixed" (E19).

E162 BUILD I02/SLICE4 shipped into `slice_verification.py`: `OverlayError`, `_copy_src`,
    `_overlay_target`, `mutation_overlay` (a `@contextmanager`), `_prepend_pythonpath`,
    `_overlay_env`, `_PROVENANCE_PROBE` and `_assert_overlay_wins`. Tests
    `tests/test_mutation_overlay.py`, **33 oracles**, classes **C0 + C3**. All four STEP exit
    checks and both `verify` commands exit 0. Full suite **4271P / 3F** -- the three
    permanently-red doc gates and nothing else.
    No C1, for the same reason as SLICE2 and with the same compensation: these functions have
    no production caller until SLICE5 assembles a verdict, so a composition-root test would
    exercise none of them. Every producer is entered in
    `notes/e2e-live-verification-register.md` instead.
    **Proven end to end, by hand, against this repository before any test was written:** the
    overlay is built, `fa.inner_loop.plan_ids` imports from inside it, the mutation is
    visible, and the tree is removed. That is the measured defect of E125/D1 -- an installed
    package winning over a mutated copy -- demonstrated closed rather than argued closed.

E163 EVIDENCE SLICE4 kill-checks, all executed, file restored byte-identical by sha
    comparison (`7dfb0005…`): CT60 (`remove-call mutation_overlay -> _copy_src`) -> **17
    failed**; CT61 (`remove-call _overlay_env -> _prepend_pythonpath`) -> 3 failed; CT63
    (copy the whole tree instead of `src`) -> 1 failed; containment guard deleted -> **5
    failed**; and `_assert_overlay_wins` neutralised -> 4 failed.
    **CT62's directive cannot fire in SLICE4 and is deferred, not satisfied** -- it names
    `remove-call … ::_run_kill_check -> _assert_overlay_wins`, and `_run_kill_check` is
    SLICE5's producer (`grep` = 0). The producer it protects is implemented and its own
    neutralisation is proven above. Second instance of this pattern after CT50b; worth a
    sweep of the remaining directives for producers that do not exist yet.
    The containment number is the interesting one. It first read **1 failed**, because four
    of the five escape paths were also absent from the overlay and were being refused by the
    existence check rather than by the guard under test -- the guard was untested while
    looking tested. Asserting the *rule* (`match="resolves outside"`) instead of the exception
    type alone took it to 5. Section 10 of the tests-writing skill, met in the wild.

E164 DECISION Phase B's own gate was crossed knowingly. The plan says "Phase B does not start
    until Phase A has produced a measured per-command cost from a real run", and SLICE2,
    SLICE2b and now SLICE4 are all Phase B. The operator directed the order; recorded here so
    the deviation is visible rather than discovered later.
    Partial payment on the debt: the overlay's own cost is now measured rather than feared --
    **15 ms** to copy this repository's `src` (2.4 MB, 163 files), against a 600 s command
    budget. The sandbox is not where Phase B's cost lives; running the slice's tests once per
    kill-check is. That number still needs a real run.

E165 EVIDENCE Mutation sweep, `slice_verification.py` with all three test files selected: 439
    mutants, **135 killed / 23 survived**, then **438 / 144 / 13** after the follow-up. Ten of
    the twelve new survivors were real:
    - **Eight** mutated the `__pycache__` / `*.pyc` exclusion in `_copy_src`, which no fixture
      contained, so the exclusion could have been deleted in silence. It is not hygiene: a
      `.pyc` copied beside its module is bytecode compiled from the *pre-mutation* source,
      and a mutated module running unmutated is a VACUOUS verdict against a good test.
    - One reached the `OSError`/`ValueError` arm of `_overlay_target`, which ran in no test. A
      NUL byte in a planner-authored path makes `Path.resolve` raise, and without that arm it
      escapes as a bare `ValueError` that reads like a harness bug.
    - One exposed **dead surface I had added myself**: `_assert_overlay_wins` carried a
      `timeout_s` parameter beyond CT62's signature, no caller passed it, so
      `_command_timeout(timeout_s)` and `_command_timeout(None)` were indistinguishable.
      Removed rather than pinned by a test for a caller that does not exist (SD-B). Promoted
      the underlying choice to **Q46** instead of deciding it quietly.
    Two survivors are equivalent (`env.get("PYTHONPATH", "")` -> `None`; both falsy) and are
    in the workplan with their reasoning.

E166 DECISION Q46 resolved **(b)** by operator ruling, 2026-10-08, overriding my provisional
    (a). `DEFAULT_PROBE_TIMEOUT_SECONDS = 30.0` is declared beside the verify budget and used
    directly by `_assert_overlay_wins`.
    The ruling corrects the premise I had reasoned from. 600 s sizes *the work a slice asked
    for*; a provenance probe is an **infrastructure assertion** about the execution
    environment. One timeout over both is a leaky abstraction -- it can only be tuned for one
    of them, and it would be tuned for the wrong one. My consistency argument does hold for
    scrubbing, `cwd` and output handling, which must match the command being vouched for; it
    does not hold for the budget, which measures something else. Deferring the constant to
    SLICE5 "once a distribution exists" was perfectionism pointed backwards: a hang from an
    agent bug arrives before any such measurement.
    **Measured.** Executing the regression -- probe restored to the verify budget -- made the
    hanging-probe oracle take **600.6 s** instead of ~1 s. The 9.5 minutes are on the record
    rather than in an argument.
    Kill-checks PROVEN, file restored byte-identical (`f3600837…`): probe silently borrowing
    the verify budget -> 2 failed; the two constants collapsed into one -> 2 failed. Three new
    oracles: the budget actually passed to `_run_one` (spy), the separation invariant, and a
    behavioural one driving a probe that never returns and asserting `ERROR` on the probe's
    own schedule. The last exists because a constant no code path honours is documentation.
    The value equals `runtime_limits.DEFAULT_BASH_TIMEOUT_SECONDS` by coincidence, not
    derivation; both the code comment and a test forbid collapsing them, since a change made
    for the model's interactive shell must not retune this gate's failure detection.

E167 SHIPPED I02/SLICE3 — the two mutation operators, AST-level and pure. `KillApplication`,
    `_resolve_targets`, `_dotted_text`, `_callee_matches`, `_Silence`, `_neutralise_body`,
    `apply_kill` in `src/fa/inner_loop/slice_verification.py`; 26 oracles in
    `tests/test_kill_operators.py` (NEW).
    Q47 resolved (d) + exact qualified name by operator ruling. The ruling's framing, which is
    now CT57: merging two notions into one `hits` was an architectural design bug. `targets`
    is a question of **search** -- locating the anchor in the AST -- and must be strictly 1.
    `edits` is a question of **transformation**, always 1 for `neutralise` and legitimately
    0..N for `remove-call`. The defect was live: under the old CT57 the four-call sample CT56
    exists to defend reported `hits == 4` and was rejected by the slice's own gate as an
    ambiguous target.
    `source: str | None`, `None` unless `targets == 1 and edits > 0`, with the invariant
    enforced in `__post_init__` on operator advice -- a constructor that cannot assemble a
    lying result beats a convention. It makes the worst available misreport a type error:
    running the slice's tests against unmutated source shows them green, which the caller
    would record as `VACUOUS` -- a sound test accused of being weak when the producer was
    merely absent.
    Resolution is the exact qualified name anchored at the module root. The suffix rule I had
    provisionally adopted manufactures the ambiguity it then reports, and no directive needs
    it: every one written so far spells the name out. Callee matching stays deliberately
    asymmetric (an undotted directive matches `Name.id` or `Attribute.attr`) because a
    definition has one canonical name and a call site does not -- `emit`, `self.emit` and
    `mod.emit` are the same producer.
    **Six kill-checks PROVEN, five of them executed by the new operator against its own
    source** -- apply, write, run, restore -- which demonstrates the slice end to end before
    SLICE5 has a consumer: CT55 `neutralise apply_kill` 22F · CT56 `neutralise
    _Silence.visit_Call` 9F · CT57 `remove-call apply_kill -> _resolve_targets` 22F ·
    `_neutralise_body` 6F · `KillApplication.__post_init__` 2F · exactness rule relaxed to a
    suffix 1F. File restored byte-identical (sha `9c9ab692a8196e1c`).
    Deviation from STEP1, recorded: no `_Neutralise(ast.NodeTransformer)` class. Both
    operators need the same enclosing-symbol lookup, and a second walker with its own prefix
    tracking would be the Single-Source-of-Truth failure the Q45-B ruling turned on. The step
    text was amended; no contract named `_Neutralise`, so no kill directive was lost.
    CT57's directive was amended `-> _count_hits` to `-> _resolve_targets`, the function that
    now answers the search question.

E168 MEASUREMENT the directive audit SLICE3 made possible. `_resolve_targets` was pointed at
    every `kill:` directive in both increment plans: **14 of 30 cannot fire today.** Twelve
    name SLICE5/SLICE6 producers that do not exist yet (expected, registered); CT62 is the
    DEFERRED case logged with SLICE4; CT50b is a defect in a shipped slice -- it names
    `_resolve_symbol`, SLICE2's guess at a name SLICE3 shipped as `_resolve_targets`.
    Measured before proposing a fix: the renamed directive leaves SLICE2's own tests
    **36 passed, green**, and reddens SLICE3's 18 of 27. So the rename would convert an honest
    `PRODUCER_ABSENT` into a `VACUOUS` -- a sound test file accused of weakness. CT50b makes
    two claims living in two slices, and the evidence lattice is per-slice. Promoted to Q48;
    left untouched pending a ruling, because wrong-but-honest beats wrong-and-confident.
    The audit is the long-outstanding sweep for directives naming absent producers, which had
    no tool until now. It is worth running at every slice boundary.

E169 DECISION Q48 resolved **(c)** by operator ruling, 2026-10-08: a `kill:` directive may name
    only a producer its own slice builds. The operator's diagnosis, now normative in schema §4
    and in the roadmap's standing decisions: two notions had been mixed. An *interface
    contract* ("a future module must provide `_run_kill_check`") is a legitimate architectural
    requirement; a *kill directive* ("cut this call and my current tests fail") is an
    instrument of test-suite quality hardening and is physically incapable of specifying an
    interface for code that does not exist. It can only guess the future private name, or
    mutate code the declaring slice's tests never execute.
    Both traps are measured, not argued. Name guessing: SLICE2 wrote `_resolve_symbol`, SLICE3
    shipped `_resolve_targets`. Foreign tests: renaming the directive leaves SLICE2's suite 36
    passed, fully green, while SLICE3's goes 18 of 27 red -- a `VACUOUS` verdict against a
    sound test file.
    Relocations, each measured against the tests of the slice that now owns it before being
    written down: CT50b -> `neutralise ::_split_dotted` **4F**; CT81 (new, SLICE3) takes the
    resolution half -> `remove-call ::_resolve_targets -> _split_dotted` **18F**; CT62 folds
    into SLICE4 -> `neutralise ::_assert_overlay_wins` **9F**; CT82 (new, SLICE5) takes CT62's
    wiring half, fires when SLICE5 is built. SLICE4's INTENT now carries the cross-slice
    expectation as prose, which is where §4 says it goes. CT67 was also brought onto the Q47
    vocabulary (`targets`/`edits`, not `hits`).
    Enforcement is CT83 + STEP5/STEP6 in SLICE5: a check script failing when a slice whose STEP
    boxes are all ticked declares a directive that does not resolve. The tick is the trigger
    because an unfinished slice is *expected* to point at absent code. CT84 states the rule as
    a CONSTRAINT.
    **Correction to E168's headline.** "14 of 30 dead" conflated two populations. Twelve were
    the plan legitimately ahead of the code and will fire when their own slice is built; two
    were the category error. After the relocation the audit reports **0 defects on ticked
    slices**, 14 pending on unfinished ones. The safety net was not half fiction -- but it had
    no way to tell the two apart, which is the defect that is now fixed.
    Declined and recorded: a `PRODUCES:` grammar field would move the check from tick time to
    authoring time, and the pre-check tolerates the new field with no new diagnostics, but it
    duplicates what the code already states and is I01 grammar, which is closed. No new slice
    was created: I02 sits on the 7-slice ceiling, and `_rule_slice_count` reads an eighth as a
    mis-scoped increment. The work went to SLICE5, which already owns `PRODUCER_ABSENT`.

E170 CORRECTION three defects in I02's own definition of done, found by assessing the
    increment against the code rather than against the plan's narration.
    (i) Item 9 demanded `git diff --stat src/fa/inner_loop/plan_ids.py` be empty. Measured
    from the end of I01: **+60 / -3**. The item is what is wrong, not the code -- Q45-B ruled
    that source positions belong to the parser that read the document. Rewritten to bound the
    change to the three sanctioned names rather than forbid it.
    (ii) Item 8 pinned a `4156P / 3F / 12S / 1X` baseline; the suite stands at **4304P** with
    the same 3F/12S/1X. Worse than stale, the formulation compared totals, which is the
    self-defeating tripwire this project has already been bitten by: the only available fix
    when the number moves is to bump the number, which teaches the next reader to bump it
    too. Replaced with a test-by-test rule -- no test green at `ed4ebca` may fail -- and the
    totals kept only as a recorded observation.
    (iii) Item 7 listed register rows D1, D3, D4, D5. **D8 is also owned by I02** and was
    added to the register after the list was written. The standing rule admits no increment
    that still owns an unticked row, so the omission would have let I02 close over an open
    obligation. Added.
    None of the three is a code defect; all three would have let the increment be declared
    done on a false reading.

E171 DECISION Q49 resolved **(a) with two corrections**, 2026-10-08, absorbing the long-open
    H3 (baseline storage and lifetime) and H7 (regression attribution scope), neither of which
    had ever been answered. H1 and H2 are recorded closed at the same time: H1 is answered by
    CT69 ("the kill-check phase runs only the contract's own test") and H2 was dissolved by
    E122's move to declared kill-checks, which removed any need for the gate to know which
    test is NEW.
    The seam: **SLICE5 accepts a baseline it does not gather**, SLICE6 captures it (CT86).
    That keeps the pure half testable and puts the one stage-loop edit in the slice whose job
    is wiring.
    Correction 1, **nodeid not file** (CT68). A file-keyed baseline reports `REGRESSION` where
    the truth is `FAILING` the moment an agent adds a deliberately-red test to an existing
    file -- the common case in this system, not the rare one. The consequence is structural:
    both the T0 and the "now" side must be harness-issued `--junitxml` runs, because the
    planner's verify commands run verbatim (`cli.py:165-170`) and surrender only an exit code
    and a truncated tail. CT69 now states that distinction.
    Correction 2, **capture once at T0** (CT85, enforced by CT86). `repair_round` admits
    several coder stages; a recapturing round would launder a regression into the baseline and
    report nothing. The writer refuses to overwrite, so the rule is structural rather than a
    convention the call site is trusted to keep.
    Two further review risks were checked against source and found **already closed**: the
    probe timeout (Q46(b), `88e8040`) and the `uv` pin (`_pin_uv_environment` sets
    `UV_PROJECT_ENVIRONMENT` and `UV_NO_SYNC=1`, `_overlay_env` inherits it by construction).
    Both have oracles -- `tests/test_mutation_overlay.py:580,593` and
    `tests/test_slice_verification_runner.py:235` -- so they are proven, not merely present.
E172 SHIPPED SLICE5 STEP1 + STEP2, 2026-10-08. `SliceVerdict` (seven members, design note
    §3.2) and `_run_kill_check` in `src/fa/inner_loop/slice_verification.py`, with
    `tests/test_verify_slice.py` (NEW, 20 oracles). Order inside the kill-check is
    load-bearing and asserted: `apply_kill` (pure) -> `mutation_overlay` (the only copy on
    disk) -> `_assert_overlay_wins` (CT82) -> the contract's own test. An oracle spies on
    `run_commands` to prove a failed probe never reaches the test, so a broken environment
    costs a probe rather than the full test budget, and can never present as a pass.
    Verdicts: test red under mutation -> PROVEN; test still green -> VACUOUS; `targets == 0`
    or `edits == 0` or the file missing -> PRODUCER_ABSENT; `targets > 1`, a failed probe, an
    `OverlayError` or an unrunnable test -> ERROR.
    Gates, run verbatim: STEP1 `len(SliceVerdict)==7` exit 0; STEP2
    `pytest tests/test_verify_slice.py -q -k kill_check` 15 passed, 5 deselected;
    slice `verify` fence 20 passed + `ruff check` clean. mypy and pyrefly clean.
E173 EVIDENCE Eight hand-mutants on the SLICE5 producers, all killed, source restored
    byte-identical, 2026-10-08. Probe check deleted -> 1F; VACUOUS reported as PROVEN -> 1F;
    PASS/FAIL inverted -> 2F; PRODUCER_ABSENT folded into VACUOUS -> 3F; `targets > 1`
    accepted -> 1F; `_module_name` keeping the `src` prefix -> 5F; `run_commands` ignoring the
    injected environment -> 1F; the `KillCheck` verdict guard removed -> 1F. The fourth is the
    one that matters: folding PRODUCER_ABSENT into VACUOUS is the collapse this increment
    exists to prevent, and three separate oracles refuse it.
    Full suite: 4324P / 3F / 12S / 1X. Compared **test-by-test** per the corrected DoD item 8:
    the three reds are exactly the EXPECTED-RED set of E161, and the 20 new passes are this
    slice's. No test moved from green to red.
E174 FINDING A pre-existing cross-test pollution defect in `tests/test_workspace_bootstrap.py`
    (`monkeypatch.setattr(os, "name", "nt")` at :1970 and :2011), 2026-10-08. With `os.name`
    patched, pytest's own `_repr_failure_py` builds a `Path` and raises
    `NotImplementedError: cannot instantiate 'WindowsPath' on your system`, aborting the
    reporter with `INTERNALERROR>`. Reproduced on `tests/test_workspace_bootstrap.py` plus
    `tests/test_doc_links.py` alone -- **99 passed and the INTERNALERROR still fired**, with
    no file from this increment loaded, so it is neither new nor caused by SLICE5. It is
    recorded rather than repaired: the fix belongs with whoever owns that file, and silently
    touching an unrelated test from inside I02 would be the cross-increment edit the plan
    grammar forbids. Consequence worth noting -- the reporter dies *after* the counts are
    computed, so a test-by-test baseline comparison (CT68) is unaffected, but a human reading
    only the tail of a run could mistake it for a harness failure.
