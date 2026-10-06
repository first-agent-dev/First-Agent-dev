# Decisions Q&A — plan-edit session 2026-10-06

> **Walk log.** Group A decided 2026-10-06 — see the verdicts inline (`DECIDED`). A standing
> principle emerged at Q2 that reorders the increment: **the prompt/skill is primary, the parser
> conforms to it.** Recorded as **SD-A** below; it applies to every remaining question.

**How to use.** One question per decision. Each carries: the finding IDs it closes (from
`findings-register-2026-10-06.md` — nothing is dropped), the question, why it matters, the
options, and my recommendation. We walk **A → B → C → D → E → F**. Answer "yes to the
recommendation" or pick an option; I record the verdict in the Status column and move on.

**Status legend:** `OPEN` · `TAKE` (edit a plan artifact now) · `BANK` (ledger/notes entry,
explicitly not scheduled) · `DROP` (rejected with a recorded reason) · `ASK` (needs more work
before it can be decided).

**Inputs folded in:** my own verification @ `2f6b8c1` · `first-agent-bridge.md` (R1–R8) ·
`REVIEW-planning-big-tasks-for-ai-agents.md` · `ARCHITECTURE-REVIEW.md` ·
`production-patterns-review-2026-10-06.md` (the parallel agent — **U1–U11**).

### What I took from the parallel agent's review

It is good work and it supersedes three of my own framings. Adopted into the
recommendations below:

| Theirs | What it replaces | Where it lands here |
|---|---|---|
| **(b′) + the admission pattern (U1)** — planner emits §4 grammar directly plus a free-form `## Grounding` block; code does `parse → validate → default/stamp → persist` with a **no-inference rule** | My binary "(a) planner emits / (b) code compiles" framing of ASK#-01. (b′) is strictly better: it keeps Evidence/Assumptions/Risks alive without a semantic translator | **Q6** |
| **keep-md as a *staged* decision with an explicit kill condition (U4)** — an SRE error budget: `plan_extract_silent_misparse_total == 0`, burn ⇒ substrate sprint; strangler-fig trajectory (U6) | My four-way G1 question. "Reject / accept / partial" was the wrong axis; **"when, measured how"** is the right one | **Q21** |
| **Findings-not-scores mutation posture (U8–U11)** — Google's mutation-at-scale: changed lines only, survivors as *review findings* routed to the test's author, top-K cap, measured arid list, pre-registered graduation rule | **Resolves conflict F4 outright.** REVIEW ("add mutation") and ARCH ("mutation is overkill") were arguing about *gating*; neither proposed the posture under which it is cheap | **Q18 / F4** |
| **Conformance ladder L0/L1/L2 (U3)** + **near-miss lint (U5)** + **golden drift corpus (U5)** | Nothing of mine — pure addition. The near-miss lint is directly reusable for my A3/A4 findings | **Q2, Q11** |
| **Tombstone sections (U7)** | Partially answers ARCH's G2 (stable IDs) at zero schema cost | **Q22** |
| **E24 removal conditions made auditable** | My flat "E24 vs P5b contradiction" | **Q23** |

**Divergence note.** Their note references `plan-edit-2026-10-06-rationale.md` and ledger entries
up to **E63** — i.e. a parallel branch has already *landed* plan edits. Those files are **not on
`main`** (only `production-patterns-review-…md` was uploaded, commit `b02b890`); `roadmap.md`,
`ledger.md` and `increment-01` on `main` are still byte-identical to what I have. **Before I write
anything into the plans, decide whose edits are canonical** — see **Q0**.

---

## Q0 — Whose plan edits are canonical? ⚠️ blocks everything in Group C

**Closes:** P17 — **Status:** ✅ **DECIDED → (c)**

> **Verdict (operator, 2026-10-06):** *"Продолжаем работу в этой ветке. От того агента нам достался
> только один новый файл."* — this branch is canonical. The parallel agent contributed exactly one
> artifact (`production-patterns-review-2026-10-06.md`); no plan edits landed, so `E49+` and `CT16+`
> are free for us. Group C is unblocked.

The parallel agent appears to have already applied edits (its §5 lists "landing pointers", but its
header says `plan-edit-2026-10-06-rationale.md` *records what landed*, and it cites ledger entries
E58–E63 that do not exist on `main`). If I now also edit `increment-01`/`roadmap`/`ledger`, we get
two divergent append-only ledgers — which is the one artifact in this project that cannot be
merged by hand without losing the provenance guarantee.

| Option | |
|---|---|
| **a** | Push the other branch to `main` first; I rebase and only add what is missing |
| **b** | I am canonical; the other agent's work stays as the review note only (its §5 says "approve before applying", so nothing may actually have landed) |
| **c** | Neither applies yet — we finish this Q&A, then I write one consolidated diff |

**Recommendation: (c), and confirm (b) as the fallback.** Their own §5 header says *"Nothing here
is applied to the plans yet"*, which contradicts their intro — so most likely nothing landed and
(c) is free. One consolidated diff authored after the walk is also the output
`first-agent-bridge.md` §7 asks for.

---

# Group A — repo-vs-plan drift and extractor defects

## Q1 — How do we close the "SLICE1 shipped, plan doesn't know" drift?

**Closes:** A1, A2, A7, C9 (E49–E51) — **Status:** ✅ **DECIDED → (a)**

> **Verdict (operator, 2026-10-06):** *"Мы работаем в среде arena.ai, мой проект не готов закрывать
> планы сам. Поэтому сейчас — (а): проставляй ты по факту."*
>
> So: tick SLICE1's `STEP#` boxes by hand, set `status: IN PROGRESS`, append ledger FACTs with
> `supersedes:` for E1/E22/E29/E30, and re-anchor the stale `tests/test_plan_ids.py` line numbers
> (A7). **Rider I am adding so this is not a silent rule violation:** schema §6 says ticks are
> harness-owned, and the harness is I03 work. I will add one line to §6 recording the **interim
> exception** — *until the I03 harness exists, the operator owns slice ticks; the agent must still
> never tick them* — so the ownership table stays true and the exception has an expiry.

SLICE1 landed in `c0a8f429`; `increment-01` still says `status: READY` with every box `- [ ]`;
ledger E1/E22/E29/E30 describe code that no longer exists. Schema §6 says ticks are
**harness-owned** — and the harness that ticks them is I03 work, so this will recur for
SLICE2/3/4. The question is the *interim* policy, not a one-off cleanup.

| Option | |
|---|---|
| **a** | Tick SLICE1's boxes by hand + `status: IN PROGRESS`; append ledger FACTs with `supersedes:` |
| **b** | Leave the boxes (model must not tick them, per schema §6); record shipped state **only** in the ledger; add one line to schema §6 making the interim rule explicit: *until I03, slice completion is recorded in the ledger, not in the checkbox* |
| **c** | Add a `shipped:` field to the increment frontmatter that a human/harness sets, keeping boxes purely harness-owned |

**Recommendation: (b) + (c).** (b) alone leaves a reader of the plan misled; (c) costs one
frontmatter line and keeps the ownership table honest. (a) violates the rule we are about to ask
the coder prompt to obey (E44/C3) — doing it ourselves on day one is the worst possible signal.
Also re-anchor or strike the stale `test_plan_ids.py:34,:38,…` line numbers in SLICE1/STEP3 (A7).

## SD-A — Standing principle: the prompt is primary, the parser conforms ⭐ new, from Q2

**Status:** ✅ **DECIDED** — applies to every remaining question.

> **Operator, 2026-10-06:** *"План будет писать AI-агент исходя из инструкций в промпте/скилле. Это
> комплексная задача — промпт должен содержать корректные инструкции, и только потом парсер
> подстраивается под промпт. Промпт главнее, так как задаёт ментальную модель всей работы LLM над
> задачей, и от неё будет зависеть качество плана."*

**Consequence — build order inside I01 is reversed from what the plan says today.** For every
grammar question the sequence is now:

1. **Define the authoring contract** — schema §4 (the normative grammar) and the prompt/skill text
   that teaches it. This is where the mental model lives.
2. **Make the parser implement exactly that contract** — the parser is downstream, never the place
   a rule is invented.
3. **Add pre-check lints** for what the contract allows but authors get wrong.

This directly endorses bridge **R1** (`SLICE1b`, emitters, `DEPS: SLICE1`) and goes further: the
*authoring-contract* half of SLICE4 must move ahead of the parser work too, because SLICE4 today
sits behind `DEPS: SLICE3`. **Retarget in the diff:** authoring contract (schema §4 + skills +
planner prompt) → parser conformance → pre-check. I will restate the I01 slice order on this basis
when we reach **Q7** and **Q30**.

**One caveat I want on the record:** SD-A does not make A3 go away. Even a perfectly authored plan
ends with `## Increment definition of done` / `## Out of scope` / `## Hand-off`, because those are
*increment-level* sections, not slice content. So the authoring contract must say **"increment-level
`##` sections may follow the last slice"**, and the parser bug is then simply the parser failing to
implement the contract. SD-A changes *why* we fix it and *in what order* — not *whether*.

---

## Q2 — A3: the last slice's section swallows the document tail

**Closes:** A3 — **Status:** ✅ **DECIDED → contract-first, then (a)**

> **Verdict:** per SD-A. Step 1: schema §4 states that a slice section runs from its heading to the
> next heading of the **same or shallower level**, and that increment-level sections are legal after
> the last slice. Step 2: `_slice_sections` implements it (`^#{1,2}\s`, ~5 lines) under a new
> `CT16 [CONSTRAINT]` in SLICE2, with the A3 case as a fixture. Step 3: optional pre-check WARN.

`_slice_sections` ends a section at the next **`SLICE` heading** or EOF. So SLICE4's `section`
is 50 lines and contains `## Increment definition of done`, `## Out of scope` and
`## Hand-off to I02`. Two consequences: the coder's scoped brief for the final slice leaks the
whole increment tail (the opposite of "scoped context"), and the tail's `CT` mentions become
contracts of SLICE4 (it gains `CT8` and `CT11`). CT4's own wording already says the intended
behaviour: *"heading through the line before the next `## SLICE` heading"* — written when the
last-slice case was not considered.

| Option | |
|---|---|
| **a** | **Parser:** end a section at the next heading of the **same or shallower level** (`^#{1,2}\s`), not only at the next `SLICE` heading. ~5 lines + fixtures |
| **b** | **Convention:** author rule — nothing may follow the last slice; move the tail into a sibling file |
| **c** | **Pre-check WARN** when a slice section contains a non-`SLICE` `##` heading |

**Recommendation: (a), as a new `CT16 [CONSTRAINT]` in SLICE2.** There is no legitimate use for
the current behaviour — it is a plain off-by-one in the span definition. (b) would force us to
delete useful increment-level sections that every plan wants (DoD, out-of-scope, hand-off).
(c) leaves `section()` and `commands_for()` still returning wrong data to I02/I03, which is the
actual consumer. Add (c) as a cheap extra signal only if you want belt-and-braces.

## Q3 — A4: `CT#` tokens in prose become contracts of the slice

