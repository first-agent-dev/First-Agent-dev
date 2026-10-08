# Open questions — raised 2026-10-07 during I01/SLICE4

Canonical record. Next free id after this file: **Q44**.

> **All three resolved by the operator on 2026-10-07** (ledger E113) and implemented in
> I01/SLICE4: **Q40 → (b)** the skeleton must be a valid plan, skills and inject files
> edited; **Q41 → (i)** SLICE4 finishes migrating both `SKILL.md`; **Q42 → (i)** I01 fixes
> the grammar tokens, behaviour text stays I03's. The original text is left unedited below
> as the record of what was asked.

---

## Q40 — The skill skeleton cannot pre-check clean, because it is a template

**Status: RESOLVED (b) — 2026-10-07.** Blocked I01/SLICE4 STEP1; now CT40.

**Measured.** Both `PLAN-SKELETON` blocks fail the SLICE3 pre-check with 3 ×
`deps-undefined-slice` each, from one line:

```
DEPS: SLICE<a>, SLICE<b> | —
```

`plan-authoring/SKILL.md:680`, `feature-planning/SKILL.md:198`. The tokens the parser sees
are `SLICE<a>`, `SLICE<b>` and `|`. `<a>` is a placeholder and `|` is the skeleton's
"choose one" notation; the parser reads both as literal slice names. CT22
(`test_skill_embeds_a_skeleton_block_that_parses`) never caught this because it asserts the
skeleton *parses*, never that it pre-checks.

**Why it blocks CT14.** CT14 wants "a sample increment authored **strictly from** the
migrated skill text". The honest construction is to derive the sample from the skeleton by
mechanical substitution — then the sample provably has the skeleton's structure. That is
impossible while this line exists: any fixed rule ("take the first alternative") yields
`SLICEa, SLICEb` and still fails. Only picking the *second* alternative (`—`) works, and
choosing it by hand is the tuning-the-fixture-to-the-lint theater `tests-writing` forbids.

**Options.**
- **(a) Templates are out of pre-check scope.** Extend CT21b to the skills. Skeleton keeps
  `<a>` / `|`; CT14's fixture is a separate hand-authored sample, kept honest by two-sided
  construct conformance (the grammar constructs the skeleton teaches == those the sample
  uses). No parser change, no skill-text change.
- **(b) The skeleton must itself be a valid plan.** Replace the alternation with a literal
  (`DEPS: —`) and move "or list the slices you depend on" into adjacent prose. CT14's
  fixture is then derived mechanically. **Precedent:** SLICE1b/STEP2 already ruled that the
  §4 example must use literal ids, "or it does not parse and proves nothing".
- **(c) Teach the pre-check a placeholder notion.** A line containing `<…>` is a template
  line; a document of template lines is a template. Friendliest to an author who copies the
  skeleton and immediately lints it, but it is a new grammar rule needing its own `CT#`.

**Recommendation: (b), keeping (a)'s conformance check as a safety net.**

---

## Q41 — The planner skills are half-migrated: prose still teaches the pre-rename `S#`

**Status: RESOLVED (i) — 2026-10-07.** Now CT41, STEP3.

**Measured 2026-10-07** (occurrences of the bare `S#` token vs the post-rename ids):

| producer text | `S#` | `SLICE…` | `STEP…` | injected at |
| --- | --- | --- | --- | --- |
| `plan-authoring/SKILL.md` | **10** | 4 | 5 | planning (L2), `coder_loop.py:895` |
| `feature-planning/SKILL.md` | **8** | 6 | 4 | planning (L2), `coder_loop.py:895` |
| `feature-planning/INJECT.md` | **3** | 0 | 0 | coder slice entry, `coder_loop.py:247` |
| `tests-writing/INJECT.md` | 0 | 0 | 0 | coder slice entry |
| `src/fa/inner_loop/prompt.py` | **0** | 15 | 5 | every role prompt |

`prompt.py` was migrated by SLICE1c and is clean. The skills were **not**: SLICE1b added a
`SLICE#`/`STEP#` skeleton but left the surrounding prose on the old grammar. The sharpest
case is `plan-authoring/SKILL.md:173`, whose id table still *defines* the tier:

```
  S#   Step / task card               (§8)
```

So the planner is handed one document that teaches `S#` in its id table and `STEP1:` in its
skeleton. The parser rejects `S#` inside a plan as ambiguous (E106 / CT37). The skill
contradicts itself, and the half that loses is the half the harness can read.

**Sub-point.** `feature-planning/SKILL.md:381` and `INJECT.md:20` write `EDIT PACKET E# / S#`.
In this planning folder `E#` is the **evidence-ledger** id. Different documents, but the same
agent reads both.

**Options.** (i) SLICE4 finishes the migration — it is "plan grammar", which E45/E47 assign
to I01. (ii) A new slice SLICE5 owns it, keeping SLICE4 to CT14. (iii) Out of I01; a named
later increment. **Recommendation: (i) for the two `SKILL.md` files**, because CT14 cannot
honestly claim "authored from the migrated skill text" while the text is not migrated.

