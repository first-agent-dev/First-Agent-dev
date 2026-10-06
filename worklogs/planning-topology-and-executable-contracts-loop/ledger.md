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