**Closes:** A4, G (register §G), and makes A5 answerable — **Status:** ✅ **DECIDED → both rules, in order, + WARN**

`_section_contracts` scans every line of the section for `\bCT(\d+[a-z]?)\b`. So CT2's
*illustrative* text — "`CT3 [CONSTRAINT]: …` parses with class `CONSTRAINT`" — gives SLICE1 a
contract `CT3` classed `CONSTRAINT`, while SLICE2 declares the real `CT3` as `FUNCTIONAL`.
**The same ID carries two classes in one increment**, so `contract_class("CT3")` is undefined
today. Step text like `(exit: CT11 green.)` re-declares contracts the same way. This is the exact
twin of the CT13 verify-fence trap — which was deliberately fixed by *convention + a pinning
test*, on the explicit grounds that parsing was "more machinery than the risk warrants".

Unlike A3, this one has a **legitimate competing use**: prose cross-references between slices and
`(exit: CT# green)` criteria are genuinely useful to a human reader, and the bridge's own proposed
slices use them.

| Option | |
|---|---|
| **a** | **Parser:** a contract is *declared* only inside the `CONTRACTS:` block (from the `CONTRACTS:` line to the next top-level field line — `TESTS:`/`STEPS:`/`DEPS:`/a fence/a `- [ ]` item). Mentions elsewhere are references, not declarations |
| **b** | **Convention + pinning test**, exactly like CT13: document the trap, never write a bare `CT#` in prose, add a test that pins today's behaviour |
| **c** | **Pre-check WARN** on a `CT#` appearing in a slice that does not declare it |
| **d** | **(a) + (c)** — parser defines declaration; pre-check warns on a reference to a `CT#` undefined anywhere in the increment (this is already CT10's job) |

**Recommendation: (d).** (a) is what makes `contract_class` / `tests_for` definable at all, and it
is the only option that fixes what `SliceRecord.contracts` actually *returns* to I02. (b) is
tempting by precedent, but CT13's situation was different: there the correct behaviour was
genuinely ambiguous (is a fenced example a command?), and the fix needed a *nested-fence parser*.
Here the correct behaviour is unambiguous and the fix is a block boundary. (c) alone repeats
option (c)'s flaw in Q2.

> **Verdict (operator, 2026-10-06):** *"Первым шагом нужно зафиксировать блок с контрактами в духе
> «объявление только внутри блока CONTRACTS», затем «ID берётся только с первой строки записи
> контракта». Так же можно добавить warn для безопасности."* — i.e. option **(d)**, with the two
> boundary rules adopted **both** and in that order, plus the pre-check WARN.
>
> **Resulting authoring contract (goes into schema §4 first, per SD-A):**
> 1. **Declaration scope.** A contract is *declared* only inside the `CONTRACTS:` block. The block
>    runs from the `CONTRACTS:` line to the first subsequent line matching
>    `^(TESTS|STEPS|DEPS|INTENT):`, a fence ```` ``` ````, a `- [ ]` item, or a heading. Indented
>    continuation lines stay inside the block — required, since CT2/CT5/CT7 all wrap today.
> 2. **One entry, one ID.** One contract per entry; the ID and `[CLASS]` are read from the entry's
>    **first line only**. Anything on continuation lines is prose. This is what stops CT2's
>    illustrative `CT3 [CONSTRAINT]: …` from becoming a contract of SLICE1.
> 3. **References are not declarations.** A `CT#` anywhere else (prose, `(exit: CT11 green)`) is a
>    reference. Pre-check **WARN** if it is not declared anywhere in the increment — this is CT10's
>    existing dangling-reference job, extended.
>
> Rules 1 and 2 are independent and both needed: rule 1 alone still mis-reads a wrapped entry whose
> continuation mentions another `CT#`; rule 2 alone still picks up a stray `CT9 [CONSTRAINT]:` typed
> outside the block. Two new contracts in SLICE2 (**CT17** declaration scope, **CT18** first-line ID);
> the WARN rides on CT10.

**Boundary questions — now answered by the verdict above; kept for the audit trail:**
1. **Where does the `CONTRACTS:` block end?** Proposal: at the first subsequent line matching
   `^(TESTS|STEPS|DEPS|INTENT):` or ```` ``` ```` or `- [ ]` or a heading. Multi-line contracts
   (indented continuations) stay part of the block — which our live plan needs, since CT2/CT5/CT7
   all wrap.
2. **Does a `CT#` need to appear on the *first* line of its entry?** Today the class regex and the
   ID regex are independent, which is how CT2's example got classed. Proposal: one contract per
   entry, ID taken from the **entry's first line only**; anything after that on continuation lines
   is prose. This single rule fixes A4 without any notion of "declaration block" — it may be the
   smaller fix. **I lean to this.**

## Q4 — A5: schema §7 promises accessors that no contract covers

**Closes:** A5 — **Status:** ✅ **DECIDED → (a) for `contract_class`+`tests_for`, (c) for `steps_mode`, + SD-B**

> **Verdict (operator, 2026-10-06):** *"(a) для contract_class и tests_for, (c) для steps_mode —
> проверь, что эти шаги запланированы корректно и мы не пропустим wiring-этап, когда дойдём до I03."*
>
> The wiring concern is **already an observed failure in this repo**, which makes it the right thing
> to worry about: ledger **E2/E3/E5** record that the flat `.commands` field shipped and has **zero
> readers** to this day. So "built in I01, wired in I02/I03" is not hypothetical risk — it is the
> project's existing pattern. Answer: **SD-B** below.

---

## SD-B — Standing decision: no accessor ships without a named consumer and a wiring step ⭐ new, from Q4

**Status:** ✅ **DECIDED** — applies to every "add an accessor / add a field" item below.

Concretely, three cheap mechanisms:

1. **`consumer:` annotation in schema §7.** Every entry in the read surface names the increment and
   the call site that will read it — e.g. `tests_for → I02, verify-gate baseline selection`;
   `steps_mode → I03, coder brief composition`. An accessor with no named consumer may not be added.
2. **A wiring `STEP#` in the consumer increment, not the producer.** When we write the I02/I03
   outlines in this diff, each adds an explicit step *"read `X` at `<file>` and act on it
   (exit: …)"*. This is what was missing for `.commands` — it was produced and never scheduled for
   consumption.
3. **A zero-reader check.** `.commands` is the live precedent; the cheapest guard is a test or
   pre-check assertion that every name in schema §7 has at least one non-test call site **by the end
   of its declared consumer increment**. Until then it is allowed and listed as pending. This also
   satisfies AGENTS.md rule 3 ("every write target has a consumer") mechanically instead of by
   discipline.

**Applied to Q4 immediately:** `contract_class` → consumer I02 (CONSTRAINT-first ordering of verify
and of mutation findings, per Q18) · `tests_for` → consumer I02 (`verify-block-design` baseline
selection, and the `TESTS:`-not-coder-writable check in Q17) · `steps_mode` → consumer I03 (brief
composition), therefore **declared in §7 as pending-I03 and not built in I01**. And `.commands`
itself gets a decision in the diff: name a consumer or retire it.

Schema §7's read API lists `commands_for`, `section`, `contract_class`, `tests_for`, `steps_mode`,
`precheck`. increment-01/SLICE2 contracts only `commands_for` (CT3) and `section` (CT4). So three
accessors would ship uncovered or absent — and `contract_class` is ill-defined until Q3 is
settled.

| Option | |
|---|---|
| **a** | Add CTs to SLICE2 for `contract_class` / `tests_for` / `steps_mode` |
| **b** | Trim schema §7 to what I01 actually builds; re-add accessors when a consumer exists (I02 for `tests_for`, I03 for `steps_mode`) |
| **c** | Keep §7 as the target surface but mark the three as "I02/I03" inline |

**Recommendation: (a) for `contract_class` and `tests_for`, (c) for `steps_mode`.** The I02
hand-off note already names `SliceRecord.test_paths` as a contract-boundary deliverable, and
`contract_class` is the thing Q3 is about — both are I02's consumers, so building them in I01 is
"build it where its spec lives". `steps_mode` has no consumer until I03 picks a brief shape; the
field already exists on `SliceRecord`, so the accessor is sugar.

## Q5 — A6: dead source reference in the roadmap

**Closes:** A6 — **Status:** OPEN

`roadmap.md` §Sources cites `PLANNING-TOPOLOGY-EXPLAINED.md`; no such file exists. Its content
survives as PRODUCTION-NOTE §2 ("condenses the design doc *Planning topology explained*").

**Recommendation:** one-line fix — repoint to
`knowledge/research/PRODUCTION-NOTE-planning-big-tasks-for-ai-agents.md` §2 and note the original
is not in the repo. Trivial; no options worth listing.

---

# Group B — the emitter gap and the two-formats question

## Q6 — ASK#-01: how does a planner-written plan become an increment file? ⚠️ the session's biggest decision

**Closes:** B2, B3, C10 (roadmap `assumed:` row), ledger GAP E56, P1–P4 — **Status:** ✅ **DECIDED → (b′)**

> **Verdict (operator, 2026-10-06):** **(b′)** — planner emits schema §4 directly plus a free-form
> `## Grounding` block; code runs admission (`parse → validate → default/stamp → persist`) under a
> load-bearing **no-inference** rule. This is also the exact embodiment of **SD-A**: the prompt
> defines the grammar, the code only checks it. ASK#-01 is closed; ledger GAP **E56** resolves to
> `DECIDED`, and the roadmap's `assumed:` row becomes a decision row.
>
> **Carried into the diff:** (1) the `## Grounding` block is *documented as unparsed* in schema §4 so
> no future reader is tempted to mine it; (2) `source_plan_sha` + `admission_version` + `tree_hash` +
> `HEAD` are stamped into increment frontmatter (P3 / Q26's G3); (3) the no-inference rule gets a
> **fixture**: a plan missing `TESTS:` must produce an `AdmitError` naming the rule, never a defaulted
> empty tuple — silent defaulting is how "no inference" rots; (4) admission is split per P-review §5:
> validation → I01/SLICE3, default+stamp → I03 controller.

Verified: `grep -c SLICE src/fa/inner_loop/prompt.py` → **0**. The planner emits
`Class/Goal/Evidence/Scope/Assumptions/Constraints/Plan/Verification/Risks`, with steps `S1.`
carrying `intent:`/`deps:`/`do:`/`accept:`/`verify:`. The durable grammar wants
`SLICE#`/`CT# [CLASS]`/`TESTS:`/`STEPS:`/`DEPS:`/```` ```verify ````. **Nothing defines the
transform.** Until it exists, "every `CT#` has a test" cannot be enforced on plans the planner
actually writes, and the coverage gate silently no-ops (E52 — live, not archival).

**My own refinement (B3), which I think is the crux:** the planner's `S1.` items are
**step-sized** — one mechanical `accept:` predicate each. The honest mapping is `S#` → **`STEP#`**.
Which means the runtime format has **no source for the `SLICE#` tier at all**: grouping steps into
commit-sized slices is a *judgement*, not a transform. Any "compiler" would have to invent the
slice tier — i.e. be a shadow planner.

| Option | |
|---|---|
| **a** | Planner emits schema §4 directly. Evidence/Assumptions/Risks have nowhere to live → lost, or the schema grows to absorb them |
| **b** | Code compiles runtime → increment. **Rejected by B3 and by the parallel review**: a semantic translator between two LLM-adjacent grammars accretes inference until it is a shadow planner |
| **b′** | **Planner emits §4 directly *plus* a free-form `## Grounding` block** (conventions / scope-out / assumptions / risks, prose, not parsed). Code runs **admission**: `parse → validate (pre-check) → default & stamp (risk floor, tree-hash, fast-path fold) → persist`, with a load-bearing **no-inference rule**: anything not derivable by rule fails loudly back to the planner |

**Recommendation: (b′).** It is the parallel agent's proposal and it is right. It keeps the
planner's thinking (Evidence/Risks) without schema churn, it removes the translator, and it has
three decades of precedent — Terraform `plan`/`apply`, Kubernetes admission webhooks ("webhooks
don't invent spec"), compiler frontends lowering to one IR. B3 is the reason (b) must die:
you cannot transform a tier that does not exist in the input.

**What I would add to their proposal:** make the no-inference rule *testable* — a fixture where
the planner omits `TESTS:` must produce an `AdmitError` naming the rule, never a defaulted empty
tuple. Silent defaulting is how "no inference" rots.

## Q7 — Do we insert `SLICE1b` "Emitters write the new grammar"?

**Closes:** B1, C1 — **Status:** ✅ **DECIDED → full reorder under SD-A**

> **Verdict (operator, 2026-10-06):** reorder. New I01 order, numbering preserved (G2/P10 — no
> renumbering, letter suffixes only):
>
> | Order | Slice | Content |
> |---|---|---|
> | 1 | `SLICE1` | ✅ shipped — extractor core |
> | 2 | **`SLICE1b`** ⭐ new | **The authoring contract.** schema §4 normative grammar (incl. Q2's section-boundary rule, Q3's CT17/CT18 rules, the `## Grounding` block from Q6, `STEPS:` modes from R7) + `plan-authoring`/`feature-planning` skills + the planner prompt emit it. `DEPS: SLICE1`. New CT19–CT21 |
> | 3 | `SLICE2` | Parser conforms to the contract: `commands_for`, `section` (CT3/CT4) + **CT16** section boundary + **CT17/CT18** contract declaration + `contract_class`, `tests_for` (Q4). `DEPS: SLICE1b` |
> | 4 | `SLICE3` | Pre-check / L1 lint: CT8–CT10, near-miss lint, dangling-`CT#` WARN, golden drift corpus. `DEPS: SLICE2` |
> | 5 | `SLICE4` | Residual migration of *historical* docs + the human migration note only (its authoring-contract content moved to SLICE1b). `DEPS: SLICE1b, SLICE3` |
> | 6 | `SLICE5` | Pinned invariants re-injection (Q9/R2) — independent, `DEPS: SLICE1` |
>
> `SLICE1b` is now the biggest slice in the increment, which is correct under SD-A — it is where the
> mental model is set. If it exceeds the sizing prior we split it `SLICE1b`/`SLICE1c` (schema-and-
> skills / planner-prompt) rather than folding it back behind the parser.

Bridge R1: insert `SLICE1b` right after SLICE1 (`DEPS: SLICE1`), retarget SLICE4 to
`DEPS: SLICE1b, SLICE3`. New CT16–CT18 (⚠️ renumber if Q2 takes CT16), new
`tests/test_skill_grammar_emit.py`. Rationale: the path planner-writes → extractor-parses →
controller-sees needs only SLICE1, and it is the cheapest thing that restores the controller's
hearing.

| Option | |
|---|---|
| **a** | Take R1 as written |
| **b** | Take R1 but make it **depend on Q6's answer** — the skills cannot be migrated to emit a grammar whose authoring contract is unsettled |
| **c** | Fold the emitter work into SLICE4 (which already migrates the skills) and skip the new slice |

**Recommendation: (b).** The slice is right and it is the highest-value unblocked work, but its
STEP2 ("add the `STEPS:` mode rule") and STEP3 (ceremony text) presuppose the authoring contract.
Sequence: decide Q6 → write SLICE1b against it. (c) is wrong because SLICE4 depends on SLICE3
(pre-check) and the emitter work does not — that decoupling *is* R1's whole point.

## Q8 — The eval prompt still speaks `S#`

**Closes:** B4 — **Status:** OPEN

`prompt.py:~866` mandates `- S1: PASS`; `validate_slice_ids` canonicalises `S1`→`SLICE1`. So the
eval's `S#` is simultaneously the planner's *step* vocabulary and the controller's *slice*
vocabulary — E7's original conflation, surviving in the prompts after the grammar renamed.

**Recommendation: BANK, owner I03** (per E47), but **add the `S#`-is-ambiguous observation to
`role-prompts-conformance.md`** — the existing banked eval delta doesn't mention it, and whoever
implements I03 needs to know the token is overloaded three ways, not two.

---

# Group C — the bridge's R1–R8 and its proposed diff

*(Q7 already covered R1. The rest follow. These are mostly "take / bank / drop" and should go
fast.)*

## Q9 — R2: `SLICE5`, pinned invariants re-injected every call

**Closes:** C2 — **Status:** ✅ **DECIDED → TAKE + both ARCH riders**

> **Verdict (operator, 2026-10-06):** take R2 with the size cap (~1.5K tokens, overflow → retrieval)
> and with the current slice's **CONSTRAINT-class contracts verbatim** in the pinned set. Lands as
> `SLICE5`, `DEPS: SLICE1`, independent of the grammar chain.

Adoption #7, called "the cheapest insurance in the list" by the research note and endorsed by both
reviews. Verified cheap: `INJECTION_SPECS` holds exactly one spec today, so this is one registry
row + one `FeatureFlags` field. Byte-stability also protects the role prompt-cache prefix (R8).

**Recommendation: TAKE**, with two additions the reviews require: ARCH G8 says the assembled block
must be **size-capped** (~1.5K tokens; overflow → retrieval), and ARCH item-7 says the pinned set
should include **the current slice's CONSTRAINT-class contracts verbatim** — they are the
acceptance surface most likely to be obeyed while visible and dropped after compaction.

## Q10 — R3: the role-prompt deltas

**Closes:** C3 — **Status:** ✅ **DECIDED → BANK, merged into one bank**

> **Verdict:** merge bridge §8A into `role-prompts-conformance.md`; E47 stands (no `src/` churn now).
> **Operator rider (2026-10-06):** *"Мой харнес увидит изменения только уже во время live e2e тестов
> системы. Пока всё в тестовом режиме."* — so the coder-prompt sentence *"the harness runs the
> acceptance checks; you do not re-run them"* is not a production-safety blocker. It is reclassified
> from **blocker** to **delivery condition**: it ships in the same change-set as the I02/I03 gate,
> and the live e2e run is the designated place where the gap would surface if we got the order wrong.

Coder (drop duplicated gate, recon budget, stop conditions), eval (L1 in code), planner (mechanical
self-checks move into the pre-check). Full insert text in bridge §8A. E47 already decided these
stay **banked** and land in the owning increment.

**Recommendation: BANK — merge bridge §8A into `role-prompts-conformance.md`** so there is one
bank, not two. No src churn (E47 stands). Flag one conflict for the owner: bridge §8A tells the
coder "the harness runs the acceptance checks; you do not re-run them", which is correct only once
I02/I03 exist — shipping that sentence early would make the coder stop verifying with nothing
replacing it.

## Q11 — R4: attempt counting keyed by work unit, not tool signature

**Closes:** C4 — **Status:** ✅ **DECIDED → BANK for I02 + both ARCH riders**

> **Verdict (operator, 2026-10-06):** bank for I02 and attach: **E29** — `signature_hash` needs a
> written canonicalisation spec (strip timestamps / PIDs / durations / absolute paths, sort lines,
> hash) or "identical failure twice" never fires and the entire skip-ahead ladder is dead code;
> **E30** — pass-on-rerun must **quarantine** the test, not merely burn budget, and a flaky
> *planner-authored* test is a planner defect, not an environment defect.

Verified: `AttemptHistory.attempt_count(tool_name, params_hash)` keys on the tool signature, and
`LoopGuard`'s own docstring says *"Distinct params are progress, not thrash"* (the same-path thrash
detector was deliberately removed in S12.7 after it vetoed a correct edit). So "three different
failed fixes for one contract" is invisible, and there is no `stall` anywhere in the controller.

**Recommendation: BANK for I02**, with ARCH's two riders attached: E29 — the failure
`signature_hash` needs a **canonicalisation spec** (strip timestamps/PIDs/durations/absolute
paths, sort lines, hash) or "identical failure twice" never fires and the whole skip-ahead ladder
is dead code; E30 — pass-on-rerun must **quarantine** the test, not just burn budget, and a flaky
*planner-authored* test is a planner defect.

## Q12 — R5, R6, R7, R8 (batch)

**Closes:** C5, C6, C7, C8 — **Status:** 🔄 **RE-ANALYSED on operator request — recommendations revised below**

> **Operator (2026-10-06):** *"Пройдись ещё раз по своим рекомендациям, сделай критический анализ.
> Думай через призму: how would senior engineers from a real production team wisely solve this?"*
>
> The pass found four substantive corrections, one of which is a **contradiction in my own
> recommendations**. Revised table replaces the one below it.

### Q12-R — revised after critical review

| | Correction | Revised recommendation |
|---|---|---|
| **R5** | **The distiller must not be an LLM.** The standard design ("summarise the transcript") adds a new failure mode: the summariser hallucinates the error, and the coder repairs a defect that never happened. A production retry loop carries a **typed retry-context record**, not a log — the record is built *mechanically* (parse pytest/ruff output, extract the assertion diff, the failing test ID, one `file:line`). Also: **"≤15 lines" is a magic number.** Size should *fall out* of the structure; a hard cap truncates the most informative field when a message is long. And this is exactly the kind of claim that must be ablated, not shipped on faith | **BANK for I03**, reframed: attempt N starts from a **clean context + a typed `AttemptRecord`**; rendering is mechanical, no LLM in the distiller; the line cap survives only as a last-resort truncation, not as the rule; **one ablation arm** (full history vs `AttemptRecord`) on the calibration set. Riders stand: WAF-safe sanitisation (D22) and `tree_hash` + `test_version` in the record |
| **R6** | **This is a cache-invalidation problem wearing a compiler costume.** A FACT recorded at commit X may be false at HEAD; auto-injecting a stale fact into a planner prompt is *worse* than injecting nothing — it manufactures confident wrong context, which is MAST's own FM-1.2. My earlier note (branch→SHA resolution) was a detail on top of the real gap. A senior team would refuse the feature without a re-verification story | **BANK the compiler for I04, but take a schema change NOW:** ledger entries gain a **`verified_by:`** field — the command that established the FACT — so a fact can be cheaply re-checked at injection time and marked `STALE` otherwise. The ledger is append-only, so new entries can start carrying it immediately at zero migration cost; without it R6 can never ship safely. This is the highest-ROI item in R5–R8 and it is a **now** action |
| **R7** | **My auto-flip rider was over-engineering, and it contradicts a principle I endorse in Q27/E23.** "Deviation on >50% of steps, twice → auto-flip to `outcome`" needs step-level diff attribution (does not exist, hard), cross-run state, and it mutates the plan under the running coder — violating "the plan is the contract". ARCH's own T3 says *syntactic-first; semantic detection stays log-only until it proves precision/recall* — and I proposed an auto-acting semantic controller one question later. **Separately, the coupling itself conflates two axes:** TRIVIAL/STANDARD/LARGE measures *scope*; `prescriptive`/`outcome` measures *uncertainty*. A tiny change in unfamiliar code wants prescriptive; a large change in boilerplate wants outcome | **TAKE into SLICE1b as: the classifier sets the *default* `STEPS:` mode; the planner may override with a one-line reason; overrides and deviations are logged as telemetry only.** Drop the auto-flip entirely. Revisit in I06 when there is data |
| **R8** | **A principle nobody can observe breaking is not a guard.** "Keep the prefix byte-stable" is correct and will silently rot; the production move is a **golden-file snapshot test** over the cacheable prefix (~10 lines) that fails on the commit that breaks it. The hit-rate metric is *monitoring* — it tells you it broke last week. Also: with cross-family eval (I03), "the cacheable part" is **per-provider**, so the snapshot is a small matrix, not one file | **TAKE as a standing constraint *plus* the snapshot test as the actual deliverable** (SLICE5 already needs CT19 to prove it did not break the prefix — the snapshot *is* that test). Hit rate → I06 monitoring. One line noting per-provider prefixes |

### Q12-R verdict — ✅ ACCEPTED, with a substrate correction

> **Operator (2026-10-06):** *"Принимаем. Уточню, что сейчас уже есть сильная система логирования
> blackboard и event_bus, велосипед не изобретай, проверяй по факту, что уже построено."*

I inspected `src/` — see **register §S**. The correction is large and it lands on exactly the two
items the critical pass flagged:

- **R5's `AttemptRecord` must not be a new type.** `BlackboardEntry` already provides
  `content_hash` (sha256 over sorted-key JSON), `parent_id` lineage, `version_dependencies`,
  `toolchain_digest`, `run_id`. An attempt is `BlackboardEntry(type="attempt")` chained by
  `parent_id`. **E29's "write a canonicalisation spec" partly dissolves**: the canonicalisation
  exists; the open question shrinks to *what payload an attempt entry carries*.
- **R6's `verified_by:` is largely already built.** `assumptions` + `version_dependencies` +
  `_assumption_violated` inside `detect_conflict` **is** a stale-fact detector. So instead of adding
  a ledger field and a re-verification mechanism, the ledger FACT should **project into a
  `BlackboardEntry`** carrying its assumptions, and staleness falls out of the existing conflict
  check. Revised: schema §5 gains the mapping, not a bespoke field.
- **`EventBus` is *not* a durable log** — it is the console/renderer bus in `fa/output.py`. The
  durable append-only log with secret elision is `TelemetryLogger`. Any metric from U4/Q21 goes to
  `TelemetryLogger`, any user-visible progress line goes to `EventBus`. Writing that distinction
  down, because it is easy to get backwards.

**The real defect is integration, not design.** `plan_ids.py` and the planning loop touch the
blackboard **nowhere**. That is the same failure shape as `.commands` (built, zero readers) and is
precisely what **SD-B** exists to catch.

**What the critical pass did not change:** R5 and R6 stay banked (neither is unblocked before I03/I04);
R7 and R8 stay in this increment. The direction of all four was right — the *mechanisms* were two
sizes too clever in R5 and R7, and one size too trusting in R6 and R8.

### Original table (superseded by Q12-R, kept for the audit trail)

| | Item | Recommendation |
|---|---|---|
| **R5** | Distilled failure packet ≤15 lines, never the raw transcript. Verified: `coder_loop.py:600-649` rebuilds full history from the log DB on retry — exactly F3's self-conditioning shape | **BANK for I03**, + REVIEW D22: add Phoenix's sanitisation (strip tracebacks, summarise fenced blocks) or provider WAFs will 403 the packet and it will look like a model failure; + ARCH: the packet needs `tree_hash` + `test_version` or STALE-SPEC rewrites make old packets uninterpretable |
| **R6** | GIVEN compiler from ledger FACTs | **BANK for I04.** Note the wrinkle the bridge already found: anchors are heterogeneous (`@ arena/01a0762b` is a *branch*, `@ 0e08ece` a *commit*) → resolve branch→SHA, skip unresolvable. ARCH G8's bounded-read cap applies here too |
| **R7** | Tie `STEPS: prescriptive\|outcome` to the existing TRIVIAL/STANDARD/LARGE classifier (`prompt.py:93-109`) | **TAKE** — fold into SLICE4/STEP2, no new slice. Add ARCH item-3's rider: the mode is planner-declared but **harness-audited** (a `prescriptive` slice whose coder deviates on >50% of steps twice auto-flips to `outcome` on replan) |
| **R8** | Keep the cacheable prompt part byte-stable; measure hit rate | **TAKE as a standing constraint** (roadmap), not a slice. Already-built machinery; the risk is only that SLICE5 (Q9) breaks it, which SLICE5's own CT19 already tests |

## Q13 — The bridge's roadmap and ledger edits

**Closes:** C9, C10, C11, C12 — **Status:** ✅ **DECIDED → take what is high-ROI; no new rationale file**

> **Verdict (operator, 2026-10-06):** *"Берём всё стоящее и high-ROI. Если есть возможность — пиши в
> существующий файл, отметь в плане ссылку на него как rationale-context surface."*
>
> **No new `plan-edit-…-rationale.md`.** This file (`decisions-qa-2026-10-06.md`) already *is* the
> rationale surface — every decision here carries its context, its alternatives and the reason it
> won. `roadmap.md` gains one pointer line naming it as the **rationale-context surface** for the
> 2026-10-06 edits, satisfying E48 / schema §1 (no rationale in plan bodies or the ledger) without
> adding a file that could trip the two deliberately-red doc gates (E19, C12).
>
> Taken: ledger **E49–E57** (all nine re-verified line-by-line this session), extended I02/I03/I04
> one-liners, the `assumed:`→decision row for Q6, the Deferred row for **prompt-side effort routing**
> (`reasoning.effort` per slice class — a lever nothing else in the project covers), and the
> `PLANNING-TOPOLOGY-EXPLAINED.md` repoint from Q5.

Ledger E49–E57 (nine FACT/GAP/DECIDED entries) — **I re-verified all nine this session, all
correct.** Roadmap: extend the I02/I03/I04 one-liners, add the `assumed:` row for Q6, add a
Deferred row for prompt-side effort routing (`reasoning.effort` per slice class — "a different
lever from prose; must be measured in its own arm"). Plus a new `notes/plan-edit-…-rationale.md`,
because E48/schema §1 forbid rationale in plan bodies and the ledger.

**Recommendation: TAKE all four**, with: E49–E57 renumbered if the parallel branch already used
those numbers (Q0); the effort-routing Deferred row is a good catch and nothing else in the
project covers it. **And the C12 warning stands:** every new file we add to `notes/` may trip the
two deliberately-red doc gates (E19) — I will report, never "fix".

---

# Group D — the citation/production review (REVIEW)

## Q14 — Do we correct the research note itself?

**Closes:** D1, D2, D4, D5, D6, D7, E1, E2, E3, E5, F1, F2 — **Status:** ✅ **DECIDED → (a), overriding my recommendation**

> **Verdict (operator, 2026-10-06):** **(a)** — correct the research note in place.
> I recommended (b) on "supersede, never edit" grounds; the operator chose a clean note. Noted and
> accepted: `knowledge/research/` is a *working* reference the planner reads, not an archived
> artifact, so a reader finding the wrong number matters more than the provenance trail. **I will
> preserve the trail in the ledger anyway** — one entry per correction with the old value, the new
> value and the primary source — so nothing is lost, it just does not live in the note.
>
> Corrections to apply: F1's invented "up to 15 points" · the superseded architecture census (whose
> current data **reverses** the conclusion, and in our favour) · MAST pinned to v1/v2 (FM-2.2
> 11.65% → **6.80%**; FC1/FC2/FC3 41.77/36.94/21.30 → 44.2/32.3/23.5; "200+" → 1642 traces) ·
> `2206.10498` is PlanBench, not LLM-Modulo · METR's "8.1 points" is b=−0.081 at R²=0.25 on a
> 16-factor composite · AWM's 24.6% is Mind2Web, not WebArena · ReWOO is 80%, not 64% · inflated
> A-grades on out-of-domain evidence. Plus the **E15 citation swap** 2410.21819 → 2404.13076
> (the cited paper attributes the bias to perplexity, not self-generation, so it does not support
> the different-family rule). E14's SWE-Gate 34.3% is **exact — no action**.

The note has real errors: F1's "up to 15 points" **does not exist** in 2608.23953 (the thesis
does, the number is invented); the architecture census is a faithful transcription of a
**superseded** version whose current data **reverses** the conclusion; MAST's numbers are pinned to
v1/v2 (FM-2.2 = 11.65% then, **6.80%** now — F1 resolved by me against primary text);
`2206.10498` is PlanBench, not LLM-Modulo; METR's "8.1 points" is b=−0.081 at R²=0.25 on a
16-factor composite; AWM's 24.6% is Mind2Web not WebArena; ReWOO is 80% not 64%; A-grades are
inflated on out-of-domain evidence.

**None of these change a design decision.** The census correction even *supports* our topology
(our planner→coder→eval with a code-owned controller is a G3-style scripted pipeline — the group
that now leads on both median and max). But the note is cited as the source of truth by the
roadmap, and the ledger's `DECIDED` entries quote its numbers.

| Option | |
|---|---|
| **a** | Edit the research note in place with corrections |
| **b** | Leave the note; add a **corrections appendix** pointing at the two reviews; add ledger entries for the claims that back a `DECIDED` |
| **c** | Do nothing — the reviews are in `notes/`, that is enough |

**Recommendation: (b).** The note is `knowledge/research/`, i.e. evidence, and this project's own
ledger discipline is "supersede, never edit". A short appendix + ledger entries for the two
corrections that touch a `DECIDED` (E14 cites SWE-Gate 34.3% — **confirmed exact, no action**;
E15 cites self-preference 2410.21819 — **needs the swap to 2404.13076**, because 2410.21819
attributes the bias to perplexity, not self-generation, so it does not actually support the
different-family rule).

## Q15 — Adopt the version-pinning rule for research notes?

**Closes:** D8 — **Status:** ✅ **DECIDED → TAKE (roadmap standing decision + prompt rule)**

> **Verdict (operator, 2026-10-06):** take. Rule: cite `{id}v{N}, retrieved {date}`; mark each claim
> `abstract` / `body` / `table`; **quote the exact sentence** for any claim a locked decision rests
> on; put a 90-day re-check date on anything benchmark-derived. Lands as a roadmap standing decision
> **and** a line in `knowledge/prompts/research-topic.md`, because the notes are written by an agent,
> not a human. Six of the eight errors in Q14 would have been caught by the quote rule alone.

The root cause of the two most consequential errors either reviewer found (the census, MAST) is
the same: **arXiv IDs cited without versions or retrieval dates.** I confirmed the mechanism twice
over this session. Proposed rule for every future research note: cite `{id}v{N}, retrieved
{date}`; mark each claim abstract/body/table; **quote the exact sentence** for any claim that
drives a locked decision; put a 90-day re-check date on anything benchmark-derived.

**Recommendation: TAKE — as a standing decision in the roadmap and a line in
`knowledge/prompts/research-topic.md`.** Six of the eight errors would have been caught by the
quote rule alone. This is the cheapest, highest-leverage item in the whole register and it is not
in anyone's increment.

## Q16 — The reliability budget

**Closes:** D10, D24, E26, E16 — **Status:** ✅ **DECIDED → structural rule only; my SLO package withdrawn**

> **Operator (2026-10-06):** *"«E16 говорит дробить на 4–7 слайсов» — это изначально было моё
> предложение, основанное на ощущениях от работы с агентами. Я рассуждал так, что если агент пытается
> разбить инкремент на 10 слайсов, то задача переусложнённая и не стоит её пускать в продакшен в таком
> виде. Представим, что задача очень объёмная — сервис с авторизацией и оплатой. Это уже можно разбить
> на 2 roadmap внутри проекта, и, спускаясь по уровням абстракции, получится меньше слайсов в итоге."*

### The contradiction I reported does not exist — I misread the rule

I filed E16-vs-budget as a tension. It is not one, and the error was mine: I read "4–7 slices" as a
**sizing prior** ("make slices this big"), competing with the budget's "slice count dominates". It is
not a sizing prior. It is an **admission-control rule — a complexity ceiling**: *if the decomposition
needs more than ~7 slices, the increment is mis-scoped; go up one level of abstraction and
re-decompose.*

Those are opposite operations. A sizing prior makes slices smaller and **increases** N. A complexity
ceiling makes the *unit* smaller by **adding a level of hierarchy**, which **decreases** N per
autonomous run. The operator's rule was already the production answer to the exponent problem; my
"contradiction" was an artefact of reading it as its own inverse.

**And hierarchy is the mathematically correct fix**, because the exponent only applies *within one
autonomous run*. A reviewable boundary between levels resets it:

| Shape | Arithmetic | Fully autonomous |
|---|---|---|
| One flat chain of 20 slices @ s=0.90 | `0.90^20` | **12%** |
| 3 sub-roadmaps × ~5 slices, checkpoint between | `0.90^5` per run = 59%; a failure costs **one sub-roadmap**, not the feature | linear in touches, not exponential |

This is also the strongest possible argument for D16 (partial value) and for checkpointing — they are
the same mechanism seen from two sides.

### Revised recommendation — smaller than what I proposed

My earlier package (TBD SLO + `human_touches_per_feature` SLI + over-slicing detector + ledger entry)
is **withdrawn as premature**. Reasons, honestly stated:

- A TBD SLO with no baseline and no runs is **inert**. The repo parks KPIs as TBD in Pillar 3 *because
  a baseline run is scheduled*; here nothing is scheduled, so the row would be decoration.
- ARCH's over-slicing detector keys on **median verify time < 60s** — runtime telemetry that does not
  exist for the planning loop. Inert for the same reason, and strictly worse than the rule below,
  which needs nothing.

### Final verdict — smaller again (operator, 2026-10-06)

> *"План я планировал писать вместе с агентом, не думаю, что нужна автоматизированная система для
> этого. Агент будет спрашивать, я — направлять."* and *"Можно обойтись инструкцией в прозе. Лимит
> n ≤ 7, иначе бьём на инкременты помельче."*

**Both of my remaining items are withdrawn.** No sub-roadmap grammar level (the hierarchy is handled
by operator judgement in conversation, not by a schema), and no pre-check contract (prose, not a
check). What lands is **one authoring instruction in SLICE1b**:

> `N ≤ 7 slices per increment. If the decomposition needs more, the increment is mis-scoped — split
> it into smaller increments.`

**Recorded honestly, because an unenforced rule drifts:** this rule is *deliberately* unchecked. Its
enforcement mechanism is the operator, who is in the loop on every plan. That is a legitimate
production answer for a human-in-the-loop tool — and it has an **expiry condition** worth writing
next to it (the E24 pattern, Q23): *if plans ever start being authored without the operator reviewing
them, the ceiling must become a pre-check FAIL.* Until then, prose.

**What survives from the whole of Q16:** one sentence in SLICE1b, plus one ledger entry recording the
exponent arithmetic as the *reason* for the ceiling — so a future reader knows it is a reliability
mechanism, not taste, and knows what the hierarchy is for. Everything else (SLO, SLI, detector,
grammar recursion, pre-check) is dropped, not deferred.

### Superseded intermediate proposal (kept for the audit trail)

**Take exactly one thing, and make it executable:**

1. **Hard structural admission rule, authoring-time, deterministic.** A slice count above the ceiling
   is a **FAIL with a named remedy**, not a warning: *"N slices exceeds the complexity ceiling —
   promote this increment to a sub-roadmap and re-decompose."* Lands as a pre-check contract in
   SLICE3. Needs no baseline, no telemetry, no LLM judgement.
2. **Make the recursion legal in the grammar.** The rule above is unenforceable unless "promote to a
   sub-roadmap" is a thing the schema permits. Today `roadmap.md` is a single flat index; the
   hierarchy the operator describes (project → roadmap → sub-roadmap → increment → slice → step) is
   **not representable**. This is the actual gap, and it is a documentation/grammar change — the kind
   I can build in this session. Lands in schema §1 and `roadmap.md`.
3. **Record the arithmetic once, in the ledger**, as the justification for rules 1–2 — so a future
   reader knows the ceiling is a reliability mechanism, not taste.

**Why this is the right size:** it converts the operator's intuition into a deterministic check plus
the structure that check presupposes, and defers every number to when runs exist. SLO work returns in
I06 with data, as the roadmap's `reasoning.effort` Deferred row does.

`s = 1 − (1−p)(1−q)²`. A 20-slice feature at s=0.900 completes autonomously **12%** of the time;
90% feature completion at 20 slices needs **s = 0.995 per slice**. METR's own Jan-2026 follow-up:
*"reliability-critical tasks require 98%+ success probabilities to be worth automating."*

The sharp part: **slice *count* dominates**, which pulls directly **against** F7's sizing cliff
(smaller slices succeed more often individually but there are more of them). The note never
notices this. REVIEW would revisit locked decision #1 (four tiers) at the end of phase 2 on this
basis. ARCH adds the cheap sensor: an **over-slicing detector** (slice count > 7 **and** median
verify time < 60s → "probably over-sliced: merge candidates").

| Option | |
|---|---|
| **a** | Declare a target now (e.g. 50% fully autonomous, 95% with ≤2 human touches) and make I06 telemetry report against it |
| **b** | Record the arithmetic and the tension as a ledger `GUESS`/`GAP`; add the over-slicing detector to SLICE3's warnings (CT10b already warns on slice count outside 4–7); set the target when I03 produces data |
| **c** | Both: (b) now, (a) as a roadmap placeholder with `TBD` numbers |

**Recommendation: (c).** This repo already has the pattern — `project-overview.md` §Pillar 3
parks KPI numbers as `TBD` until a baseline run, explicitly so they do not block v0.1. Do the
same here. But **record the E16 contradiction loudly**: E16 says "4–7 slices is the sizing prior";
the budget says slice count dominates. Those two cannot both be tuned independently.

## Q17 — Verification integrity as a security boundary

**Closes:** D11, E10 (G5), E11 (G6, partly) — **Status:** ✅ **DECIDED → BANK; IntentGuard untouched this cycle**

> **Operator (2026-10-06):** *"Звучит здраво, но я не смогу одновременно чинить систему chat-invoke
> workflow (это то, что мы разрабатываем сейчас) и intent_guard (такая система уже есть) — расширим её
> по необходимости позже."*
>
> **BANK the audit and all five controls.** No IntentGuard / ADR-12 / ADR-13 work this cycle; the
> chat-invoke workflow is the single focus. Recorded in the I02 hand-off note with the §S corollary
> attached: `write_set` on `BlackboardEntry` already exists, so when this is picked up, four of the
> five controls are **assertions over an existing mechanism**, not new machinery — which is why
> deferring is cheap rather than accruing debt.
>
> **One carve-out I am keeping, and flagging for your veto:** the `TESTS:`-paths-not-in-the-coder's-diff
> assertion is a **pre-check lint inside the planning loop we are building**, not an IntentGuard
> change — it parses a line SLICE3 already parses and compares it to a diff path list. It stays in
> SLICE3 unless you say otherwise. Everything that touches the sandbox, the egress proxy or the
> command classifier is out.

**The strongest convergence between the two reviews**, and both call it non-negotiable. Nothing
stops the coder editing the planner's test file. Evidence: a UC Berkeley agent scored 100% on
three benchmarks without solving a task; SWE-bench Pro Verified's anti-hacking controls cost
GLM-5.2 171 of 731 passes; Cursor found 63% of successful trajectories *retrieved* rather than
derived the fix; RewardHackingAgents shows tampering and leakage are **independent** failure modes
where partial defences fail.

Controls: read-only `TESTS:` paths · verify runs where the coder cannot write · hash the
verification surface at baseline and re-check at the gate · deny-list `conftest.py`/test config/CI
workflows from coder writes · a derivation-vs-retrieval telemetry category.

**Important for us:** this repo may already be most of the way there — ADR-12 secret isolation,
ADR-13 workspace isolation, the `bashlex`/IntentGuard `REPO_WRITE` classifier, `check_protected_paths.py`.
**I have not audited that claim.**

| Option | |
|---|---|
| **a** | Audit the existing controls against the five, then add only the gaps as I02 contracts |
| **b** | Add all five as I02 contracts regardless |
| **c** | Bank for I02 review without an audit |

**Recommendation: (a).** The audit is maybe an hour and it is exactly the "does this component
earn its place" discipline the project mandates. The one control I am confident is **missing** is
the cheapest: **`TESTS:` paths must not appear in the coder's diff** — the pre-check already parses
that line, so it is a diff-path assertion, and it belongs in SLICE3 now, not I02.

## Q18 — Mutation testing: F4 resolved by posture

**Closes:** D14, F4, U8–U11, E11 (partly) — **Status:** ✅ **DECIDED → scoped mutation gate + appeal, no exceptions**

> **Verdict (operator, 2026-10-06):** *"Гейт + апелляция через GUESS→decided."* and, on my proposed
> skip for structural slices: *"Не уверен, как мы их определим? По плану все тесты будут запускаться
> харнесом, чувствую лишнюю сложность. Может, проще не пропускать?"*
>
> **Agreed — the skip rule is dropped, and the reason is stronger than "simpler".** Defining
> "structural slice" needs contract classification plus a branch in the gate, i.e. new complexity to
> *avoid* running a check. And mutation on a refactor slice is not noise — it is **meaningful**: a
> refactor claims behaviour is preserved, so surviving mutants on the changed lines say the tests
> stopped constraining the refactored code. That is exactly what you want to know. No exception.
>
> **Final shape — two mechanisms, one of which already exists:**
> 1. **One scoped mutation run per slice, as a gate.** Changed lines only; tooling exists
>    (`scripts/run_slice_mutmut.py`, `count_mutants.py`, `mutation_sweep.py`); scoping bounds the
>    finding count, so no top-K ranker is needed.
> 2. **Appeal:** the planner may dismiss a survivor with a one-line reason appended to the ledger via
>    the existing `GUESS→decided:` flow. This is what stops an equivalent mutant wedging the loop —
>    the project rule is "never wedges", and production teams reject *unappealable* gates, not gates
>    with false positives.
>
> **Dropped from my proposal as over-built:** findings-format spec, routing mechanism, top-K cap,
> pre-registered graduation rule, shadow phase, upfront arid list. The arid list, if it is ever
> needed, **derives from operation**: three dismissals of one operator class nominate it. Six
> mechanisms became two.

REVIEW: add mutation-based non-vacuity to item 1 — fail-before/pass-after proves the test is
sensitive to *the change*, not to *the behaviour* (>99% of tests that failed on mutated code
passed on the original; MutGen 53%→89.5%). ARCH: full per-slice mutation is "overkill"; use
rationale lines + held-out tests + periodic hack-checks.

**They were arguing about gating.** The parallel review dissolves it with Google's
mutation-at-scale posture: changed lines only, survivors surfaced as **review findings** routed to
the test's author (here: the **planner**, since the planner wrote the test), top-K cap, measured
arid list, and a **pre-registered graduation rule** (shadow → gate only on measured precision).
Nobody gates on mutation score. **And this repo already owns the tooling**
(`scripts/run_slice_mutmut.py`, `count_mutants.py`, `mutation_sweep.py`) plus a kill-check
protocol in `feature-planning` §12 — so ARCH's cost objection is weaker here than in general.

**Recommendation: TAKE the findings-posture, BANK the mechanism for I02** (shadow mode + ablation,
graduation rule written *before* the ablation runs). Add REVIEW's cheap companion now: the
pre-check should require **≥1 boundary/edge test per `FUNCTIONAL` contract** — every evaluated LLM
systematically omits `None`/`inf`/`NaN` tests, and that is a one-line lint.

## Q19 — Review capacity, the PR brief, and partial value

**Closes:** D13, D15, D16, D17, E17 (G12), E35 — **Status:** ✅ **DECIDED → bank all four in I05; two lines land now**

> **Verdict (operator, 2026-10-06):** PR-brief artifact, decision-surface-per-slice and partial-value
> go to the I05 bank. Two things land in the roadmap now: the **≤3-slice fast path as a first-class
> path** (it changes how every future roadmap is carved, and "the tiers collapse gracefully" is
> contradicted by the evidence — ceremony is fixed-cost), and **recoverability as the fourth reason
> the planner writes steps** (one sentence — and after Q16 it is the strongest of the four, since
> checkpointing is what breaks the exponent).

REVIEW's §5.4 is the production argument the note has no answer for: AI moved the bottleneck
*downstream* to human review (AI PRs average ~1.7× more issues; volume 3–5× against a fixed review
rate). Four related gaps:

- **PR-brief artifact** — the note's PR step is one line ("HARNESS composes the PR from the
  tracker"); in production this is the single biggest lever on human gate latency.
- **≤3-slice fast path** — "the tiers collapse gracefully" is contradicted by field evidence;
  ceremony is **fixed-cost**. Make the flat plan a first-class path, not a degenerate case.
- **Decision surface per slice** — the set of choices a slice may *not* make unilaterally. This is
  the answer to the strongest objection to scoped context (SLICE2 picks an error envelope, SLICE3
  picks another, both pass their own contracts).
- **Partial value** — "increment 3 of 4 failed permanently" currently produces an unticked box.

**Recommendation: BANK all four for I05** (chat orchestration / ceremony / scope — which already
absorbs the monster plan's S6a "PR-body source" and S7 "scope signal"), **except the fast path**,
which I would record as a roadmap standing decision now because it changes how every future
roadmap is carved. Add D17 (recoverability as the 4th reason the planner writes steps) to the
roadmap's standing decisions — it is one sentence and it is the strongest of the four reasons.

## Q20 — The remaining REVIEW items (batch)

**Closes:** D3, D9, D12, D18, D19, D20, D21, D22, D23, F3 — **Status:** ✅ **DECIDED → revised allocation (two TAKEs, rest banked)**

> **Verdict (operator, 2026-10-06):** take the revised allocation. **Two corrections I made to my own
> earlier recommendations before asking**, both from the same mistake — proposing a *pre-check*
> (authoring-time, static) for something that can only be known at *runtime*:
>
> - **D18** (measure flake variance at baseline by running verify k times) — I had this as "TAKE, one
>   pre-check warning". A pre-check cannot run anything. **Corrected to BANK for I02**, where the
>   baseline run actually happens.
> - **D20's parallel-slice file-set disjointness** — I had it as BANK "no parallelism until I06+".
>   Per **§S** it is *already implemented*: `read_set`/`write_set` overlap detection in
>   `Blackboard.detect_conflict`. **Corrected to BANK with a pointer**, so whoever picks up deferred
>   item #11 does not rebuild it.
>
> **Landing now (2):** **D23** — the phase-1 exit criterion *"the gate rejects ≥95% of patches that
> pass functional tests but violate a stated constraint"*, into the I02 hand-off note, because we have
> no other concrete definition of "the gate works". **D21** — the slice-brief volume cap, as **prose
> in SLICE1b** following the Q16 pattern rather than as a check.
>
> **Banked:** D3 (MAST 6.80% as a ledger FACT with the version table) · D12/F3 (N-version → roadmap
> Deferred row: *diagnosis* only, selection on CONSTRAINT satisfaction, k ≤ 3 — REVIEW's
> imperfect-verifier argument beats ARCH's second-noisy-signal guard) · D19 calibration → I03 ·
> D20's `TESTS:`-not-in-diff stays in SLICE3 per Q17 · D22 → I03, with the WAF-sanitisation rule
> riding on R5 and a note that this repo already has the threat model (ADR-11/ADR-12) the research
> note does not know about. **D9 is already absorbed** by Q14's in-place correction.

| | Item | Recommendation |
|---|---|---|
| **D3** | MAST FM-2.2 is 6.80%, not 11.7% → `ASK#` justification 1.7× weaker | **BANK** as a ledger FACT with the version table. Build #13 anyway (it is cheap); do not size effort around 11.7% |
| **D9** | §8 goalposts are stale (Verified ~96% saturated) | **TAKE** — demote §8 to "context" in the corrections appendix; judge on pass^k over our own held-out set |
| **D12 / F3** | N-version: REVIEW says drop verify-based *selection* (imperfect-verifier ceiling, 2411.17501); ARCH says keep it with an eval-L2/L3 Goodhart guard | **Settle on paper now, both are deferred (#10).** REVIEW has the stronger argument — a *theoretical* result that resampling cannot reduce false-positive rate, plus optimal K often ≤5 and K=0 when a false positive costs 10×. ARCH's guard still selects on a noisy signal, just a second one. **Recommend: N-version *diagnosis*, selection only on CONSTRAINT satisfaction, k≤3** → roadmap Deferred row |
| **D18** | Flake classification must be **measured** at baseline (run verify k times, record variance), not defined | **TAKE** — one pre-check warning in SLICE3; it converts item 12's definitional claim into a measurement |
| **D19** | Judge calibration; family switching changes the *direction* of judge error, not its size; swap 2410.21819 → 2404.13076 | **BANK for I03** (three-level eval) + the citation swap in Q14 |
| **D20** | Pre-check additions: `TESTS:` not coder-writable · parallel-slice file-set disjointness · baseline flake measurement | **TAKE the first and third into SLICE3** (see Q17, D18); **BANK the second** (no parallelism until I06+) |
| **D21** | Cap slice-brief volume (~1.5–2K tokens) — *the budget becomes a sizing mechanism, not a style rule* | **TAKE as a pre-check WARN** in SLICE3. Cheap, and it is the only sizing signal we have that does not depend on telemetry |
| **D22** | Phoenix hazards: WAF filtering on tracebacks · token expiry mid-run · CI permission boundaries · per-installation lock. Plus: **no prompt-injection threat model** | **BANK**, but route the WAF rule into R5's failure packet now (Q12), and raise the threat model as its own question — this repo has a threat model (ADR-11 "LLM as Untrusted Compiler", ADR-12) that the research note does not know about |
| **D23** | Three-phase build plan with exit criteria + **mandatory ablations**; phase-1 exit = the gate rejects ≥95% of patches that pass functional tests but violate a stated constraint | **TAKE the phase-1 exit criterion into I02's hand-off note** — it is a concrete, measurable definition of "the gate works", and we have nothing equivalent. The 20-slice corpus doubles as the item-12 held-out set (parallel agent's U11) |

---

# Group E — the architecture review (ARCH)

## Q21 — G1: is markdown-regex an acceptable substrate? ⚠️ the one that challenges I01's premise

**Closes:** E6, F6, U4–U6, E36 — **Status:** ✅ **DECIDED → (b′) with the Blackboard as the named destination; no metrics yet**

> **Verdict (operator, 2026-10-06):** keep markdown as a staged decision, and **name the strangler's
> destination concretely**: per **§S** the structured record store G1 asks for **already exists** —
> `Blackboard`, with content hashes, lineage, assumptions and conflict detection, persisted through
> `SessionDatabase` and completely untouched by the planning loop. So the end-state is not "build a
> schema-first substrate"; it is **project slice records into the store we already have**. Shoot #1
> is that projection, not the I04 ledger parser.
>
> **Taken now:** the **golden drift corpus** + **near-miss lint** (`^#{2,4}\s+SLI?CE?\s*\d` →
> *"did you mean `## SLICE2:`? (line 41)"*) in SLICE3 — and they double as the fixture asset for Q2's
> CT16 and Q3's CT17/CT18, so one test asset serves three decisions.
>
> **Not taken:** the error-budget counters and the `plan_precheck_first_pass_rate` SLI. Same reason
> as Q16 — no runs, no baseline, so the numbers would be decoration. They return in I06.
>
> **Still true and recorded:** the live silent mis-parse (E52 — a fresh plan parses to empty
> `.slices` and `workflow_controller.py:332` returns early) is fixed by the Q7 reorder (SLICE1b makes
> the planner emit the grammar), not by a metric. **F6 dissolves:** the strangler keeps I01 moving
> (REVIEW's order) while G1's end-state stays a named destination rather than a flag day (ARCH's
> goal). E36's Phase-0-first build order is therefore declined.

ARCH's highest-risk item and its self-declared "highest-leverage engineering change": the source
of truth should be validated structured records, with markdown as a **rendered projection**; the
acceptance criterion is **zero silent mis-parses**. Its build order puts this in **Phase 0, before
anything LLM-facing** — i.e. before everything we have planned.

**My A3 and A4 are live instances of exactly the failure class G1 predicts**, which strengthens its
case considerably. So does E52: a fresh plan parses to empty `.slices` and the gate no-ops in
silence.

Against it: filesystem-canon markdown is a *founding* principle of this project (ADR-3/ADR-4,
"human-readable, git-able, diff-reviewable"), I01 is half-built on it, and no production failure
has occurred.

The parallel agent reframes the question correctly — **not "whether" but "when, measured how"**:

| Option | |
|---|---|
| **a** | Accept G1; Phase 0 substrate work before I01 continues |
| **b** | Reject; close the failure class point-by-point |
| **b′** | **Keep markdown as a *staged* decision with an explicit kill condition.** Name the patterns (gradual typing; strangler fig; SRE error budget). Define the budget precisely: `plan_extract_silent_misparse_total == 0` **always** (burn ⇒ freeze features, substrate sprint) and `plan_precheck_first_pass_rate` as an SLI with a floor. Make it measurable with a **golden drift corpus** + differential property test + a **near-miss lint** (`^#{2,4}\s+SLI?CE?\s*\d` → *"did you mean `## SLICE2:`? (line 41)"*). Declare the strangler trajectory: the I04 ledger parser is shoot #1; markdown becomes render-only when the trigger fires |

**Recommendation: (b′), and it is the best single idea in any of the four documents.** It converts
an unfalsifiable architectural argument into a metric with a consequence. Two things I would add:

1. **The E23 early-return must become a loud event when the input is slice-shaped.** That is the
   live silent mis-parse (E52) and it is today's budget burn — so the budget starts at **non-zero**
   and (b′) obliges us to fix it in SLICE1b/SLICE3, not later. Make that explicit or the metric is
   theatre on day one.
2. **The golden drift corpus is also the answer to Q2/Q3.** The A3 and A4 behaviours become corpus
   fixtures, which means the parser fix and the budget share one test asset.

## Q22 — G2: do positional slice IDs rot our cross-references?

**Closes:** E7, U7, P9, P10 — **Status:** ✅ **DECIDED → conditions only; tombstones declined for now**

> **Verdict (operator, 2026-10-06):** write E24's three conditions next to the decision; **no
> tombstone convention** — it solves a problem we have not had once. The letter-suffix mechanism
> (`SLICE1b`) already covers insertion without renumbering, which is the case we actually hit this
> session. P10's scale envelope (natural keys good to ~100s of slices) is recorded as a note.

`SLICE2`/`STEP3` are positions, but `DEPS:`, ledger refs and `ASK#` all link by name; any insert,
delete or STALE-SPEC rewrite silently re-points them. ARCH wants stable keys frozen at creation.
Partially mitigated already: the grammar allows letter suffixes, which is exactly what bridge R1
uses to insert `SLICE1b` without renumbering.

**Recommendation: the parallel agent's U7 — tombstone sections.** A retired slice leaves
`## SLICE3: [retired] — superseded by SLICE3a, <reason>` (parseable, unrunnable), so a `DEPS:`
reference to it fails loudly via CT10 instead of silently re-pointing. Zero schema change; it is
the ledger's own `supersedes:` philosophy applied to slices. Full surrogate keys are the right
end-state beyond ~100s of slices — record the scale envelope, do not build it now.

## Q23 — P5b vs E24: compat shim for the `S#` rename?

**Closes:** E24, P11 — **Status:** ✅ **DECIDED → keep E24, record the three conditions**

> Conditions under which zero-deprecation removal was acceptable: (1) no live consumers of the old
> form; (2) corpus small, archived, mechanically migratable; (3) a migration note ships for humans.
> All three hold today. If any fails later → P5b-style warn-and-remove. Written next to the decision
> so a future reader knows when it expires.

ARCH's P5b wants parse-old-warn-don't-fail for one quarter. Our ledger E24 decided SLICE#-only,
no dual grammar — and it is **shipped and pinned by a test**
(`extract_plan_ids("### Step S1: legacy").slices == ()`).

**Recommendation: keep E24, and write down the three conditions under which it was acceptable**
(the parallel agent's §2.6): (1) no live consumers of the old form; (2) the corpus is small,
archived, mechanically migratable; (3) a migration note ships for humans (SLICE4/STEP3 covers it).
All three hold today. If any fails later → P5b-style warn-and-remove. Writing the conditions next
to the decision is what lets a future reader know when it expires.

## Q24 — G6: planner authors both the spec and its acceptance

**Closes:** E11, E22 (T2), E4 — **Status:** ✅ **DECIDED → readback, not independent authorship**

> **Analysis (operator asked for a production-grade options review).** The question conflates two
> failure modes:
> - **(A) weak acceptance** — the test does not enforce the stated contract. **Already closed by
>   Q18's mutation gate.** Anything further is a second mechanism against one threat.
> - **(B) wrong spec** — the contract itself misreads the requirement. **Irreducibly human**: the
>   requirement exists only in the operator's head and the task text, so any check derived from the
>   plan inherits the plan's error.
>
> **Held-out tests are rejected as specified**, and the reason is not cost: the eval reads *the same
> plan*, so it inherits the misunderstanding. To be independent it would have to author from the
> original task text only — at which point it is a second planner, with a disagreement-resolution
> problem. It does not address (B) and it duplicates (A).
>
> **Verdict — the control against (B) is the operator's review, written down as such, plus two
> near-free readback mechanisms** (precedent: aviation/medicine readback-hearback; DO-178C graduates
> independence by criticality rather than demanding separate authorship everywhere):
> 1. **`## Grounding` gains a mandatory line**: *what I understood you to want, and what I
>    deliberately excluded.* Five lines the operator can check instead of two hundred.
> 2. **One rationale line per `CONSTRAINT` contract**: what wrong implementation it catches. A
>    readback at the test level; also what makes an L3 review possible.
> 3. **`TEST-DEFECT` as a first-class verdict** (I02) — **not** an independence fix but a *liveness*
>    one: today "the test is wrong" is not an expressible outcome, so a wrong test burns the entire
>    repair ladder and wedges the loop. Needed regardless.
>
> Risk-graded independence (the DO-178C shape) was considered and deferred: it presupposes a `RISK`
> vocabulary, and **verified 2026-10-06: the schema has none** (see E14).

ARCH's self-declared most important methodological correction: principle 8 says separate authorship
from acceptance **at every level**; item 1 makes the planner author both. The coder is separated;
the planner is not. Three fixes: **eval-held-out tests** (small coder-blind suite per slice,
authored on the eval's family, run only at the gate); a **`TEST-DEFECT` route** ("the test is
wrong" must be a first-class verdict with its own budget, since hacking concentrates on tasks with
defective test infra); **CONSTRAINT rationale lines** (one line per test: what wrong implementation
it catches).

**Recommendation: TAKE the `TEST-DEFECT` route and the rationale lines into the I02 hand-off note;
BANK held-out tests behind a measurement.** The route is nearly free and its absence is a real
wedge (a wrong test burns the whole repair ladder — we have no "the test is wrong" verdict today).
Rationale lines are one line of authoring guidance that makes L3 review possible. Held-out tests
double the planner's test-authoring cost and overlap with Q18's mutation findings — pick **one**
of the two after the I02 ablation, not both on faith.

## Q25 — G5 / G13 / G14: sandbox, cost model, redaction

**Closes:** E10, E18, E19 — **Status:** ✅ **DECIDED → all banked (follows Q17)**

> G5 (unaudited verify commands) folds into Q17's bank — IntentGuard is out of scope this cycle.
> G13 (no cost/latency model) → I06, but the **graceful degradation order** is recorded now as a
> roadmap standing decision: N-version → retry, k=2 → k=1+samples, frontier → cheap,
> **ledger-logged, never silent**. G14 (secrets/PII) → banked; noted that this repo is already strong
> here (ADR-12 egress proxy, gitleaks) and that per **§S** `TelemetryLogger` already does secret-key
> detection and value elision — the genuinely new surface is the cross-family eval in I03, flagged in
> the I03 outline.

| | Gap | Recommendation |
|---|---|---|
| **G5** | Planner-authored verify commands are unaudited RCE | Folded into **Q17**'s audit. Add the pre-check **command policy** (allowlisted runners, repo-contained paths, deny network/privilege/outside-worktree writes) to SLICE3 — that part is pure lint and does not depend on the audit |
| **G13** | No cost/latency model; the design is eval-heavy *by principle* | **BANK for I06** (telemetry), + record the **graceful degradation order** now as a roadmap standing decision: N-version → retry, k=2 → k=1+samples, frontier → cheap, **ledger-logged, never silent** |
| **G14** | Secrets/PII through prompts and records; cross-family eval = egress to a *second* processor | **BANK**, but note this repo is strong here already (ADR-12 egress proxy, gitleaks, `.gitleaks.toml`). The genuinely **new** surface is the cross-family eval in I03 — flag it in the I03 outline now so it is not discovered late |

## Q26 — G3 / G4: freshness and durable resume

**Closes:** E8, E9 — **Status:** ✅ **DECIDED → G3's stamp rides on Q6; G4 banked**

> **G3 (freshness).** Per **§S** the field already exists: `BlackboardEntry.version_dependencies:
> dict[str,str]` is literally the `tree_hash` + `HEAD` stamp ARCH asks for. So G3 becomes part of
> Q6's admission default/stamp step, not a new mechanism. **G4 (durable resume)** → banked for I03,
> with the §S note that the blackboard is already SQLite-backed through `SessionDatabase`, so the gap
> is likely smaller than ARCH assumed and needs an audit before any design.

G3: planner-once assumes the tree at slice time equals the tree at plan time; without a
`tree_hash + HEAD + touched-paths` check, the first concurrent human commit creates heisen-slices.
G4: controller progress (which slice, which ladder rung, streaks) is not durable; `kill -9` should
resume exactly once.

**Recommendation: BANK both for I03**, but **G3's stamp lands now** as part of Q6's admission step
(the parallel agent's U2 already stamps `source_plan_sha` + `admission_version`; adding
`tree_hash` + `HEAD` is the same five lines and it is what makes the later check possible). G4
needs an audit first: `session.db` is already the per-run authority, so the gap may be smaller
than ARCH assumes.

## Q27 — The remaining ARCH riders (batch)

**Closes:** E12–E16, E20, E21, E23, E25, E27, E28, E31–E34, E36 — **Status:** ✅ **DECIDED → six taken, ten banked**

> **Taken (6):** **E21** reflection must be ledger-typed, raw prose never replayed into prompts
> (schema §5; per §S "typed" means a `BlackboardEntry`) · **E23** syntactic-first, semantic detection
> log-only until it proves precision/recall (roadmap standing decision — *this rule already paid for
> itself this session: it is what killed my own R7 auto-flip*) · **E27** baselines must be hermetic
> and **affected-path scoped**, not a full suite per slice (I02 hand-off — a real defect in a design
> we already banked: `verify-block-design.md` currently implies O(slices × suite-time)) · **E28a**
> pre-check returns **all** violations at once (SLICE3; free at build time, expensive to retrofit) ·
> **E31** pass^k **resettability** — *verified: schema §6:149 defines `VERIFIED` as pass^k and never
> says what resets k, so passes could accumulate across different code states* · **E34** the REPLAN
> predicate written as a deterministic rule (I03 outline, one sentence — it is E23's first
> application and it preempts an LLM judge).
>
> **Two corrections to my own earlier recommendations:** **E25** (`(auto)` authoring guidance) —
> downgraded to BANK, because the field's executor is the I03 harness and **SD-B** forbids shipping
> guidance for a field with no consumer. **E28b** (versioned check list) — downgraded to BANK; it is
> a compat/migration mechanism and we just reaffirmed E24's no-shim stance.
>
> **Banked (10):** E12 (G7 — **already implemented** per §S as `read_set`/`write_set` overlap
> detection; pointer recorded so deferred item #11 does not rebuild it) · E13 (ledger GC — premature
> at 48 entries / 168 lines) · **E14** (risk floor — **not a rider but a new concept: verified
> 2026-10-06 that the schema has no `RISK` vocabulary at all**; dependency recorded) · E15 (eval
> calibration → I03, merged with D19) · E16 (skill-registry rot → flagged against Pillar 4, where it
> is load-bearing) · E20 (buy-vs-build → one honest roadmap paragraph) · E25 · E28b · E32 (L2 cites
> test IDs, not hunks → `role-prompts-conformance.md`) · E33 (cap blocking `ASK#` → I05). **E36**
> (Phase-0-first build order) is **declined** — resolved by Q21's strangler.

| | Item | Recommendation |
|---|---|---|
| **E13 (G8)** | Ledger bounded reads + GC (FACT→ADR promotion, FAILED expiry, GUESS must resolve) + enforced write perms | **TAKE the GC policy into schema §5 now** (it is grammar, and our ledger is already at E48/168 lines); BANK the retrieval cap for I04 |
| **E21 (T1)** | Reflection output must be **ledger-typed**; raw prose never replayed into prompts | **TAKE into schema §5** — one sentence, and it is the resolution of a real tension (Reflexion vs self-conditioning) |
| **E23 (T3)** | "No LLM deciding" vs semantic triggers → **syntactic-first**; semantic detection stays log-only until it proves precision/recall | **TAKE as a roadmap standing decision.** It protects the project's own "controller is code" rule from erosion in I03/I05 |
| **E27** | Baselines must be hermetic and **affected-path scoped**, not a full suite per slice | **TAKE into the I02 hand-off note** — `verify-block-design.md` currently says "run the slice's commands once on the untouched tree", which is O(slices × suite-time). This is a real defect in a design we have already banked |
| **E28** | Pre-check returns **all** violations at once; the check list is **versioned** | **TAKE into SLICE3** — both are free at build time and expensive to retrofit |
| **E25** | `(auto)` steps default to harness-executed when the exit criterion is a pure function of repo state | **TAKE into SLICE4's authoring guidance** (schema §4 already defines `(auto)`; nothing says when to use it) |
| **E34** | Make "major drift is a REPLAN" a **predicate**: trivial = diff touches only paths listed in the slice section AND all CT# stay PASS AND no new file outside the set | **TAKE into the I03 outline** — it converts a vibe into something the harness can detect with no LLM judgement |
| **E31** | pass^k **resettability** requirement; streak resets on any gate-input change | **BANK for I03**; add to schema §6, which already defines `VERIFIED` as pass^k for stochastic gates without saying what makes k meaningful |
| **E32** | L2 verdicts cite **test IDs**, not hunks (hunks rot on rebase) | **BANK for I03** → `role-prompts-conformance.md` |
| **E33** | Cap blocking `ASK#` per increment (≤5); auto-promote only GUESSes a contract depends on | **BANK for I05** |
| **E12 (G7)** | Parallel safety verified syntactically, not planner-asserted | **BANK** — already deferred (#11) |
| **E14 (G9)** | Rule-based RISK floor (auth/crypto/perms/billing/migrations → ≥elevated regardless of tag) | **BANK for I05**; it is also a natural "default" step in Q6's admission |
| **E15 (G10)** | Eval calibration set (≥100 labelled verdicts) before trusting k=2 | **BANK for I03**, merged with D19 |
| **E16 (G11)** | Skill-registry rot (versioning, usage counting, GC, retrieval precision) | **BANK** — but flag it against **Pillar 4** (agent writes its own skills), where it is directly load-bearing |
| **E20 (G15)** | Buy-vs-build: adopt ecosystem seams, build only the deep half | **BANK as a roadmap note.** Worth one honest paragraph: Spec Kit at 111k stars ships the shallow version of this design |
| **E36** | ARCH's revised build order (Phase 0 substrate first) | **Resolved by Q21's (b′)** — the strangler trajectory replaces the Phase-0 flag day |

## Q28 — Scope discipline: what do we refuse?

**Closes:** register §H — **Status:** ✅ **DECIDED → standing decision with teeth**

> **Verdict (operator, 2026-10-06):** *no component proposed by either review ships without (a) a
> named failure mode it prevents, and (b) an on/off ablation planned in the increment that adds it.*
> Goes into `roadmap.md` as a standing decision. The research note quotes itself against itself —
> MAST found **3 of 14 failure modes are created by multi-agent structure** — and both reviewers make
> "ablate before permanence" their governing rule.

The two reviews add ~55 findings to a project whose governing principle is minimalism-first
(`project-overview.md` §1.2 — a five-question test before any component) and whose own adoption
plan quotes the research note against itself: *"More structure is not more success"* — MAST found
**3 of 14 failure modes are created by multi-agent structure**, and the meta-recommendation is to
**ablate each component before granting it permanence**. Both reviewers repeat this: REVIEW makes
"ablate before permanence" the governing rule of its build plan; ARCH says "measure the
compounding claim or drop it."

**Recommendation: make it a standing decision with teeth.** Something like: *no component added by
either review ships without (a) a named failure mode it prevents, and (b) an on/off ablation
planned in the increment that adds it.* Then the honest output of this session is a **small** set
of plan edits — I count roughly **6 TAKEs into I01**, 4 schema/roadmap lines, and ~30 banked ledger
entries — rather than 55 new slices.

---

# Group F — remaining conflicts

## Q29 — F2 and F6, the two open conflicts

**Closes:** F2, F6 — **Status:** ✅ **BOTH CLOSED**

> **F2** (SWE-bench Pro 23% vs 43.6%) — both reviewers right about different versions, the same
> mechanism as F1; drives no decision, and §8 is corrected in place by Q14. Recorded, closed.
> **F6** (different first moves) — dissolved by Q21: the strangler keeps I01 moving (REVIEW's order)
> while G1's end-state becomes a named, already-existing destination (the `Blackboard`) rather than a
> flag day (ARCH's goal, achieved differently).

- **F2 (SWE-bench Pro, 23% vs 43.6%)** — both reviewers right about different versions, same
  mechanism as F1. Drives no decision (§8 is being demoted anyway, D9). **Recommend: record and
  close.**
- **F6 (different first moves)** — REVIEW says "this is a pipeline design, not a system design,
  build the gate right"; ARCH says "the substrate is wrong, rebuild the artifact layer first".
  **Recommend: Q21's (b′) dissolves it** — the strangler keeps I01 moving (REVIEW's order) while
  the error budget holds ARCH's end-state as a dated, measured commitment rather than a flag day.

## Q30 — What does this session actually emit?

**Status:** OPEN

`first-agent-bridge.md` §7 asks for: a unified diff over `worklogs/…` plus a short note to the
operator (what changed, what is banked, what needs a decision).

**Recommendation:** after the walk — (1) `increment-01` edits (SLICE1b, SLICE5, Q2/Q3/Q4 contracts
in SLICE2, SLICE3 additions, DEPS retarget, status/frontmatter); (2) `roadmap.md` (standing
decisions, Deferred rows, I02–I04 one-liners, dead source ref); (3) `ledger.md` append-only
(E49+); (4) `notes/artifact-schema-and-grammar.md` (§4 contract-block rule, §5 ledger GC +
reflection typing, §6 interim tick rule); (5) `notes/i02-handoff-verify-gate.md` (affected-path
baselines, TEST-DEFECT, phase-1 exit criterion, mutation posture); (6)
`notes/role-prompts-conformance.md` (merge bridge §8A); (7) a new rationale note. Then re-run the
dogfood check and `authoring-check`.

---

## Q35 — what does `commands_for(None)` own? (raised during SLICE2 implementation)

**Question.** CT4b defines `PlanIds.plan_commands` as the ```verify blocks *before the first
slice heading*. CT16, written later in the same slice, stops a slice section at the first
heading of depth ≤ its own — so the increment-level sections that the last slice used to absorb
are now outside every slice. A verify block in one of them would be present in the flat
`.commands` and reachable from no record: verbatim the harm CT4b's "Catches" clause names, in a
position CT4b does not cover. Which semantics does `commands_for(None)` carry?

**Options considered.**
- (a) **Unowned** — every command outside every slice section (prologue *and* tail).
- (b) Prologue-only, plus a SLICE3 pre-check WARN on orphaned blocks.
- (c) Prologue-only, orphan recorded as a known gap for I02.

**Verdict: ✅ DECIDED — (a), operator-confirmed 2026-10-06.**

**Reasoning.** (a) satisfies CT4b's letter, because the prologue is a subset of the unowned; what
widens is the contract's reach, onto a class that did not exist when it was drafted. It makes
ownership *total*: every command belongs to a slice or to the plan, so orphaning is impossible by
construction rather than detected by a guard. (b) builds a watchman instead of removing the
cause — it would warn about a perfectly legitimate DoD verify block, producing noise, and the
command would still be unreachable to a per-slice consumer. (c) knowingly ships a defect already
in view, at a repair cost of one line of definition.

**Second-order effect, and the strongest argument for (a).** CT4c previously pinned the flat
field with `⊇`. That assertion is weak: it passes when `plan_commands` is empty and it tolerates
extra junk in the flat field. Totality lets CT4c assert an exact identity instead —
`set(.commands) == set(.plan_commands) | ⋃ set(record.commands)` — which fails if a command is
dropped, duplicated into the wrong slice, or misattributed.

**Blast radius.** Measured at `d2faea4`: `increment-01` has zero post-last-slice verify blocks,
so present behaviour is unchanged; the broadening is future-proofing. Naming stays honest —
"plan-level commands" reads as "belonging to the plan rather than to a slice", which is what a
DoD verify block is. Consequence for I02: `commands_for(None)` is its plan-level gate input.

**Recorded as:** ledger E87; CT4b, CT4c and STEP3 amended in `increments/increment-01-…md`.