---

## Q42 — Is `INJECT.md` in CT14's conformance scope?

**Status: RESOLVED (i) — 2026-10-07.** Now CT41, STEP4.

**Measured.** `feature-planning/INJECT.md` is 59 lines, contains **no `PLAN-SKELETON` block
and no plan-grammar token at all** (`SLICE`, `STEP`, `CONTRACTS:`, `DEPS:`, `TESTS:`,
`INTENT:`, `verify`, `exit:` — all zero). It passes the parser **vacuously**: zero slices
parsed, zero diagnostics, because there is nothing in it to check. `plan-authoring/` has no
`INJECT.md` at all, and is not in `CEREMONY_SKILLS`.

**The two injections are different stages, not duplicates:**

| path | file | stage |
| --- | --- | --- |
| `coder_loop.py:895` (`_drive_session_inner`) | **`SKILL.md`**, full body incl. skeleton | planning / L2 expansion |
| `coder_loop.py:247` (`_ceremony_blocks`) | **`INJECT.md`** | coder, at slice entry |

**Therefore:** the text the *planner* actually receives when it writes a plan is
`SKILL.md` — so yes, **SKILL.md is the right conformance target for CT14**, and checking
only `INJECT.md` would verify a file the planner never sees.

**The open part** is ownership of INJECT.md's 3 × `S#`. E45/E47 assign *coder behaviour* to
I03, which would make INJECT.md I03's. But these three tokens are *grammar*, not behaviour,
and grammar is I01's. Options: (i) I01 fixes the grammar tokens in INJECT.md and leaves its
behaviour to I03; (ii) INJECT.md is wholly I03's and the stale grammar is registered as debt;
(iii) CT14 covers every injected text, SKILL.md and INJECT.md alike.
**Recommendation: (i)** — a grammar token is grammar wherever it lives, and leaving it
teaches the coder an id form the parser rejects.

---

## Q43 — The accessors are a second lenient surface that E106 never named

**Status: OPEN. Raised by I01's DoD walk, 2026-10-07. Does not block I01.**

E106 (Q/S-c) decided: `parse_slice_id` is **strict** inside a plan, because `S2` is
ambiguous there between a slice and a step; `canonical_slice_id` **keeps** its leniency, and
the decision scoped that leniency to "the eval-report boundary
(`workflow_controller.py:336`), because a report has one namespace".

**Measured.** The accessors `commands_for`, `tests_for` and `section` *also* canonicalise —
`ids.commands_for("S1") == ids.commands_for("SLICE1")` is an asserted behaviour
(`tests/test_plan_ids.py`, `test_accessors_accept_either_id_grammar`). So there are **two**
lenient surfaces, and E106 named only one.

**Why it matters.** The accessors are what I02 and I03 will call. If a caller holds a step id
and passes it where a slice id is expected, a lenient accessor silently resolves it to the
wrong object instead of returning nothing — exactly the ambiguity E106 set out to remove.

**Options.** (i) Ratify: an accessor call is a single-namespace lookup like a report, so the
leniency is correct; amend E106's wording to name both surfaces. (ii) Tighten: accessors take
strict ids, and a caller that holds a legacy id canonicalises first; the three assertions
change. (iii) Split: lenient lookup stays but returns a flag, so a caller can tell an exact
hit from a canonicalised one.
**Recommendation: (i)** — but it must be *decided*, because today it is an accident of
implementation rather than a stated rule, and I02 is about to build on it.

## Q44 — Kill-directive diagnostics must name `file:line`, and nothing in I01's surface carries a line

**Status: OPEN. Raised while implementing I02/SLICE2, 2026-10-08. Resolved provisionally so
SLICE2 can ship; the choice is reversible and the operator may overrule it.**

**Measured, by source read.** CT51 and CT52 require every kill-directive diagnostic to name
`file:line`, in the manner of `heading-near-miss` (CT26) and `step-near-miss` (CT37). But:

- `SliceRecord` has no line field — `slice_id, intent, contracts, test_paths, steps_mode,
  commands, section, tests_note` (`plan_ids.py:156-167`);
- `PlanIds` carries no raw text either — `slices, gaps, contracts, tests, commands,
  slice_records, plan_commands` (`:183-192`);
- the house precedent solves this by scanning the **whole document**:
  `_rule_step_near_miss(text, path)` enumerates `text.splitlines()` and its docstring argues
  the whole-document scan explicitly (`:745-756`).

So CT50's "`parse_kill_directives(section)` reads `section()` output" and CT52's "`file:line`"
cannot both be satisfied without something bridging section-relative lines to absolute ones.
The sharp version of the question is one of **ownership**: may I02 reach for the raw plan text
to locate what I01 parsed, or should I01 grow the offset?

