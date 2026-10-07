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