**Options.**
(i) **I02 scans the document, I01 stays sealed.** `parse_kill_directives(section)` keeps CT50's
signature and reports section-relative lines; `validate_kill_directives(plan_text, ids, path)`
does one whole-document pass for absolute lines, asking I01 (`ids.contracts`,
`contract_class`) what is a contract and what class it is. I02 locates ids it did not define;
it never decides what a contract *is*. Cost: a small shape regex (`^\s*CT\d+[a-z]?\s*\[`) lives
in two modules.
(ii) **I01 grows `SliceRecord.start_line`** (and contract line offsets). Ownership stays clean
and every later consumer benefits. Cost: an I01 change after I01 was called done, a new
exported field, and D8's drift risk between the surface and schema §7.
(iii) **I02 computes the offset by substring search** — `plan_text.find(record.section)`, exact
because `section` is sliced verbatim from the text. Cheapest, but couples I02 to a layout
detail I01 owns, and goes quietly wrong the day a section is ever normalised.

**Recommendation and provisional resolution: (i).** It is the only option that adds no I01
surface, keeps CT50's signature verbatim, and reuses the whole-document pattern the pre-check
already justifies for exactly this reason. The duplicated knowledge is bounded to "a contract
entry starts with its id in brackets", and every id it finds is validated against
`ids.contracts`, so a drift in that shape degrades to "no line found", never to a wrong class.
**If a second consumer ever needs line offsets, switch to (ii)** — at that point the field
earns its keep and option (i)'s regex should be deleted, not copied a third time.

---

## Q45 — should the contract→line map move into I01, retiring I02's copy of the grammar?

**Status:** OPEN. Supersedes the provisional resolution of Q44 if answered "yes".

**Raised by** the operator, 2026-10-08: *"разве мы не парсим их по якорям `#CT-N`? так же можно
машинно получать всегда корректный номер строки, даже если план сдвинется по структуре."*

### What is true

There is no `#CT-N` anchor construct — `grep` over the whole planning folder finds zero
anchors of any form (`#CT-N`, `{#…}`, `<a id=>`), and the schema never uses the word. But the
premise behind the question is right: **the contract id is itself the anchor.** `CT44` is a
unique token that I01 already canonises (`_CONTRACT_RE`), and anchoring on it would survive
any structural shift of the plan — which is precisely the property that a locator keyed to the
*entry shape* lacks, as E152 demonstrated at the cost of a real defect.

### What is also true, and decides it

Measured over both real plans, locating a contract by **first occurrence of its id token**:

| plan | declared | disagreements with the true declaration line |
| :--- | ---: | ---: |
| increment-02 | 41 | **0** |
| increment-01 | 42 | **8** |

The I01 failures are not noise, and three of them name the mechanism:

- `CT17`/`CT18` declared at 231/236, first mentioned at line **22** — a forward prose
  reference, "see CT17/CT18", **209 lines early**.
- `CT3` declared at 201, first mentioned at **53**, inside CT2's own text, which quotes
  `` `CT3 [CONSTRAINT]: …` `` as an *illustration*. This is the exact case I01's CT18 exists to
  defend against, now biting a second consumer.

Pointing an operator at line 22 for a defect at line 231 is worse than reporting no line at
all. So the naive id-anchor is out; scoping the search to the owning slice section narrows it
but does not fix the quoted-illustration class, because the illustration sits in the same
CONTRACTS block as the declaration it imitates.

### The fork

Anything correct must therefore recognise *an entry*, not *a mention* — which is grammar, and
grammar is I01's. Two honest options remain:

- **(A) Keep today's arrangement.** I02 holds a locator mirroring `plan_ids._CONTRACT_ENTRY_RE`,
  with `test_every_contract_in_a_real_plan_is_locatable` pinning the agreement over both real
  plans. Cost: one duplicated regex, bounded by a drift oracle. Already shipped and green.
- **(B) Move it to I01.** `PlanIds` grows a contract→line map (or `SliceRecord` grows
  `start_line`), and I02 deletes its copy. One source of truth; the duplication cannot drift
  because it no longer exists.

**(B) is the stronger engineering answer, and the SD-B objection that blocked it has lapsed.**
SD-B forbids an accessor without a named consumer increment; when Q44 was first weighed there
was none, so (i) was chosen. I02/SLICE2 is now a shipped consumer that was *actually burned* by
the duplication. The bar is met.

**Why this is not being done unilaterally:** I01 is a closed increment, and widening the
surface of a closed increment is a scope decision, not a refactor. It also costs a second
round of kill-checks and a mutation sweep on `plan_ids.py`. Operator's call.

**If (B) is chosen, the work is:** add the map to I01's extractor behind its own contract and
kill-check; delete `slice_verification._CONTRACT_ENTRY_RE` and its drift oracle; keep the `0`
sentinel semantics ("line unknown") so the degradation story is unchanged; re-run both sweeps.
Estimated one slice-sized unit of work, and it shrinks I02 rather than growing it.
