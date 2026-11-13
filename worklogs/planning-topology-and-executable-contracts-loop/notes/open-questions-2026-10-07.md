# Open questions — raised 2026-10-07 during I01/SLICE4

Canonical record. Next free id after this file: **Q91** after Q90 below.

**Current owner/disposition alignment, 2026-10-15 (E200–E203):** retained I02 owns explicit-plan
Q57/Q58, CT92 rules and local admission/gate proof. Q59/Q60 exact nested choices, Q61/CT97
foundation implementation, Q66 propagation and Q63 final E2E schema are I03 consumers, not I02
shipping dependencies. Broad design directions are recorded in the execution decision note; this
owner migration does not mark exact Q59–Q63 fields/choices or runtime proofs RESOLVED.

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

**2026-10-15 source correction:** current `src/fa/inner_loop/plan_ids.py:218–255` uses exact
strict `_record` lookup; the measured lenient behavior below is historical. I02 preserves current
semantics and uses only extractor-origin IDs. This correction does not ratify a Q43 option or
rewrite its historical Status; any proposed semantic change still needs explicit disposition.

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

**Status: RESOLVED (B) by operator, 2026-10-14.** The operator confirms the I01 parser-surface expansion was already decided; keep the source-position surface and CT78–CT80. This supersedes the former OPEN status below.

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

**Why this was not done unilaterally at the time of the original review:** I01 is a closed
increment, and widening the surface of a closed increment is a scope decision, not a refactor. It
also costs a second round of kill-checks and a mutation sweep on `plan_ids.py`; operator approval
was needed.

**Work proposed at that time (subsequently ratified below):** add the map to I01's extractor
behind its own contract and kill-check; delete `slice_verification._CONTRACT_ENTRY_RE` and its
drift oracle; keep the `0` sentinel semantics ("line unknown") so the degradation story is
unchanged; re-run both sweeps. Estimated one slice-sized unit of work, and it shrinks I02 rather
than growing it.

**Operator resolution, 2026-10-14 — option (B), RATIFIED.** The operator confirms that expanding the closed I01 parser surface for source positions was already decided. Retain `SliceRecord.start_line`, `SliceRecord.contract_lines`, and `PlanIds.contract_line()`; keep the I02 locator regex retired. Q65 records the same disposition. This decision resolves scope only; implementation proof remains the relevant test/kill evidence, not this answer.

---

## Q46 — does the provenance probe get its own timeout, or share the verify budget?

**Status:** **RESOLVED (b)** by operator ruling, 2026-10-08. Raised by SLICE4's implementation,
2026-10-08, and promoted rather than decided quietly because it is a policy choice about when
the harness declares `ERROR`, not an implementation detail.

**The situation.** `_assert_overlay_wins` runs `python -c "import <module>; …"` through
`_run_one`, which requires a per-command budget. The only budget that exists is
`DEFAULT_VERIFY_TIMEOUT_SECONDS` (600 s), sized for a test suite. A provenance probe is an
import and finishes in milliseconds.

**Options.** **(a) Share the verify budget** — one constant, and the probe fails under exactly
the conditions the command it vouches for would. A hung import costs 10 minutes before the
kill-check is marked `ERROR`. **(b) A dedicated probe budget** (a few seconds) — faster
failure, but a second constant to tune and a new way for the probe and its command to
disagree: a machine slow enough to time the probe out would likely have timed the command out
too, and then the operator sees `ERROR` from the probe rather than the real signal.
**(c) Make it a parameter** and let SLICE5 decide per call.

**Provisionally (a), and implemented.** I had written (c) — a `timeout_s` parameter with a
`None` default — and mutation testing exposed it as dead surface: no caller passes it, so
`_command_timeout(timeout_s)` and `_command_timeout(None)` are indistinguishable. The
parameter was removed rather than pinned by a test for a caller that does not exist (SD-B).

### Resolution — (b), a declared sanity-check budget

`DEFAULT_PROBE_TIMEOUT_SECONDS = 30.0`, separate from the verify budget and used directly by
`_assert_overlay_wins`.

The operator's reasoning, which corrects the premise of option (a): 600 s sizes **the work the
slice asked for** -- a suite, a compile, a heavy check. A provenance probe is an
*infrastructure assertion* about the execution environment, and putting the two on one timeout
is a leaky abstraction, because the number can then only be tuned for one of them. The
consistency argument that justified (a) applies to scrubbing, `cwd` and output handling -- the
things that must match the command being vouched for -- and not to the budget, which is
measuring something else entirely.

30 s is deliberately generous rather than derived: enough for a cold import on slow I/O, and
the value of the choice is the 9.5 minutes it saves on a genuine hang. Deferring it to SLICE5
"once there is a measured distribution" was perfectionism pointed the wrong way -- **a hang
caused by an agent bug happens before any such measurement exists**, which is precisely when
the budget matters.

**Measured, not argued.** Executing the regression (probe put back on the verify budget) made
the hanging-probe oracle take **600.6 seconds** instead of ~1. The cost of (a) is not
theoretical and is now on the record.

**Not to be unified:** the constant equals `runtime_limits.DEFAULT_BASH_TIMEOUT_SECONDS` by
coincidence, not derivation. That one sizes an interactive shell call the model issues
mid-turn; collapsing them would let a change made for the model's benefit silently retune this
gate's failure detection. Stated in the code comment as well, because the coincidence is an
invitation.

## Q47 -- `hits` cannot mean both "targets matched" and "calls replaced"

**Status:** **RESOLVED (d) + exact qualified name** by operator ruling, 2026-10-08.
Found by reading CT57 against STEP2b before writing any code.

> The operator's ruling, verbatim in substance: *merging the two notions into one*
> `hits` *in CT57 was an architectural design bug.* `targets` *is a question of search
> -- locating the anchor in the AST -- and must be strictly 1: 0 is* `PRODUCER_ABSENT`,
> *>1 is* `ERROR`. `edits` *is a question of transformation -- how many nodes did we
> modify? For* `neutralise` *always 1; for* `remove-call` *legitimately 0..N, since one
> method may hold four calls to a logger or an emitter.* Plus: put the invariant in
> `__post_init__`, so the constructor cannot assemble a result that lies.

### What SLICE3 is for, so the numbers have a job

A contract may declare `kill: neutralise path::symbol` or
`kill: remove-call path::symbol -> callee`. The claim is: *break this producer and the slice's
own tests must go red*. SLICE5 will cash the claim by applying the mutation to a copy of the
source, running the tests in SLICE4's overlay, and mapping the result onto the status lattice:

| what happened | status |
| --- | --- |
| mutation applied, tests went red | `PROVEN` |
| mutation applied, tests still green | `VACUOUS` -- the test does not test it |
| the named symbol is not in the source | `PRODUCER_ABSENT` -- the plan is ahead of the code |
| the directive names more than one thing | `ERROR` -- never guess which |

`apply_kill` is the pure half: source text in, mutated source text out (CT58 forbids it from
touching the filesystem or a subprocess). It must hand the caller enough information to pick
the right row, and **the difference between the last two rows is the whole reason this slice
exists** -- "the producer is missing" must be distinguishable from "the test is weak", which
is the slice's stated INTENT.

### The contradiction

CT57: "`hits == 0` means the target is absent and the caller raises `PRODUCER_ABSENT`;
**`hits > 1` is an ambiguous target** and the caller raises `ERROR`, never a guess."

STEP2b: "assert the four-call-form sample yields **`hits == 4`**".

The four-call sample is the one CT56 was written to defend: `a = emit(x)`, `emit(x)`,
`if emit(x):`, and a call inside a comprehension. The measured finding is that deleting only
`ast.Expr` statements sees **1 of 4**, so `remove-call` must replace *every* call form. The
normal, correct outcome for `remove-call` is therefore several replacements -- and under CT57
that same number is read as "ambiguous" and rejected. **The slice's headline capability is
unreachable through its own gate.**

The cause is visible once stated: CT57 was written while thinking about `neutralise`, where
"targets matched" and "edits made" are the same number (you find one function, you blank one
body). For `remove-call` they come apart -- one target, four edits. One integer cannot carry
both.

### The facts a caller actually needs

1. **Did the directive name exactly one thing?** `0` -> `PRODUCER_ABSENT`; `>1` -> `ERROR`.
2. **How much did the operator change?** `neutralise`: 0 or 1. `remove-call`: 0..n, and `0`
   with the symbol present still means `PRODUCER_ABSENT` -- the call site the contract claims
   exists, does not.
3. **The mutated source**, which is meaningless and *dangerous* unless 1 and 2 both passed.

Point 3 is the sharp edge. If a caller ignores the counts and runs the tests against source
that was never mutated, the tests pass and it reports `VACUOUS` -- accusing a good test of
being weak when the real story is a missing producer. That is the same class of false
accusation CT50b was created to stop (E-note: three directives naming `_Silence.visit_Call`
resolved to nothing under a bare-name reader).

### Options

**(a) `hits` counts replacements; ambiguity raises inside `apply_kill`.**
Resolve the symbol first; two or more matches raise. `hits` then means "edits made": `0` ->
`PRODUCER_ABSENT`. STEP2b stands.
*Cost:* the caller handles two channels, return and exception, for one question. A pure source
transform that also raises is harder to reason about, and the lattice decision is now split
across a `try` and an `if`.

**(b) Return a bare 3-tuple `(source, targets, hits)`.**
Keeps `apply_kill` total. The caller owns the whole lattice, as CT57 intends.
*Cost:* two adjacent `int`s in a positional tuple. `source, hits, targets = apply_kill(...)`
type-checks perfectly and inverts the lattice -- mypy cannot see a transposition of two
`int`s. And nothing stops a caller using `source` when it is meaningless.

**(c) Keep CT57 verbatim; weaken STEP2b to `hits == 1`** by counting the enclosing symbol.
*Cost:* nothing then proves the four-call-form behaviour, the measured finding CT56 exists to
encode. The slice ships its central behaviour untested. **Rejected.**

### (d) -- recommended: a named result, and `None` where the source is not usable

```python
@dataclass(frozen=True)
class KillApplication:
    """What one directive did to one source text. (CT57)"""

    source: str | None  # the mutated text; None unless it is safe to run
    targets: int  # definitions whose qualified name is the directive symbol
    edits: int  # bodies neutralised (0 or 1) / call sites silenced (0..n)
```

`apply_kill(source, directive) -> KillApplication`, total, never raising. `source` is `None`
whenever `targets != 1 or edits == 0`.

Two properties neither (a) nor (b) has:

- **The type system enforces the branch.** `source: str | None` means a caller cannot write
  the mutated text into the overlay without first establishing that there is one -- mypy
  refuses. The dangerous path from point 3 above, running a no-op mutation and blaming the
  test, stops being a matter of discipline and becomes a compile-time error. This is the one
  design property worth paying for here.
- **Field names, not positions.** `targets` and `edits` can no longer be transposed, and they
  read the same way in the code, in an eval report and in a test assertion.

It also keeps every lattice decision at the single call site that owns the lattice (CT57's
intent, and the Single-Source-of-Truth principle the Q45-B ruling turned on), adds no new
vocabulary -- no third status enum beside the lattice, nothing CT59 or the §5 "no mutation
DSL" rule would object to -- and leaves STEP2b intact with `edits == 4`.

*Cost:* one frozen dataclass, in a module that already holds `CommandResult`, `KillDirective`
and `SliceRecord`. House style, not new machinery.

### A resolution rule that shrinks the ambiguity case (part of the same decision)

I had provisionally resolved symbol lookup as "any unambiguous dotted **suffix** of the
qualified path", so a bare `visit_Call` would match `_Silence.visit_Call`. On review that rule
is what *manufactures* most ambiguity, and it is not what any directive written so far needs:
every directive in this plan already spells the symbol out in full (`::apply_kill`,
`::_Silence.visit_Call`). Proposal, bundled into (d):

> **Exact qualified name, anchored at module root**, split by `_split_dotted` (CT50b).

Then `targets > 1` is only reachable when a module genuinely defines the same qualified name
twice -- a `try/except ImportError` fallback, a platform-conditional `def`, a redefinition
bug. It stays in the contract because silently mutating one of two definitions is exactly the
guess CT57 forbids, but it becomes the rare guard it should be rather than the common case. A
mis-spelled or under-qualified symbol now lands on `PRODUCER_ABSENT`: loud, accurate, and
already a status the lattice carries.

### Consequent plan edits if (d) is chosen

- CT57 reworded: two counts, their separate meanings, and `source is None` as the
  not-safe-to-run signal.
- CT56 unchanged. CT58 unchanged (purity is strengthened: no raising either). CT59 unchanged.
- STEP2b keeps `== 4`, renamed to `edits`.
- STEP3 names `KillApplication` as part of the producer set.

## Q48 — may a contract's kill directive name a producer another slice builds?

**Status:** **RESOLVED (c)** by operator ruling, 2026-10-08.

> The operator's diagnosis, which is the one now written into schema §4: this is a category
> error -- two different notions were mixed in the architecture. An *interface contract*
> ("a future module must provide `_run_kill_check` with this signature") is a legitimate
> architectural requirement. A *kill directive* ("cut this call and my current tests fail")
> is an instrument of test-suite quality hardening, and is **physically incapable of being
> an interface specification for future code**. Attempting it springs the name-guessing trap
> or the vacuous trap. A constraint on a future slice belongs in structural requirements or
> public interfaces -- the expectation as `INTENT:` prose in the slice that needs it, the
> contract and its directive declared in the slice that builds the producer, so that when
> that slice is written its own directive fires against its own tests and yields an honest
> `PROVEN`. Ruling: **option (c)**, and CT62 folds into SLICE4.

Found by the directive audit that SLICE3 made possible: `apply_kill`'s resolver can now be
pointed at every directive in both plans. **14 of 30 cannot fire today.** Twelve are SLICE5
and SLICE6 producers that do not exist yet -- legitimate, and the register already tracks
them. One is CT62, recorded as DEFERRED when SLICE4 shipped. The fourteenth is a defect in a
**shipped** slice:

```
CT50b (SLICE2)  kill: remove-call …::_resolve_symbol -> _split_dotted
```

`_resolve_symbol` was SLICE2's guess at a name SLICE3 would later provide. SLICE3 shipped it
as `_resolve_targets`, which does call `_split_dotted`. So the directive reads
`PRODUCER_ABSENT` against working code -- the exact false accusation CT50b itself was written
to prevent, which is a pointed demonstration that the class is real.

**Renaming the symbol is not the fix.** Measured: applying
`remove-call …::_resolve_targets -> _split_dotted` leaves SLICE2's own test file
**36 passed, fully green**, and reddens SLICE3's **18 of 27**. A kill-check runs the tests of
the slice that owns the contract, so after the rename CT50b would fire, find SLICE2's tests
unmoved, and report `VACUOUS` -- accusing a sound test file of being weak. That is a worse
state than today's honest "absent".

The real cause: **CT50b makes two claims that live in two slices.** The grammar accepts a
dotted symbol (SLICE2's parser, proven by `test_kill_directives.py`), and the operators
resolve one (SLICE3's resolver, proven by `test_kill_operators.py`). A single directive
cannot be killed in both places, because the evidence lattice is per-slice.

**Option (a) — split the contract.** CT50b keeps the grammar half and takes a directive that
fires inside SLICE2; a new contract in SLICE3 (next free id **CT81**) takes the resolution
half with the directive measured above. Each half is then provable where it lives.
*Cost:* a new contract id on a shipped slice, and a second place to read about dotted symbols.

**Option (b) — a kill-check runs the tests of the slice owning the *producer*,** not the
contract. One directive stays sufficient for a cross-slice claim.
*Cost:* changes SLICE5's verdict assembly before it is written, and weakens a useful property
-- today a slice's verdict depends only on that slice's declared tests. It also needs a rule
for producers no slice claims.

**Option (c) — a directive may name only a producer its own slice builds**, enforced by the
validator, and CT50b's resolution half moves wholesale into SLICE3.
*Cost:* the strictest and the most honest; it would have caught this at authoring time
instead of after shipping. But it forbids a contract from constraining downstream slices,
which CT62 (SLICE4 naming SLICE5's `_run_kill_check`) deliberately does.

**Recommendation: (a) now, and (c) as a validator rule once SLICE5 exists** -- (c) would have
prevented this and CT62's deferral both, but it is a plan-wide rule and belongs with the
component that can enforce it. Left untouched pending a ruling: today's `PRODUCER_ABSENT` is
wrong but honest, where the rename would be wrong and confident.

### What was built, and one mechanism considered and declined

Schema §4 gains the normative rule; `roadmap.md` gains the standing decision; CT84 (SLICE5)
carries it as a CONSTRAINT.

Relocations, each one **measured against the tests of the slice that now owns it** before
being written down -- fixing unfirable directives while adding another would have been the
same sin:

| contract | was | now | fires |
| :--- | :--- | :--- | :--- |
| CT50b (SLICE2) | `remove-call ::_resolve_symbol -> _split_dotted` | `neutralise ::_split_dotted` | **4F** |
| CT81 (SLICE3, new) | — the resolution half of CT50b | `remove-call ::_resolve_targets -> _split_dotted` | **18F** |
| CT62 (SLICE4) | `remove-call ::_run_kill_check -> _assert_overlay_wins` | `neutralise ::_assert_overlay_wins` | **9F** |
| CT82 (SLICE5, new) | — the wiring half of CT62 | `remove-call ::_run_kill_check -> _assert_overlay_wins` | when SLICE5 is built |

Enforcement is CT83: `scripts/check_kill_directive_ownership.py`, failing when a slice whose
`STEP` boxes are **all ticked** declares a directive that does not resolve. The tick is the
trigger because an unfinished slice is *expected* to point at code that does not exist. After
the relocation the audit reports **0 defects on ticked slices** and 14 pending on unfinished
ones -- the separation that did not exist before, and the honest reading of the original
"14 of 30": twelve were the plan legitimately ahead of the code, two were the category error.

**Declared, then declined: a `PRODUCES:` field** listing each slice's `path::symbol` outputs,
which would let the pre-check refuse a foreign directive at *authoring* time rather than at
tick time. Measured as cheap to add -- the pre-check tolerates the unknown field with no new
diagnostics -- but rejected for now on two grounds. It duplicates what the code already
states, so it can drift from the truth and would need its own check to stay honest; and it is
plan-*grammar*, which is I01's surface, closed. CT83 catches the same defect one step later at
a fraction of the cost. Recorded here because the idea will occur to the next reader too.

**Not done: a dedicated slice.** I02 holds exactly 7 slices and `_rule_slice_count` warns at
the ceiling, reading an eighth as a mis-scoped increment rather than a long one. The work went
to SLICE5, which is unstarted and already owns `PRODUCER_ABSENT` in the lattice, so the rule
lands beside the classification it refines and before SLICE6 authors anything new.

## Q49 — where does `REGRESSION`'s "before" come from? (absorbs H3 and H7)

**Status:** **RESOLVED (a), with two corrections** by operator ruling, 2026-10-08.

The seam stands: SLICE5 accepts a baseline it does not gather; SLICE6 adds the capture point
(CT86). Two risks raised in review were accepted and are now CT68/CT85:

1. **Key by pytest nodeid, never by file.** A file-keyed baseline turns one newly-added
   failing test into a red *file* and reports `REGRESSION` where the truth is `FAILING` — and
   an agent adding a deliberately-red test is the common case here, not the rare one.
   Consequence, which is a design statement and not a detail: the baseline and the "now" side
   must both be **harness-issued instrumented runs** (`--junitxml`), because the planner's
   `verify` commands run verbatim (`cli.py:165-170`) and yield only an exit code and a
   truncated tail. No nodeid is recoverable from them. CT69 now says so.
2. **Capture once, at T0.** `repair_round` admits several coder stages per run. If a repair
   round recaptured, round 1 could break an adjacent test, round 2 would adopt the breakage as
   the new normal, and nothing would ever be reported. CT85 forbids it; CT86 makes it
   structural by refusing to overwrite the artifact rather than trusting the call site.

Two further risks raised in the same review were **already closed in shipped code**, verified
against source rather than recollection: the provenance probe's timeout (Q46(b), `88e8040`,
`DEFAULT_PROBE_TIMEOUT_SECONDS = 30.0` mapping overrun to `ERROR`, with the 600.6 s
alternative measured) and the `uv` determinism pin (`_pin_uv_environment` sets
`UV_PROJECT_ENVIRONMENT` **and** `UV_NO_SYNC=1`; the former is deliberately absent from the
scrubber allowlist, and `_overlay_env` is built on top of `_build_env` so the overlay cannot
drift from a plain verify command). Both carry oracles, not just code.

CT68 says: *a test green at baseline and red after the change yields `REGRESSION`; red-to-red
is advisory and does not block.* Nothing in the plan says what "at baseline" means, and the
two handoff questions that would have said it were never answered — **H3** (baseline storage
path and lifetime) and **H7** (regression attribution scope), both recorded as "blocking
implementation only" in `i02-planning-readiness-2026-10-07.md` and never closed. They are one
question and are promoted here as one.

It is not deferrable past STEP1: whether `SliceVerification` carries a baseline, and what
`_classify` is handed, both follow from the answer.

### Source-verified constraints (measured today, not recalled)

| fact | where |
| :--- | :--- |
| the gate runs inside `_run_stage`, i.e. **after** a role has done its work | `workflow_controller.py:511` |
| the harness owns the stage loop, so a **pre-coder point exists** | `_run_linear:1061`, `_run_adaptive:913` |
| a run already has a per-run artifact home | `WorkflowArtifactPaths(base_dir, eval_report, flow_state)`, `:217` |
| one run may hold several coder stages | `progress.repair_round`, `:188` |
| the operator's tree must be byte-identical across a gate run, and `git worktree` is refused | CT64; SLICE4 docstring |
| the baseline may read only the slice's own `TESTS:` paths | CT69 |

And the fact that decides most of it: **a slice's `TESTS:` file is usually NEW.** It does not
exist before the coder writes it, so it can carry no "before" state at all. Whatever the
answer, `REGRESSION` can only ever be a statement about test paths that **already existed**.
That is H7's attribution scope, and it falls out rather than being chosen.

### Options

**(a) Capture before the coder stage, once per run.** The harness runs the slice's `TESTS:`
paths **that already exist** before dispatching the coder, and writes `verify_baseline.json`
beside `eval_report.json`. `REGRESSION` = green there, red now.
*Cost:* one extra run of those files per workflow run, bounded by CT69. Needs a new call site
in the stage loop, which is SLICE6 territory, so SLICE5 must take the baseline as an argument
rather than fetch it.
*Catches:* the case the verdict exists for — the coder's change broke something adjacent.

**(b) Capture at the first gate run; compare on later repair rounds.** No pre-coder work; the
first gate pass writes the baseline, round 2+ compares.
*Cost:* nearly free, no new call site.
*Blind to the main case:* at the first gate run the coder has already edited. A test the
coder broke in round 1 is red at baseline and never reported. It catches only regressions
introduced *by repairs*, which is the smaller half.

**(c) Materialise `HEAD` and run there.** `git archive HEAD` into a temp dir — never `stash`
or `worktree`, both of which CT64 and the SLICE4 docstring rule out.
*Cost:* the heaviest. A second environment to build, and the tests at `HEAD` are the *old*
tests, so a renamed test reads as a regression.
*Most faithful* to "before the change", and the only one that survives the harness being
restarted mid-run.

**(d) No baseline in I02.** `REGRESSION` leaves the emitted set; the gate reports PROVEN /
VACUOUS / PRODUCER_ABSENT / FAILING / ERROR / SKIPPED, and regression attribution lands in
I03 with the eval loop that already compares runs.
*Cost:* the increment's DoD demands `REGRESSION` demonstrated, so that line changes too. But
no lattice member is left that nothing can produce — which is the failure mode (d) avoids and
(b) creates in practice.

### Recommendation: (a), with the capture itself deferred to SLICE6

(a) is the only option that catches the case the verdict names. The split that makes it cheap
is already forced by the facts: `REGRESSION` is about **pre-existing** test paths, and those
are exactly the ones that can be run before the coder starts.

The clean seam: **SLICE5 accepts a baseline it does not gather.** `verify_slice(...,
baseline: Mapping[str, bool] | None)` — pytest nodeid → was green. `None` means no baseline was taken,
and then `REGRESSION` is simply not reachable and is reported as such, never as a pass. SLICE6
adds the pre-coder call site that fills it, which is where the stage-loop edit belongs anyway.
That keeps SLICE5 pure and testable, and it keeps the one risky edit in the slice whose job is
wiring.

A sub-decision that follows and does not need its own question: **a baseline row that could
not be established is not `False`.** If the pre-coder run errors, the row is absent, and an
absent row can never produce `REGRESSION` — consistent with the standing rule that `ERROR` is
never a pass.

**Implementation finding (E180):** stock pytest `--junitxml` serializes `classname` + `name`,
not `Item.nodeid`; on a real class/parameterized sample, the XML contained no exact nodeid and no
file attribute. The harness now has `fa.inner_loop.junit_nodeid_plugin`, which copies the
authoritative `item.nodeid` into a custom JUnit `user_property`; the real pytest/JUnit oracle
verifies class and parametrized nodeids. The runner must load this plugin explicitly and the
XML parser must reject a missing/duplicate property rather than reconstruct an ID.

## Q50 — does a single kill-check speak the slice's vocabulary, or its own?

**Status:** RESOLVED (a) by operator, 2026-10-08. The operator selected reuse of the
constrained `SliceVerdict`; STEP3 (`_classify`) consumes that answer directly.

CT65 says `SliceVerification` carries "the per-contract kill-check outcomes" and never names
their type. One kill-check can reach only four of the seven members: it speaks about a single
contract, so it cannot observe a failing verify command (`FAILING`), a baseline comparison
(`REGRESSION`) or a missing verify block (`SKIPPED`).

| | (a) reuse `SliceVerdict`, constrain it | (b) a separate `KillOutcome` enum |
| :--- | :--- | :--- |
| words in a report | one set | two, plus a mapping between them |
| illegal state | rejected at construction by `KILL_CHECK_VERDICTS` | unrepresentable by typing |
| `_classify` | reads members directly | must translate, and a translation can be wrong |
| risk | a reader sees `PROVEN` and must ask "of what?" -- the contract id is adjacent | the two vocabularies drift, and reports start saying `killed` where the lattice says `proven` |

**Ruling (a), confirmed by the operator.** The project's stated fear is vocabulary growth
(CT59, "no mutation DSL"), and (b)'s type-level safety is bought with a translation step
that is itself unverified. The constraint is enforced, not documented: `KillCheck.__post_init__`
raises on the three unreachable members, and an oracle proves it for each.

**What would overturn it:** if the operator wants per-contract and per-slice outcomes to be
distinguishable at a glance in the eval report, (b) is better and the cost is one mapping
function with its own oracle.

## Q51 — what command does the kill-check phase actually issue?

**Status:** RESOLVED (a) on agent recommendation, 2026-10-08, after the operator asked
whether (a) is the most correct option. It is not blocking for STEP3, but it is the one producer
in this slice that **no unit test executes verbatim** (the hermetic fixture substitutes it), so
it remains live-only risk and must be covered before SLICE6.

CT69 fixes *what* runs -- "only the contract's own test" -- and is silent on the command. The
slice's own `verify` fence cannot be reused: it is the planner's text, run verbatim
(`cli.py:165-170`), and may name several commands, a whole suite, or no pytest at all.

- **(a) a module constant, `uv run pytest {path} -q`** -- matches the deployed coder workspace,
  which is a uv project with `UV_PROJECT_ENVIRONMENT` pinned (`fa-entrypoint.sh`). The constant
  is also the seam a hermetic test substitutes, exactly as `_PROVENANCE_PROBE` already is.
- **(b) derive it from the slice's `verify` fence**, filtered to the contract's test path --
  closer to "the same run as the verify it judges", but the filtering is a guess about someone
  else's command line, and a `verify` fence holding `ruff` would have to be silently dropped.
- **(c) take it as a parameter from the caller** -- defers the choice to SLICE6 and makes the
  policy explicit at the composition root, at the cost of one more thing the controller must
  get right.

**Recommendation adopted (a).** Source verification confirms the live coder workspace is a
`uv` project, the runner pins `UV_PROJECT_ENVIRONMENT` and `UV_NO_SYNC=1`, and the hermetic
fixture needs a replaceable command constant. (b) parses a command line the planner owns, the
same class of mistake as parsing a contract body for a directive (F1); (c) moves policy into
the controller without a second runner being supported. If another test runner becomes a real
product requirement, make it explicit configuration rather than infer it from `verify` text.


## Q52 — what wins when a command fails and the baseline proves a test regression?

**Status:** RESOLVED (a) by agent after the operator instructed “Continue”, 2026-10-08. The
operator did not select an option; the agent adopted the fail-closed command-authoritative
interpretation below, grounded in the verbatim command contract (CT44/CT69).

### Source-verified facts

- CT65 returns one `SliceVerdict` for a slice; the result does not have a second status axis.
- `CommandResult.outcome` is independently one of `PASS`, `FAIL`, `ERROR`. `KillCheck.verdict`
  is independently one of `PROVEN`, `VACUOUS`, `PRODUCER_ABSENT`, `ERROR`.
- STEP3 explicitly says `ERROR` dominates, but gives no ordering for `FAILING` versus
  `REGRESSION`.
- CT68 says green-at-T0 → red-now is `REGRESSION`, and red-to-red is advisory and does not
  block. Under Q49, the comparison is by pytest nodeid.
- CT69 requires two harness-issued JUnitXML runs for nodeid evidence; the planner's `verify`
  commands remain verbatim and only supply exit status plus a truncated tail.

So both signals can be true: `run_commands` can report `FAIL` while the JUnitXML nodeid map
proves that a test which was green at T0 is red now. They can also disagree about whether the
underlying test failure is the whole reason for the failing command. A red-to-red test produces
no regression row, but the verbatim verify command can still return non-zero for it. The single
verdict then has to choose which fact governs routing.

| | (a) command exit remains authoritative | (b) the nodeid evidence refines test failures |
| :--- | :--- | :--- |
| precedence | `ERROR > FAILING > REGRESSION`; a non-zero declared command is blocking | `ERROR > REGRESSION > FAILING`; a proven green→red nodeid is the more specific result |
| red-to-red | no `REGRESSION`, but a non-zero command still yields `FAILING` | non-blocking only if the failure is attributable solely to those pre-existing red nodeids |
| consistency with CT68 words | requires clarifying “advisory and does not block” to mean “does not create a regression verdict” | preserves the literal non-blocking reading, but needs a reliable way to attribute an arbitrary verbatim command's failure to the separately issued JUnitXML run |
| implementation cost | the existing `CommandResult` and one verdict suffice | additional attribution/evidence or a separate result axis; CT65/CT69 may need amendment |

**Ruling (a), fail-closed, adopted by the agent after “Continue”.** The declared command's
exit remains authoritative: `ERROR` dominates; with commands present, a non-zero exit is
`FAILING` even if a baseline comparison also finds green→red; `REGRESSION` is returned only
when the declared commands pass. With no verify commands, the legacy result is `SKIPPED`.

“Red-to-red is advisory and does not block” applies to the *baseline comparison*: it creates no
`REGRESSION`. It does not suppress a separate non-zero result from the planner-owned command.
Because CT69 keeps these commands verbatim and exposes no reliable causal attribution,
suppressing their exit based on a separately issued JUnitXML run could turn an unrelated ruff,
shell, or setup failure into a pass. This reading preserves command authority and never lets
uncertainty present as success. A missing baseline/current JUnit report (`None`) with verify
commands present is `ERROR`; an empty mapping is a valid completed report with no collected
tests.


## Q53 — how does each FUNCTIONAL contract select its own kill-check test?

**Status:** RESOLVED (c), operator-selected 2026-10-08; SLICE5 STEP4 implements and tests the
all-path composition. Raised after source-reading the composition inputs.

### Source-verified facts

- `SliceRecord.test_paths` is a slice-level tuple. It lists one or more `TESTS:` paths, not a
  test per contract (`src/fa/inner_loop/plan_ids.py:149`).
- `parse_kill_directives(record)` returns `dict[contract_id, KillDirective]`, but neither the
  directive nor `SliceRecord.contracts` identifies a pytest nodeid (`slice_verification.py:440`).
- At question time, `_run_kill_check(directive, test_path, root)` accepted one path; STEP4 now
  accepts a sequence and `verify_slice` passes the complete `SliceRecord.test_paths` tuple. The
  schema still supplies no per-contract mapping, by the operator's explicit Q53(c) choice.
- Schema §1's prior decision explicitly deferred per-contract test attribution to I02, and only
  enforces a slice-level `TESTS:` line (`notes/artifact-schema-and-grammar.md:454`).

At question time, choosing the first `TESTS:` path, using every slice path for every contract,
or guessing from a function name was not equivalent under the then-current CT69. A mutation
for CT-A can make CT-B's unrelated test fail, producing a false `PROVEN`; Q53(c) explicitly
amends CT69 and accepts that attribution risk rather than concealing it.

| | (a) explicit per-contract nodeid | (b) enforced naming convention | (c) run all slice `TESTS:` paths per contract |
| :--- | :--- | :--- | :--- |
| mapping | `FUNCTIONAL` contract declares one exact pytest nodeid | test function name embeds the contract id; a collection check demands exactly one match | no mapping; every declared path is run under every mutation |
| changes | reopen/extend I01 grammar + planner/test-authoring prompts and precheck | add convention + precheck/collection oracle; contract bodies remain unchanged | amend CT69; cost becomes O(functional contracts × slice test set) |
| correctness | explicit and unambiguous | deterministic if the naming rule is strict and collision-checked | can falsely attribute another contract's failure to this producer |
| compatibility | touches the schema I01 currently owns | avoids new grammar but introduces an authoring convention | amend CT69; accepts weaker attribution without a new mapping |

**Operator decision: (c), 2026-10-08.** Run every path in the slice's `TESTS:` list for each
`FUNCTIONAL` contract's kill-check. Do not add a contract-to-test mapping or infer one from
names. CT69 is amended accordingly: the baseline and current nodeid capture stay scoped to the
slice's declared tests, while the kill phase runs that same complete path set under each
contract mutation. The operator accepts the resulting O(functional contracts × slice test
paths) cost and weaker attribution: one unrelated failing test can make a contract's
kill-check appear `PROVEN`. Preserve that risk in the implementation, tests and e2e register;
do not imply per-contract attribution.


## Q54 — how should CT83's `scripts/` producer be killed by the mutation overlay?

**Status: RESOLVED (b), 2026-10-08.** The operator selected a narrow, explicit `scripts/`
mutation root alongside `src/`; it does not widen mutmut's global `source_paths`. STEP5–STEP6
are complete after the real CT83 producer kill returned `PROVEN` through `verify_slice`.
Decision recorded in ledger E189; implementation evidence is E190.

### Measured blocker and source-verified facts

- SLICE4 originally copied only `workspace/src`, and `_overlay_target` rejected everything
  outside `overlay/src` (E187). The exact CT83 directive returned `ERROR` before running tests.
- `scripts/check_kill_directive_ownership.py` is a developer gate, not runtime package code:
  deployment imports runtime modules from `/opt/first-agent/src`; Dockerfile.fa copies only
  `scripts/fa-entrypoint.sh`; pyproject packages `src/fa`.
- `PYTHONPATH=<overlay-root>` by itself does not win when pytest imports
  `scripts.*` while the workspace root is on `sys.path`; a real subprocess experiment selected
  the workspace copy. The test process therefore needs a bootstrap before test collection, not
  merely a relaxed path check.
- The global mutmut config copies `scripts` only as test support (`also_copy`) and keeps mutation
  authority in src-only `source_paths`. That configuration remains unchanged.

### Selected architecture and acceptance conditions

- Keep two separate, allowlisted roots: required `src/` and optional `scripts/`. Copy each tree
  separately; a kill target must start under exactly one root, and resolved writes must remain
  inside that same root. Reject source-root symlinks, `..` traversal and per-file symlink escapes.
- Keep `tests/` outside the overlay. Do not copy the repository wholesale and do not widen
  mutmut's `source_paths`.
- Always prepend `<overlay>/src` for project imports. For a `scripts/` mutation, expose the
  overlay parent and load a small pytest bootstrap from the overlaid `src/`; it inserts the
  overlay parent before collection and verifies the exact target module's `__file__` is under
  `<overlay>/scripts`. A bootstrap/provenance failure is `ERROR`, never a kill.
- CT60–CT63 and the e2e register are amended. Exact import-provenance tests cover both roots;
  a real pytest subprocess proves the mutated scripts module wins while tests remain in the
  workspace. The CT83 kill now executes through `verify_slice` and returns `PROVEN`; STEP5/STEP6
  are ticked. SLICE6's separate SD-C `drive_session` composition-root proof remains mandatory
  for I02 completion.

The earlier option table and deployment research remain below as the rationale record; the
operator's explicit choice supersedes the old recommendation language.

## Q55 — should a blocking verify gate suppress eval?

**Status: RESOLVED by operator, 2026-10-08.** Always run the real eval stage after a successful
coder stage, even when the verifier reports a blocking result. The controller then reconciles
the actual eval report and typed verifier evidence. Do not use a synthetic harness report to
replace the evaluator or to short-circuit its call. If a caller omits `eval` or lists it before
`coder`, the workflow places one eval immediately after each coder stage. A non-zero coder
stage still fails fast; Q55 concerns successful coder stages only.

## Q56 — how does enforce-mode verification interact with eval routing?

**Status: RESOLVED by operator, 2026-10-08; Option 1 confirmed and clarified.** Eval's negative
routing authority is preserved: any eval non-complete route (`return_to_coder`,
`return_to_planner`, or `blocked`) remains the effective route. When eval says `complete`,
reconcile the verifier floor as follows:

- Observe mode records evidence but leaves routing to eval.
- In enforce mode, a **determinate** blocking verifier result routes to `return_to_coder`,
  subject to the existing bounded `repair_round` budget.
- In enforce mode, an **indeterminate** result (ERROR, harness fault, missing/unclassifiable
  evidence) routes to `blocked`; the gate itself does not start a repair loop for infrastructure
  uncertainty.
- In **enforce** mode, a blocking non-passing gate can never yield effective `complete`,
  terminal `DONE`, or process exit 0. Observe mode may complete by eval's decision while retaining
  the non-passing evidence for operator review.

The controller changes its effective route/status only; it preserves the actual model-authored
`EvalReport` and its route in `eval_report.json`. This is the operator's “gate as a floor, not a
ceiling”: verifier facts prevent a false pass but cannot erase a stricter eval decision.
Implementation and proof: SLICE6 CT72/CT73/CT75/CT77, C1 test
`tests/test_verify_gate_live.py::test_real_workflow_writes_verification_and_supplies_it_to_eval`.

## Q57 — what is the controller outcome after kill-directive admission rejects a plan?

**Status: RESOLVED by operator, 2026-10-09 — bounded pre-coder planner repair.** A determinate
`validate_kill_directives` diagnostic is supplied to the planner through a bounded repair loop in
the same workflow invocation, in **both linear and adaptive modes**. The controller revalidates
each revised plan and does not dispatch coder while any blocking diagnostic remains. Do not fail
immediately on a small, determinate schema/validator diagnostic when budget and planner are
available. Exhausted `max_replans`, missing planner when repair is needed, or indeterminate
validation fails closed as `blocked`; persist the diagnostic and final route. The repair budget is
shared with adaptive eval-driven planner replans. Linear receives admission repair only and keeps
its existing one-pass eval semantics. Eval is not called for a rejected pre-coder attempt: Q55
requires eval after a successful coder stage, and no coder stage has succeeded yet. Once a coder
stage succeeds, normal eval and Q55/Q56 reconciliation apply. The plan-revision transport itself
is resolved as the controller-owned candidate with same-path canonical promotion in Q58; runtime implementation and proof remain pending.

**Core negative proof (not yet implemented):** deleting the production call to
`validate_kill_directives` permits coder dispatch for the malformed plan and makes the real-
composition C1 test fail. `tests/test_verify_gate_live.py` already proves verify/eval composition,
but not admission. The planned extension must prove successful repair, both linear/adaptive
callers, budget exhaustion, and that no coder/eval runs before revalidation passes.


## Q58 — what narrow plan-revision interface should Q57 use?

**Status: RESOLVED by operator, 2026-10-09 — controller-owned candidate with physical same-path promotion.** The operator accepted option 1 and added the requirement that a passing repair replaces the original canonical increment file in place. This resolves the transport choice only; runtime implementation and proof remain pending.

**Accepted behavior.** The current planner can write `knowledge/research/` and `.fa/`, not canonical `worklogs/...` (`src/fa/inner_loop/profiles.py:132-145`), so the repair planner must not receive general write access to the increment. The controller creates one draft per attempt under `.fa/admission/<run_id>/`; the real planner registry gets a writer scoped to that exact draft only. The active `--plan`, sibling paths, traversal, absolute paths, and symlink escapes are denied.

For an increment run, the exact supplied `--plan` file under `worklogs/planning-topology-and-executable-contracts-loop/increments/` is the sole canonical current plan. The `.fa` draft is staging only. The controller re-reads it, runs `precheck` and `validate_kill_directives`, serializes controller promotions for that target, then rechecks the original-plan hash. Only a passing, unchanged candidate is written to a hidden, uniquely named non-plan temporary sibling of the canonical file, flushed, and atomically installed with `os.replace` at the **same path**. Readers see either the complete old file or the complete repaired file—never a partial write and never a second active-plan location. Clean the temporary sibling on failure and remove the staging draft after promotion; preserve attempt/diagnostic/target/source/candidate/promoted hashes and final route in `admission.json`. The hash/lock are concurrency protection only, not a review approval marker.

A failed validator remains eligible for another bounded planner attempt. Empty/unreadable input, indeterminate validation, missing/failed writer, source-hash mismatch, or failed replacement blocks before coder/eval; any failure before replacement leaves the original plan byte-identical. Do not broaden the planner allowlist to `worklogs/` or silently fall back to direct writes. For live E2E, use a disposable workspace copy at the same relative increments path and prove that exact test `--plan` is replaced; never mutate the tracked source plan during the live test.

**Alternatives considered, not selected.** (2) Letting the planner write the active file would expose canonical plans to partial or invalid writes and require a broader allowlist. (3) Returning the full plan as structured provider output would require a new response schema and controller transport path that do not exist.

**Implementation status (E273, 2026-10-23).** The authority side of the promotion exists and is locally proved:
`publication.publish_plan` → `WorkspaceAuthority.publish_plan` (same-path replace is the irreversible point,
then revision/pointer forward, no rollback; see increment-03's E273 result). What the required proof above still
needs is the **controller leg**: `_promote_validated_plan` continues to call `publish_plan_buffer` until the
dispatcher route exists (SLICE1 STEP3), and that call is to be *moved*, not duplicated — the transport is
deleted in the same change that routes it, so exactly one writer ever owns the canonical plan. Until then the
two paths fail closed against each other: the authority refuses a seal whose plan bytes moved outside it
(`_validate_plan_boundary`), and a later authority forward step refuses a canonical tree that is not the
committed revision.

**Required proof before runtime completion.** Real `run_workflow` → `_cmd_run` → `drive_session` C1 path with only `ProviderChain.request` mocked; prove both validators pass before the exact canonical file's bytes change, subsequent coder reads that same path, and no alternate active path is used. Invalid/stale candidates and promotion errors leave the source byte-identical and reach `blocked` with no coder/eval. C3 denies exact-target escape, `..`, absolute path, and symlink writes. Deleting the scoped-writer or `_promote_validated_plan` producer call makes its named test fail. Tests stay outside Q54 mutation roots; a live-host E2E case covers the producer.

---

## Q59 — Is chat escalation advisory, or must complex tasks be forced through `invoke_workflow`?

**Status: RESOLVED — operator 2026-10-16 (E231).** Advisory/manual invocation PLUS the existing
experimental mid-chat prompt-injected invoke suggestion. No new --require-workflow, router-only
mode or production success guard. Preserve/verify expansion/routing and current injection plumbing;
prompt compliance is not a guarantee. Mandatory managed execution remains independent of workflow
choice. Current contract: I03 spec §§7/7.0/9; source cli.py:2408–2437, expansion.py:10–23.

### Historical proposals and source analysis (superseded by E231 above)

**E230 current finalization:** still OPEN, not ratified by plan review. Exact current proposal and
binary oracles are in I03 spec §§7/7.1/9; current source is1132eee, not the old d910 anchors below.
Q63's package owner is now I03 SLICE6 (former I02 SLICE7). See E230 findings before deciding.

**2026-10-15 review:** I03 spec §7 proposes an explicit --require-workflow router-only route,
without changing ordinary advisory chat. Exact guarantee/name remains unratified; SLICE5 STEP1
requires disposition, not a prompt-compliance claim.

**Status: OPEN on enforcement strength; the user-experience intent is clarified.** Operator
intent, 2026-10-14: chat is the everyday front door for any task. A deterministic scope/escalation
module should inject a recommendation to use `invoke_workflow` when work looks complex, and the
operator may also ask chat to invoke it manually. Do not replace ordinary chat with a mandatory
workflow-first entrypoint by default.

**What already exists.** `_resolve_scope_point` computes a deterministic estimate before the first
provider call (`src/fa/cli.py:2293-2299`); `_publish_scope_estimate` sends it via the non-cacheable
`turn_context` (`cli.py:2110-2165`, `2426`); `CHAT_SYSTEM_PROMPT` tells chat to call
`invoke_workflow` on `workflow_linear` (`src/fa/inner_loop/prompt.py:1004-1023`); and the live
chat registry registers that tool when workflow context exists (`src/fa/cli.py:1772-1803`). The
manual/advisory path is therefore already represented in code.

**Important enforcement gap.** The gate defaults off (`runtime_limits.py:154-159`). If enabled,
`WITHHELD_WRITE_TOOLS` removes `fs_write_file`, `fs_edit_file`, and `fs_spawn_subagent`, but not
`fs_run_bash` (`src/fa/inner_loop/routing.py:72-78`). The Bash hook uses a command classifier and
`allow_general_write=True`; its own source says `../` writes are not confined (`hooks/builtin.py:99-145`).
So the current prompt suggestion is advisory, and even the optional gate is not a complete
write-capability boundary. `invoke_workflow` itself takes no PlanRef path, which is appropriate;
its task/context decision is tracked in Q66.

**Options.**
- **(a) Advisory default + manual invoke (recommended).** Keep general chat and its current
  scope hint. Treat the hint as a recommendation, not a guarantee. Preserve an explicit operator
  phrase/tool-call path for “use the workflow.” No new entrypoint is required for ordinary use.
- **(b) Strict automatic escalation.** When a deterministic high-confidence policy selects
  workflow, build a read/search/context + `invoke_workflow` registry before dispatch and remove
  *all* direct mutation routes, including shell. This needs a complete gate and a policy for
  false positives/negatives; the current optional gate is insufficient.
- **(c) Explicit required-workflow mode.** Keep general chat unchanged, but offer an explicit
  command/UI mode that guarantees the workflow route when the operator requests it. This is the
  strongest way to honor a must-use instruction without trusting prompt compliance.

**Recommendation.** Use (a) as the default, with (c) as the deterministic override if “must use
workflow” needs a guarantee. Keep (b) opt-in until routing evidence justifies it; the deferred
calibration criterion is not a reason to claim estimator accuracy. Preserve Q55/Q56 in every
nested run. The unresolved operator choice is whether manual “use workflow” needs a guaranteed
controller route or whether model-mediated tool selection is acceptable.

---

## Q60 — Is the proposed CT96 planner-managed selection/bootstrap protocol approved?

**Status: RESOLVED BY DELEGATED ENGINEERING DESIGN — operator 2026-10-16 (E231).** The operator
instructed source verification/reuse, then wise robust maintainable design; this was NOT blanket
ratification of the earlier proposal. Source-verified selected solution is I03 spec §§7/7.0/7.1:
one existing workflow/admission/repair machine, existing child allocator and PlannerDispatch,
strict stable-pair choice/clarification, deterministic fixed-three-file bootstrap, explicit v2
acquisition cross-fields with unchanged v1 readers. Existing reserved enums are not producers.
Current pr_prepare producer is tools/prepare_pr.py, not a nonexistent tools/pr_prepare.py. Optional
private entry/capability is not a public boolean missing-plan bypass. Plan-only delegation here;
construction/proof/deployment not performed or approved by this resolution.

### Historical proposals and source analysis (superseded by E231 above)

**E230 current finalization:** still OPEN, not ratified by plan review. Exact current proposal and
binary oracles are in I03 spec §§7/7.1/9; current source is1132eee, not the old d910 anchors below.
Q63's package owner is now I03 SLICE6 (former I02 SLICE7). See E230 findings before deciding.

**2026-10-15 review:** [I03 spec §7](i03-execution-workspace-spec-2026-10-15.md#7-nested-acquisition-and-q66--source-grounded-design-e231)
proposes exact stable project_slug/increment_id selection, clarification and controller-rendered
bundle, replacing the old path-shaped recommendation only if approved. Existing linkage/status
handling and managed admission v2 are explicit remaining schema dispositions; no option ratified.

**Status: OPEN. CT96 remains recommended, not operator-ratified.** Operator leans toward option
(a), 2026-10-14, and asks whether it remains sound; the decision is not yet ratified. This gates
the chat acquisition path, not the already separate verification-runner work.

The current proposal uses one closed typed result from the nested initial planner:
`PlanSelection{kind: SELECT_EXISTING, workspace_relative_path}` or
`ProjectBootstrapBundle{kind: BOOTSTRAP_NEW_PROJECT, project_slug, increment_slug,
roadmap_body, increment_body}`. No PlanRef path is added to the outer chat schema; no free-form
file map, raw ledger entries, or destination is accepted. The controller renders roadmap/I01
metadata and the append-only ledger header, performs shared admission, stages under private
`.fa/admission/<run_id>/`, then publishes a new `worklogs/<slug>/` only with an atomic no-clobber
rename. Full roadmap/ledger model files would require a minimal versioned content validator;
path/size checks alone are not content validation, and the production `parse_ledger` remains I04
work.

**Options.** (a) Approve CT96's controller-rendered, typed bundle and stated caps/no-clobber rules;
(b) accept model-supplied complete artifacts but require the minimal I02 bootstrap-content
validator before publication; or (c) defer new-project bootstrap and support only existing-plan
selection for now. Option (c) does not satisfy the complete target behavior.

**Production-grade refinement (recommended, not yet operator-approved).** Make the existing-plan
selection return stable identifiers such as `project_slug` and `increment_id`, then have the
controller construct and validate the canonical relative path; do not let the planner supply even
a constrained filesystem path. Add a closed `NEEDS_CLARIFICATION` result so ambiguous project
matches or insufficient context return to chat instead of silently creating a duplicate project.
No-clobber publication remains the final race guard, not a reason to choose bootstrap on ambiguity.

**Recommendation: (a).** Confirm the exact choice shape, metadata/status rendering, required
roadmap sections/I01 row, empty generated ledger, size caps, no-follow staging, no-clobber
publication, and post-publication write-failure policy in CT96. Treat directory rename as an
irreversible publish: if later PlanRef/admission persistence fails, retain valid published files,
block before the next provider stage, and do not auto-delete/overwrite them. All of this remains a
recommendation until the operator answers.

---

## Q61 — What PlanRef integrity boundary is acceptable for CT97's nested in-process topology?

**Current design direction / owner (E197–E201):** foundation I03 uses trusted controller plus
Docker-backed cells/private host supervisor, exclusive workspace writer/private views and fenced
sealed publication. PTY stays; do not adopt an old option that removes arbitrary shell or treats
in-process hooks/read-only mounts as the complete boundary. Earlier alternatives below are
historical rationale, not permission to bypass this direction. Exact deployment contracts and
negative proof remain pending; this note does not mark Q61 runtime/security evidence complete.

**Status: RESOLVED — operator selected option (a), 2026-11-02.** The trust boundary is the trusted
controller in the parent plus one shared, disposable, per-stage OS-sandboxed copy-on-write workspace for
all provider write surfaces, followed by trusted validated import. This resolves the architecture choice;
it does not close CT97 implementation, runtime security evidence, or any S4P1/W0/W1 acceptance row.

**Scope clarification (2026-11-02).** `invoke_workflow` is registered for the `chat` role only. The
`acquisition_unavailable` check applies to the child pipeline's requested roles (default
`planner,coder,eval`); it does not mean coder should receive or invoke `invoke_workflow`. Direct
`fa workflow` remains a separate manual CLI path and is not changed by this decision.

**Source-confirmed topology and exposure.** `invoke_workflow` synchronously calls
`run_workflow` (`src/fa/inner_loop/tools/workflow_tool.py:463-484`); its stage callback is
`_cmd_run` (`src/fa/cli.py:1687-1706`), which calls `drive_session` (`src/fa/cli.py:2408`). A
blanket read-only mount on that current process/call stack would also restrict the trusted
controller's allowed candidate/bootstrap publication and same-path promotion. `SandboxHook` only
path-checks `fs_read_file`/`fs_write_file`, defaults `allow_general_write=True`, and routes
`fs_spawn_subagent` through a bash classifier that explicitly does not confine subagents
(`src/fa/inner_loop/hooks/builtin.py:31-36, 99-145`). `fs_edit_file` writes directly after
workspace-path resolution and generic blackboard checks, with no PlanRef identity rule
(`src/fa/inner_loop/tools/edit_file.py:104-110, 137-155`). Bash may use a persistent PTY or
subprocess fallback, and `_run_stage` verifies a pre-coder snapshot after dispatch rather than
preventing mutation (`src/fa/inner_loop/tools/run_bash.py:152-165, 219-235`;
`src/fa/inner_loop/workflow_controller.py:1053-1081, 1093-1104`).

**Options.** (a) Keep the trusted controller in the parent and give all provider write-capable
surfaces one shared per-stage OS-sandboxed copy-on-write workspace with a validated import step; or
(b) refactor nested orchestration across a trusted controller/worker IPC boundary so provider
stages run in isolated workers with mediated filesystem changes. Either way, current subagents stay
absent; future exposure requires inherited isolation. A post-hoc hash alone or a path-only
read-only bind is insufficient.

**Operator scope clarification, 2026-10-14:** subagents are planned but off by default; the current
`implementer`/coder profile does not include `fs_spawn_subagent`, and the tool's feature flag
defaults off (`profiles.py:117-131`; `tools/spawn_subagent.py:139-154`). I02 need not build child
isolation now. Its current proof should assert the workflow-stage registry omits subagents. Any
future flag/profile change that exposes them must require the same boundary to propagate to every
child before enablement.

**Simplest robust recommendation (still needs operator ratification):** keep the trusted controller
and promotion path in the parent process; do not refactor all workflow orchestration to IPC. Give
each provider stage one shared, disposable writable view used by *all* provider write-capable
surfaces (`fs_write_file`, `fs_edit_file`, `fs_run_bash`/PTY, and descendants), so tools see one
consistent stage state. Seed it from an explicit snapshot of the actual current worktree—not a
clean checkout—including staged/unstaged and untracked project changes; exclude secrets/caches by
policy and expose needed toolchains read-only. Keep the host canonical PlanRef, `.fa/admission/`,
`.git`, credentials, and controller state outside the writable view. At stage end, have the trusted
parent validate and import only approved workspace diffs; reject protected paths, symlink/hard-link
and special-file tricks, path escapes, and any destination whose host version changed since the
snapshot. This preserves existing user edits and turns concurrent changes into explicit conflicts
instead of overwrites. The controller alone performs candidate validation and same-path promotion.
If full snapshot/view/import cannot be provided, fail closed before coder or defer general shell and
provide a narrowly scoped test runner; do not mix host-direct file tools with a stale shell snapshot
or silently fall back to today's unsandboxed PTY/subprocess path. Hash checks after the stage are
detection, not the security boundary. Preserve ordinary source edits and Q55's real eval after a
successful coder dispatch; a detected PlanRef mismatch is indeterminate and cannot yield terminal
success.

**Remaining risks/tests:** indirect prompt injection through repository content, symlink and
hard-link aliases, rename/replace races, persistent PTY state, subprocess descendants, timeout
cleanup, concurrent workflow runs, and unexpected writable mounts/caches. C1/C3 must start from a
dirty checkout with staged, unstaged, and untracked sentinels; prove all pre-existing state is
visible and preserved, allowed source edits return as unstaged changes, and a concurrent host edit
causes a conflict instead of clobber. Also prove PlanRef/control-plane protection, shell attempts
through direct redirection/Python/symlink/hard-link/child-process routes, fail-closed sandbox
startup, unchanged host PlanRef bytes, successful trusted promotion, and Q55 eval ordering. A
path-only read-only bind or post-hoc hash alone is insufficient. The operator must ratify the
boundary before CT97 implementation; do not claim it closed from plan text.

---

## Q62 — What closed validator/rule vocabulary should CT92 persist?

**2026-10-15 implementation-spec update:** [exact explicit v1 table](i02-explicit-admission-spec-2026-10-15.md#3-exact-admissionjson-v1--ct92--q62-implementation-specification)
now supplies the missing values, initial EXPLICIT_INPUT and strict checks. The historical Status
line below is unchanged; implementation/read-write tests and review are still absent. Its statement
that the values are missing describes the earlier review, not the current specification. No Q59,
Q60 or Q63 policy ratification follows.

**Status: OPEN as an implementation-plan gap; no operator-policy choice is implied.** CT92 makes
the diagnostic object exact and requires closed rule vocabularies, but the earlier wording left
non-`precheck`/`kill-directives` rules to a versioned `AdmissionRule` enum without listing concrete
`plan-ref`, `bootstrap`, `promotion`, and `artifact-io` values. This review updates CT92's preferred
representation to per-validator `rule` tables; those v1 values are still missing. The diagnostic
writer cannot be schema-exact or tested against unknown values until the mapping exists.

**Options.** (a) Publish the v1 per-validator table in CT92 now, with compatibility/versioning
rules; or (b) make its publication a required first CT92 substep before writing the schema or
controller. The recommendation below favors (b) to avoid expanding the plan with an unratified
vocabulary.

**Senior review, 2026-10-14.** A closed machine-readable rule vocabulary is worth implementing:
these diagnostics are an audit trail and a controller contract, and arbitrary provider/model text
must never become a persisted rule or control decision. But a single large `AdmissionRule` enum
that duplicates every validator's rule list is not the simplest design.

**Recommendation:** keep CT92's exact versioned artifact and existing `validator`/`rule` fields,
with stable validator-specific `rule` codes. Reuse the existing closed rule IDs for `precheck`
and `kill-directives`; define small sets for `plan-ref`, `bootstrap`, `promotion`, and
`artifact-io` (for example, `validator=plan-ref, rule=path-escape`;
`validator=promotion, rule=source-changed`; `validator=artifact-io, rule=append-failed`). The
validator field already provides the namespace. Validate the code against the allowed set for that
validator at write/read time; unknown pairs fail closed. Persist no free-form diagnostic message or source snippet.
Keep `admission.json` focused on admission attempts, route and hashes; workflow/session evidence
remains the source of truth for actual provider dispatch facts. This makes Q62 a specification
prerequisite to CT92, not a separate product-policy gate. The implementation author can add the
small v1 code table as the first CT92 substep.

---

## Q63 — Is the proposed live E2E result vocabulary approved?

**Status: RESOLVED — operator 2026-10-16 (E231).** Exactly `NOT RUN | PASS | FAIL | BLOCKED`.
Every state permits optional short reasoning/commentary; no extra hardcoded reason variants and
no required BLOCKED reason. Artifact field `commentary` is optional in every state, ≤512 UTF-8
bytes, single line, redacted, never control flow. I03 SLICE6 owns actual artifact/test changes;
append-only attempts and independent live-result ownership remain. Existing roadmap/increment/
CT vocabularies and generic READY are not changed. See artifact schema §6 and I03 spec §9.

### Historical proposals and source analysis (superseded by E231 above)

**E230 current finalization:** still OPEN, not ratified by plan review. Exact current proposal and
binary oracles are in I03 spec §§7/7.1/9; current source is1132eee, not the old d910 anchors below.
Q63's package owner is now I03 SLICE6 (former I02 SLICE7). See E230 findings before deciding.

**Status: OPEN. Non-blocking for core runtime coding; settle before SLICE7 finalizes the live-case
index/run sheet.** The plan recommends `NOT RUN | PASS | FAIL | BLOCKED` with append-only attempt
evidence and keeps the live-result assignment with the operator or an LLM evaluating collected
evidence. The actor-ownership rule is standing; the exact enum remains a recommendation in CT88
and the handoff note.

**Senior review, 2026-10-14.** I agree: this is a good, simple closed vocabulary. `NOT RUN` is
the initial/no-attempt state; `PASS`, `FAIL`, and `BLOCKED` are reviewed outcomes. I would keep
those four values and add one small schema invariant: `BLOCKED` must carry a required reason code
(e.g. `DEPLOYMENT_UNAVAILABLE`, `SAFETY_STOP`, `EVIDENCE_MISSING`), so it cannot become a vague
skip. A blocked case is not a product failure and cannot count as PASS. Keep append-only attempts,
local proof separate from host judgment, and require deployed SHA/run ID/command/exit/observable/
evidence references for any assigned result. This is an assistant recommendation, not operator
ratification; the entry stays open until the exact vocabulary and reason-code rule are explicitly
resolved.

---

## Q64 — Who owns the deferred calibration criterion and when must it be promoted?

**Status: DEFERRED TO I06 by operator, 2026-10-14.** The 20-slice/≥95% criterion remains outside
I02 and is not a blocker for I02 coding or shipping. Define the detailed owner, trigger, and
non-overlapping calibration/held-out regression sets in I06 before I06 makes a calibrated
reliability claim or changes gate policy. The earlier proposed trigger (before the first such
claim or policy change) is a planning recommendation, not an additional I02 requirement.


---

## Q65 — Does the current I01 source-position change resolve Q45, or must it be reverted?

**Status: RESOLVED (a) by operator, 2026-10-14.** The operator explicitly ratifies the scope
expansion and confirms it had already been decided. Keep the single-source-of-truth design in
I01 and CT78–CT80: `SliceRecord.start_line`, `contract_lines`, and `PlanIds.contract_line()` carry
declaration positions; the I02 duplicate locator stays removed. This is a decision record, not
runtime/test evidence. Q45 is updated to match; see ledger E196.

## Q66 — Should `invoke_workflow` expose an explicit context field?

**Status: RESOLVED for the public tool schema; runtime propagation proof remains OPEN.** Operator
clarification, 2026-10-14: no extra `context` field is wanted. The nested workflow should inherit
the current chat context and supply it to the planner role as input tokens alongside that role's
own prompt and skills. Keep `task` as the explicit user-requested goal; context is controller-
managed invocation state, not another model-authored wire field.

**Current source-confirmed gap.** `INVOKE_WORKFLOW_SCHEMA` accepts `task`, `mode`, `roles`, and
budgets, with no `context` property (`src/fa/inner_loop/tools/workflow_tool.py:164-196`); that is
consistent with the operator decision. But `_resolve_handoff_task` currently adds only live
read/write/search-path facts to the task (`:331-375`). `WorkflowInvocationContext.session_context`
is the persistent session identity/workspace/database/manifest object, not the chat transcript
(`src/fa/session/manager.py:52-57`). The handler passes `task=handoff_task` plus that metadata to
`run_workflow` (`workflow_tool.py:463-484`); the nested `drive_session` reconstructs history from
the child run log, not the parent conversation (`src/fa/inner_loop/coder_loop.py:562-630`). Thus
the public schema decision is resolved, but the intended inherited-context behavior is not
currently demonstrated by source.

**Implementation recommendation.** At the moment of tool invocation, capture a bounded,
immutable snapshot of the parent conversation after the parent's compaction/summary boundary and
pass it through the existing live controller context-provider—never an additional `invoke_workflow`
parameter. Compose `per_role_task["planner"]` for initial user-task input, not SYSTEM `turn_context`;
the nested planner uses its own role prompt and skill instructions. Do not copy the outer chat system prompt, tool
schema, or unrelated tool catalog; do not duplicate prompt/skill tokens. Budget/compact the
inherited context explicitly, preserve current user constraints and decisions, label repository
and tool output as untrusted data, and record actual child input-token usage. Apply the existing
secret-redaction/data-egress policy before crossing provider chains: never inherit credential
values, auth metadata, or raw secrets, and do not write transcript content into workflow artifacts;
record only the allowed control references/counts there. Ordinary child conversation/event/debug
logs remain allowed under existing credential redaction and debug opt-in; no global suppression,
mandatory transcript-age GC or advanced privacy service is introduced. Scope the full initial
input to initial dispatch; repair/replan use distilled goal/failure/ref packets, not repeated history.

**Required proof.** The real outer-chat → `invoke_workflow` → nested planner C1 test must show
that a prior user constraint and relevant assistant/tool context reach the first planner request,
that a synthetic credential sentinel is omitted/redacted under the egress policy, that the
planner's own prompt/skills are present, that no new context field is in the tool schema, and that
existing size bounds hold, and no raw transcript enters admission/control schemas. Ordinary child
logs are allowed with credential redaction; prove initial-versus-distilled-replan separation. Do not
treat path-only session facts as proof of transcript inheritance.

### Current scoped readiness queue as of 2026-10-15

- **Before coding the requested chat → `invoke_workflow` target path:** settle Q59's advisory vs
  guaranteed-route boundary, Q60's typed selection/bootstrap protocol, and Q61's PlanRef integrity
  mechanism. Q66's public API decision is resolved (no extra tool field), but its inherited-context
  plumbing and C1 proof remain unimplemented. Q57/Q58 settle repair and same-path transport as
  decisions only; they do not implement them.
- **Before the CT92 admission writer:** implement/test the closed table now supplied in the
  explicit-admission spec §3; do not claim its implementation from this document update.
  Q43 remains open: I02 preserves current strict accessor semantics and only extractor-origin
  IDs. A proposed leniency/semantic change needs explicit disposition, not implicit adoption. Q45 is now resolved (option B) by Q65; keep the approved source-position
  fields and do not revert them.
- **Before foundation I03 final-group E2E package finalization (former I02 SLICE7):** ratify Q63's four-state vocabulary and decide whether
  `BLOCKED` requires the recommended reason code; this does not block core runtime coding.
- **Deferred outside I02:** Q64 is assigned to I06 by operator instruction; do not restore the
  20-slice/≥95% criterion as an I02 gate.
- Q59–Q63 remain decision/specification questions; Q64 is deferred, Q65 is resolved, and Q66's
  API decision is resolved while runtime proof remains. Current production source still lacks
  admission, planner-managed selection/bootstrap, inherited chat-context propagation, and the CT97
  PlanRef boundary; see retained I02 local DoD and foundation I03 conditional briefs/migration bank.

I02 does not wait for the successful nested path, OS boundary or deployed-host evidence; it still
requires retained explicit Q57/Q58 implementation, negative unavailable managed-path proof, Q62/Q43
disposition where used, full-suite failure identities and independent/operator review. Nothing
in this owner edit closes those proofs. Old tracker/L2-eval references follow the deferred successor.


---

## Q67 — How is the first eval-requested replan represented before candidate validation?

**Status: RESOLVED (a) — explicit operator selection, 2026-10-16.** Keep v1 canonical
ADMITTED during the first eval-only replan, durably persist unchanged history before provider,
reserve shared credit, then record the actual candidate outcome. Only real FAIL permits RETRY;
no coder until validation, publication and final durable admission. No pending schema or synthetic
FAIL. E211 implements the local composition; this disposition alone is not contract acceptance.
The proposal and source measurements below are historical, from before approval.

**Source-verified starting point:** `4b6e3625e63fe00d4ed5f6a6830bb94ec52908bd`.
`run_workflow` still reads explicit PlanRef without invoking the new admission helpers;
`_run_adaptive_replan` still dispatches the ordinary planner/coder/eval sequence.
The next implementation must use scoped candidates, shared planner credit, durable barriers,
actual candidate validation and no fabricated diagnostics.

**Unspecified lifecycle point.** An eval `return_to_planner` can request a revision of a
canonical plan whose structural/kill validators still PASS. Explicit-admission spec §3 and
`admission_schema.py::_record_attempt` allow RETRY only for DIAGNOSTICS with a real FAIL.
`_record_attempt_hashes` allows EVAL_REPLAN/ADMITTED only after a nonnull promoted hash.
Thus neither PASS/RETRY nor an unpromoted EVAL_REPLAN/PASS/ADMITTED attempt can represent the
first pending planner dispatch. The spec explicitly requires pre-dispatch RETRY for determinate
validation failure (§2), but does not explicitly state whether an eval-only first replan retains
the previous canonical ADMITTED record or requires a new pending-dispatch representation.
This is not a reason to weaken existing schema checks or manufacture a validator failure.

**Reproduced C0 schema probe (not product proof):** an exact initial EXPLICIT_INPUT/PASS/ADMITTED
record is accepted. Appending EVAL_REPLAN/PASS/RETRY with candidate/promoted null is rejected;
appending EVAL_REPLAN/PASS/ADMITTED with those nulls is also rejected. Keeping the previous
ADMITTED record unchanged is accepted. All checks use the real `validate_admission_record`,
not a fake validator. `write_admission_record` already supports `attempt=None` for a durable
unchanged-history write. No source or test code changed for this probe.

**Options:**

- **(a) Keep v1 and canonical-state meaning (recommended).** ADMITTED describes the currently
  accepted canonical snapshot, not permission to run coder while a revision is pending. Before
  the first eval-requested replan, recheck canonical identity and durably persist the unchanged
  ADMITTED record; reserve shared planner credit before provider dispatch. After the scoped
  planner returns, append its actual EVAL_REPLAN candidate validation/promotion or BLOCKED
  outcome. Only a determinate candidate FAIL gets a RETRY entry before another planner attempt.
  No new schema values/fields; no synthetic FAIL, premature promoted hash, coder/T0 dispatch or
  success inferred from the retained ADMITTED status. The controller's pending revision blocks
  coder until final validation/publication/durable admission succeeds. Admission/write/provider
  uncertainty remains fail-closed; existing Q55 post-coder eval obligations are preserved.
- **(b) Add explicit pending-dispatch evidence.** Require a durable new attempt before even the
  first eval-only revision provider. Specify/version a pending state or separate dispatch event
  and its cross-field/old-record compatibility rules before implementation. Do not silently
  broaden v1 RETRY or overload DIAGNOSTICS with model eval text. Exact schema extension needs
  separate disposition; choosing this direction alone does not ratify an unspecified shape.

**Question:** approve (a), or require (b) and settle the versioned shape first?
CT74/CT87/CT91/CT92/CT94/CT95 and GAP-06/10/12/15 remain open. This question does not reopen
Q57 bounded repair, Q58 same-path publication, Q55 actual eval or I03 ownership decisions.


## Q68 — Which recovered tool errors invalidate a scoped planner attempt?

**Status: RESOLVED (a) — explicit operator selection, 2026-10-16.** Raised during E211 source
review, before checkpointing the new scoped-outcome projection. Applies only to
ADMISSION_REPAIR/EVAL_REPLAN, not ordinary planning.

**Measured:** the initial E211 consumer rejected every trusted tool error accumulated across a
session, even a failed read/list/search followed by successful preparation/publication. Q57/Q58
require fail-closed preparation/publication, but did not explicitly ratify this broader rejection.
The session loop can project trusted paired call/result names without parsing model prose.

**Options offered:** (a) publication failures only (recommended); (b) any tool failure, including
subsequently recovered read/list/search errors. The operator explicitly selected **(a)**.

**Approved rule:** a result error from the actual publication tools `fs_write_file` or
`pr_prepare` invalidates that scoped attempt even if a later call succeeds. Recoverable
read/list/search result errors alone do not. Missing outcome/nonzero terminal outcome still
fails; actual candidate validation, successful preparation, same-path publication and durable
admission remain mandatory. This is not permission to ignore final candidate/IO/guard failures.
`SessionOutcome.failed_tools` carries only trusted tool names; no raw error bodies/model text are
persisted into admission control fields. Ordinary planner exit behavior is unchanged.

E211 C1 pairs exercise real failed `fs_read_file` versus failed `pr_prepare`, followed by real
successful preparation/write, in both observe/enforce. Mutation checks must kill both removal of
prepare-error consumption and reintroduction of the blanket tool-error rule. No security-boundary
or complete SLICE6 claim follows from these local tests.


## Q69 — Keep the original C1 public test without recursive whole-bank verification?

**Status: RESOLVED — explicit operator approval, 2026-10-16.** The old constructed C1 plan
selected its own outer public file for each internal kill. The unfiltered 481-case baseline had
not completed after ten minutes; selected subsets were not normative acceptance evidence.

Approved: factor a nonrecursive constructed-plan leaf into `tests/fixtures/i02_gate_probe.py`,
with a deterministic test subject in `tests/fixtures/i02_gate_subject.py`. The outer C1 retains
real controller→CLI→session/provider-IO-only composition, persisted artifacts, once-only global
command, independent slice attribution, exact eval evidence and all nine internal producer kills.
Its constructed plan selects the whole leaf file; the leaf's own plan has no FUNCTIONAL kills.
Other `_plan_text` callers keep the original default TESTS path. This is fixture factoring, not a
runtime recursion-marker change, skipped C1, fabricated PROVEN or contract→test mapping.

All **16** retained SLICE6 normative mutations still run the **complete outer public test file**.
A completed unmutated full-file baseline precedes those runs. Collection, runner, timeout and
infrastructure errors cannot count as kills. Approval permits the construction; measured results
and remaining acceptance obligations are recorded in the E212 continuation of the E211 note.


## Q70 — Which nested requests fail when managed plan acquisition is unavailable?

**Status: RESOLVED — operator selected coder-containing-only guard, 2026-10-16.** Blocking all
nested workflows was offered but NOT selected: it would unnecessarily remove planner/eval-only
delegation. Missing managed acquisition must fail closed for coder-containing requests, including
the default planner,coder,eval roles, before child identity allocation, handoff/artifacts/provider.
Use the structured `acquisition_unavailable` tool error; do not guess a plan or add a public
PlanRef field/stub acquisition backend.

Otherwise-valid planner/eval-only delegation remains supported. In a session-bound invocation,
allocate the actual child RunContext through existing SessionManager authority in the same
session/workspace/DB; never forward the parent's differently-bound RunContext as the child.
Missing/mismatched parent authority and allocation failure remain fail-closed. Legacy invocations
without either session/run context keep their existing unbound behavior; this does not establish
I03 managed acquisition, cross-session reuse, parallel orchestration or OS isolation.

C0 covers repeated refusal without consuming the next child identity and invalid noncoder request
preconditions before allocation. C1 exercises the normal CLI/chat registry path with only provider
IO mocked: default/coder refusal and planner, planner/eval, eval delegation; inspect actual child
binding, provider sequence, session rows, global history and absent fabricated admission. E212
records actual results and producer-removal sensitivity separately from policy approval.


## Q71 — May the documentation guard distinguish recorded alias-denial evidence from obsolete workspace claims?

**Status: RESOLVED direction — custom operator authorization, 2026-10-16.**
The operator replied: “implement suiting production-grade wise design. robust and maintainable policy”.
This delegates design selection, not selection of the proposed exact-path exception below.

**Adopted construction:** reject retired local/shared/object-sharing clone recipes and the existing
one-session/container-lifecycle assertions, not mere filesystem mechanism names. Security denial,
risk discussion and negative-test evidence may mention alias mechanisms in any document. Retain
existing historical exceptions without adding a project-path exception. The deterministic detector
recognizes unsafe clone flags with intervening flags/continued lines; explicitly safe no-local/no-
sharing options are not matched. This is a bounded lexical recipe/claim guard, not an NLP claim
classifier or execution-isolation guarantee. Two-sided C0 controls are required. No evidence
rewrite, skip, baseline waiver or runtime policy relaxation. The proposal below is historical.

Review checkpoint:
`c881621d53026c21cf4cecbd037ae1361bbfae92`. No production or test-oracle change is authorized
by recording this question. Q69/Q70 remain resolved; this does not reopen runtime acquisition,
execution isolation, verifier attribution or supported noncoder delegation.

**Source-verified conflict:** `tests/test_deploy_scripts.py:847–879` scans every Markdown file
for five literal phrases. Its second phrase (`stale_phrases[1]`, the unhyphenated filesystem-link
term) is rejected regardless of whether a document asserts an obsolete capability or records
actual denial/remaining risk. The existing finite path/prefix exceptions omit these three files:

1. `worklogs/planning-topology-and-executable-contracts-loop/ledger.md:2259–2261`:
   append-only EVIDENCE records actual descriptor-origin rejection, not support for unsafe cloning.
2. `notes/e2e-live-verification-register.md:400,406,598,605–607,749–750,965` under that project:
   alias-denial test obligations and actual writer-error evidence; local proof is explicitly not
   deployed isolation acceptance.
3. `notes/execution-foundation-scope-reduction-and-reuse-audit-2026-10-15.md:185–187`:
   explicitly warns that leaf no-follow does not establish ancestor/alias safety.

Fresh command (supported Python/locked environment):

```bash
uv run --frozen --no-sync pytest tests/test_deploy_scripts.py::test_workspace_stale_claims_are_confined_to_historical_evidence -q --tb=short
```

Actual: **1 failed in 0.54s**, rc1; the three paths above are the complete reported violation set.
This is the same candidate-only failure recorded in E213, not a new product regression. No skip,
waiver, added allowlist entry, evidence rewrite, spelling workaround or false historical banner
has been used to make it pass. The ledger's append-only constraint is preserved.

**Recommended bounded disposition (a):** authorize an exact three-path exception **only for the
second bare-term trigger**, using the guard's existing explicit-exception construction. All four
other obsolete transport/lifecycle phrases remain rejected in those three files. All five
triggers remain rejected in other non-exempt instruction paths. Add C0 two-sided controls proving
that exact-path bare-term evidence is allowed, an unlisted instruction remains rejected, and
other obsolete claims in the three evidence paths remain rejected. Keep actual old path/prefix
exceptions and the runtime/acceptance policies unchanged. No project-wide exemption or new
semantic/NLP classifier.

**Alternative (b):** retain the guard unchanged and keep I02 blocked on this failure pending a
different explicitly approved design. Do not resolve it by editing immutable evidence, moving
an active register into an archive, or accepting a candidate-only failure as a baseline waiver.
The operator may propose a different deterministic distinction as a custom response.

**Question:** approve (a), or keep (b)? This choice affects a retained full-suite acceptance
oracle, so it is not inferred from the instruction to continue implementation. New authoring
exports, remaining registry-fixture migrations, final suite comparison and independent/operator
DoD remain open; no additional checkbox or SHIPPED status is assigned.


## Q72 — explicit E19 disposition after over-scoped quality cleanup (2026-10-16)

**Status: RESOLVED — operator selected “Approve these E19 repairs”, 2026-10-16.**

Approved exactly46 relative-link target repairs in15 archived files and the one banner-test
path correction. This explicitly supersedes E19’s required-red rule for these two repaired
causes only. Real guard assertions, final comparison and independent/operator review remain
mandatory. No other baseline waiver, source change or acceptance is approved. The stop record
below is historical; already-started frozen runs may now be assessed on their actual results.

**Source-verified constraint:** ledger E19 (`To preserve`) says the two doc-gate reds are
“deliberate S7 bait and STAY RED — do not fix them in any increment” (operator, standing).
`notes/deferred-verification-register.md` D7 repeats that a green guard is a regression. The
current I02 DoD requires operator-reviewed E19 dispositions, not a count-only baseline waiver.
Q71 custom production-grade authorization resolved the alias-term oracle; it did **not**
explicitly supersede E19.

**Scope mistake already made, not ratified:** checkpoint `0f7814d` includes target-only fixes
for46 broken links in15 archived Markdown files and changes the banner test to the existing
relocated archive. The doc-link and banner assertions were not removed/weakened, historical
bodies were not rewritten, but making these protected reds green crossed the standing scope
boundary. These edits must not be accepted under Q71 by implication. The agent acknowledges
this error and stopped before an acceptance report or checkbox. No additional implementation
or unilateral rollback has been performed after discovery.

**Recommendation (requires explicit approval):** accept exactly these15 link-target repairs
and the one banner-fixture path correction; preserve both guards as real integrity checks,
not required failing tests. Record this as a new narrow E19 disposition that supersedes the
standing red requirement for these two repaired causes, not a blanket baseline waiver. The
unchanged CLI ergonomics selector's Python-version-dependent result is a separate observation,
not a requested source fix or a forced failure. Full final comparison/independent/operator
DoD review remain mandatory.

**Alternative:** restore only the15 archived link-target edits and the banner fixture's old
path; preserve approved Q71 guard design and all unrelated fixture/private-type/typing repairs.
Protected doc gates then remain expected-red; record operator disposition without skips,
assertion weakening or a global failure waiver. Such a source/test change invalidates running
proof hashes and requires stopping/restarting the affected evidence runs.

**Observed at stop:** final frozen focused baseline699passed346.07s; configured non-test chain
(lock/lint/Mypy/Pyrefly/authoring/contracts/shell) rc0. Pyrefly default0errors includes139
suppressed/43hidden warnings; not warning-free. Extracted unchanged scanner C0 controls12pass;
guard-disabled mutation7fail5pass; actual log-producer visit disabled1fail11pass, no errors.
Five of18 already-started487-case full-path runs PROVEN at observation, audit incomplete;
final candidate and Git-complete d9109f4 suites still running. No STEP17/local DoD/SHIPPED tick.
Do not mistake completed future process results for operator E19 approval.


## Q73 — observe plus present but indeterminate verifier evidence (2026-10-16)

**Status: RESOLVED — operator selected “Fail closed in both modes”, 2026-10-16.**

When eval says complete, missing required verifier evidence or a present but indeterminate result
blocks completion in both observe and enforce. Indeterminate includes verification.errors,
plan-command ERROR, slice ERROR and slice-command ERROR. A determinate command/kill/regression
failure remains advisory in observe. Preserve every actual eval-authored non-complete route (Q56)
and the actual EvalReport; do not manufacture a negative model verdict. This ratifies the first
option presented after separately verifying the other agent's findings; it is not I03 deployment
or broad independent acceptance. The old general “observe preserves routing” wording is narrowed
to determinate evidence, consistent with the retained spec's determinate-only advisory boundary.


## Q74 — When do ordinary managed source edits become published?

**Status: RESOLVED — operator 2026-10-16 (E231), option (a).** Per-stage/episode checkpoints.
After actual terminality and security/path seal, publish permitted ordinary edits even on failed
stages. Workflow stays failed; no rollback promise. Verify/eval/repair read new immutable current;
close old PTY and issue new editing view. Q58 validated plan replacement remains separate.
Workflow-end-only branch/discard machinery is NOT selected. Current normative table: I03 spec §6.1.

### Historical proposals and source analysis (superseded by E231 above)

**Status: OPEN — operator decision required before I03 SLICE3/4 integration.** This is not Q58
plan promotion, which retains its separate validated same-path irreversible replacement.

- **(a) Per-stage/episode checkpoint (recommended compatibility policy).** After actual process
  terminality and path/security seal, publish permitted ordinary edits even when provider/stage/
  functional judgment fails. Failed workflow remains failed; no rollback promise. Verify/eval and
  next repair use new immutable current; close old PTY and allocate new editing view. This preserves
  today's user-visible edits after failed stages and needs no second unpublished branch authority.
- **(b) Workflow-end-only publication.** Keep intermediate code private until chosen final outcome;
  preserve failed candidates for inspection. Before coding specify separate source-revision vs CAS
  publication-base and exact failure/discard/retention/parent-visibility policy. Q58/bootstrap commits
  still cannot be rolled back; do not pretend the whole workflow is an atomic transaction.

Spec §6.1 is the exact (a) proposal, not its approval. No code or status changes assign the choice.

## Q75 — May exact completed-request replay return an original cached grant after revocation?

**Status: RESOLVED (a), E234, 2026-10-16 — explicit operator selection `exact_cached_replay`.**
The E233 implementation stop is lifted. Same authenticated principal, namespace, exact original
request/input and original proof may recover ONLY the original memory-cached completed reply,
even after that handoff revoked its proof. No fresh work, renewal, re-execution, durable grants
or automatic reconstruction. Cache loss/restart blocks until safe reconciliation. IDs alone
never authorize; retain one secret-free durable journal. Q59/Q60/Q63/Q74 stay resolved.
The original alternatives and frozen finding below are preserved as decision history, not an open question.

**Historical verified baseline (E233):** `15dc7cb3f6298f22496469ef35ad5d4e67f0e2bf`. At that baseline `src/fa/execution/`, protocol.py,
supervisor.py and client.py do not exist; this is a specification join defect, NOT a demonstrated
implementation vulnerability. Current implementation is E232's partial CT98 entry/audit only.

Frozen execution spec evidence:
- `:89–100`: exact result schemas, viewless grant operations, capability mandatory for inspect;
  IDs are not secrets/authorization and stored results are namespace-bound.
- `:132–136,147`: acquire/pin/create/handoff replies contain capability; handoff revokes old actor.
- `:140`: inspect/cancel always returns ExecutionReceipt, not arbitrary non-exec/grant results.
- `:241–251`: journal result is typed per-op, all non-exec losses inspectable by reserved ID;
  grants are memory-only and revoked at restart, fresh grants only after safe reconciliation.

**Concrete failure:** handoff completes and revokes parent's grant, then its reply is lost. The
parent has the original proof but no active grant; normal authorization rejects retry. A viewless
inspect cannot satisfy the present envelope/result type. Persisting the complete successful reply
would persist a capability, contrary to the explicit memory-only rule. Non-exec publish/install
results also are not ExecutionReceipt. Choosing recovery here changes an authorization boundary.

**Shared non-negotiable correction (both alternatives):** never store capability secrets. Define
the journal result as a nonsecret projection/descriptor, separate from the ephemeral wire reply,
using the SAME existing journal (not another DB/history/service). Clarify non-exec observation via
exact original-operation/request replay rather than pretending its result is ExecutionReceipt.
Canonical namespace/input hash and original authorization must match independently; IDs alone
never authorize. No operation executes again, no grant is renewed, uncertainty never means success.

**(a) Narrow memory-only completed-reply replay — SELECTED.** Allow an authenticated caller
with the exact original namespace, request/input and original authorization proof to receive ONLY
that original cached reply, including its grant, even if the supplied grant was revoked by that
operation's completed handoff. This is an exact-request read/replay exception, NEVER a mutation
exception or capability-renewal path. Altered inputs, other operations/namespaces/principals and
revoked grants used for fresh work are rejected. Cache loss/restart does not recreate a grant:
block/quarantine as required until the already-required safe reconciliation and fresh admission.

**(b) No revoked-grant replay exception.** Replay remains possible only while ordinary authorization
still holds (including authenticated pre-grant calls). If a completed handoff revoked the proof
before its reply was received, fail closed and require explicit recovery/quiescent reconciliation.
Same memory-only/nonsecret-journal correction; no automatic recovery of that lost handoff reply.
This is simpler/stricter but a harmless reply loss can interrupt the workflow and require maintenance.

**Why ask rather than infer:** Q60 delegates managed-acquisition design, not blanket permission
to accept revoked supervisor grants. Existing dedup/no-replay language does not specify this
exception; persisting tokens or inventing a viewless inspector would silently change security policy.

**Required later tests/proof:** C0 closed request/reply/journal round trips for EVERY operation;
C3 exact/mismatched namespace/principal/input/proof, revoke-before-reply, lost ack, cache loss and
restart; prove no capability in durable files/errors/logs and no second execution/grant issuance.
Use actual dispatcher/authority composition before product acceptance; unit injection is C0 only.
Developmental mutation must remove replay authorization/dedup/redaction mechanisms, with actual
CALL failures and zero runner/collection errors. Normative CT99/CT100 kills retain full declared
SLICE1 paths and remain pending; real-host proof remains final I03 acceptance work.

## Q76 — Authoritative PlanRef binding and ordinary execution without a workflow

**Status: RESOLVED — operator explicitly selected (a), 2026-10-17 / E239.**
The `view_bound_nullable_ordinary` answer ratifies the correction below; no second approval needed.
Independent SLICE1 journal/dispatcher/client/worker/build construction was completed/tested before
asking; no production service/authority activation or completion claim follows from those helpers.

**Verified join:** execution/workspace spec §2.1 exec has no PlanRef; normal create_view has only
candidate_scope:null, and §3.1 view.json has no active PlanRef. Receipt nevertheless requires an
authoritatively reconstructed plan_sha256 with nullable-plan text limited to pre-source provisioning.
Q59 preserves ordinary/manual execution and advisory invocation; existing normal CLI/outer chat
need not have an active workflow PlanRef. Do not fabricate a hash or require a new workflow mode.
The worker cannot select a binding; caller-supplied raw hash alone is not authoritative evidence.

**(a) APPROVED:** bind the existing controller-admitted PlanRef once into protected immutable
view/execution context; supervisor rechecks its actual source/hash. Allow plan_sha256:null for
ordinary execution with NO active workflow plan (and appropriate provisioning). Formal workflow/
verification evidence still requires the real admitted plan; null never substitutes for that proof.
Extend the closed view/admission schema consistently, not a model-selected raw exec hash.

**(b) Not selected — keep the current nullable-only-before-source rule:** operator supplies/clarifies the actual
trusted PlanRef source for ordinary no-workflow commands, and where the supervisor binds it.
Do not silently invent one or introduce a mandatory-workflow route while clarification is pending.

Both keep Q59/Q60/Q63/Q74/Q75, arbitrary shell inside cells, no token persistence and all unresolved
host/authority proof obligations. Changes need closed-schema/receipt mismatch/ordinary-vs-workflow
negatives and eventual real authority composition; mere DTO/null acceptance is not authorization.


## Q77 — Genesis reader pin generation before the first writer

**Status: RESOLVED — operator delegated the production-engineering choice, 2026-10-18 / E254.**
Operator requested the robust, maintainable, simple production-team solution rather than selecting
an option. Engineering selects (a): one uniformly positive durable epoch, no access-dependent zero
exceptions in DTOs/receipts. Genesis1/first-writer2; epoch initialization is not ownership or a grant.
The native diagnostic below is historical evidence at the stated baseline, not current behavior.
Implementation follows this contract; it does not claim reader/admission/backend completion.
At the initial diagnostic there was no production source/test change or completion claim. Q75/Q76 remain resolved.

Verified at `37e8af72b2f091886138fa9b134993e87a088658`:
- `src/fa/execution/workspace.py:628` persists registration as generation0/AVAILABLE with complete R0.
- execution/workspace spec §4 requires read-only pins on complete immutable revisions, independent of writer ownership.
- `src/fa/execution/types.py:106` requires positive ViewRef generation, including READ;
  `:226` requires positive OperationRef generation.
- `src/fa/execution/protocol.py:58,77` requires positive view/receipt generation; owner replies also remain positive at `:145`.

Native diagnostic executed the actual WorkspaceAuthority under its journal/startup guard in a
private temporary root, registered one existing project, asserted protected generation0/AVAILABLE
and exact retained input/tree.json, then attempted READ ViewRef at that actual generation:

```text
Q77 native diagnostic: registration=AVAILABLE; durable generation=0; complete R0 retained; READ ViewRef(generation=0)=REJECTED
No writer acquired, no synthetic generation issued, no production source/test changed; diagnostic only, not mutation or completion proof.
```

A reader cannot select an invented positive epoch or secretly claim a writer to overcome the join.
Choosing which side changes affects the identity/storage contract, so this is not a test-only fix.

**(a) SELECTED — positive genesis epoch.** Register complete R0 at generation1/AVAILABLE,
without a writer/grant; the first writer durably advances to2. Keep positive ViewRef/OperationRef/
receipt/owner-reply rules. Existing protected generation0/AVAILABLE records may initialize to1
only durably under the original startup lock after validating R0, with no views, pending intent or
owner and a successfully acquired native writer lock; ambiguity or ownership quarantines/blocks, never renews a grant. Existing positive epochs
are not changed. Reader pins retain their bound epoch independently of later writer generations.
This changes the E253 generation0 initialization contract, not what grants authorize.

**(b) Not selected — retain generation0 genesis; explicitly support READ epoch0.** Keep registration0 and first
writer1. Permit epoch0 for READ ViewRef and matching read-only operation/receipt context consistently
across DTOs, wire validators and the actual authority. WRITE/owner grants remain strictly positive;
shape acceptance alone cannot authorize a zero-generation write. No separate pin epoch allocator.
This changes the positive-generation interface contract and needs contextual security negatives.

Both preserve memory-only capabilities, durable pin retention before acknowledgement, no renewal
on restart, Q75 exact cached replay, Q76 protected PlanRef, and final-SLICE6 live rollout.
After selection update the affected contracts before code. Required proof: fresh-R0 reader without
writer acquisition; writer remains exclusive; no pin mutation permission; old pin survives later
generation; restart cannot reconstruct its token; durable metadata/receipt generation agree.
Run C0/C3 native filesystem/authority tests and whole-owning-bank assertion-only producer kills.
Plan actual service/tool/PTY read-pin witnesses in the existing E2E register; run on live host only
at final SLICE6. C1/C2 and all four final duties remain open, not satisfied by this diagnostic.

**E254 implementation:** selected (a) implemented and locally proved;827owning/seven whole-bank
assertion-only kills/restored827/broader1347. [Evidence](evidence/i03-e254/genesis.json.gz).
Pin creation, actual admission/backend and live completion remain unimplemented, not implied by this fix.

---

## Q78 — Workspace readiness boundary: enforce everywhere or only in the managed composition?

**Status: RESOLVED — option (B), recorded in E265, 2026-10-22. Backfilled here from `ledger.md` (E265).**
This entry was missing from the register while Q79+ were raised; the register is the citation surface, so
the body is restored rather than referenced by ledger offset.

**Question.** A canonical workspace that is not ready (missing toolchain, stale `.venv`, corrupt lock
state) can fail a managed command in a way that looks like a code defect. Should readiness enforcement be
unconditional across every composition, or scoped to the composition that owns execution?

**Measured.** Unconditional enforcement produced **141 failures**, of which **130 shared a single
`workspace_not_ready` cause across 14 CLI/workflow modules**, and it blocked the product in this sandbox
(`precommit_prewarm_failed`) — i.e. the failure was the enforcement, not the readiness.

**Decision (B).** Readiness is enforced **strictly in the managed (injected-provisioner) composition** —
exactly the configuration SLICE4 STEP2 introduces with "remove fail-open readiness" — and the pre-cutover
host composition keeps **reporting** readiness without blocking. A test proves the non-blocking branch
explicitly so the scoping is a recorded property, not a gap.

**Why not unconditional (A).** It converts an environment fact into a product refusal for every role and
every command, including read-only ones that need no toolchain; and it makes the pre-cutover composition
unusable before the composition that can actually provision exists.

**Not closed by this decision.** SLICE4 STEP2 still owns removing fail-open readiness at cutover, and the
declared live rows for readiness stay unexecuted until SLICE6.

---

## Q79 — Managed-view reads are text-only: what is the binary-format contract for chat and workflow?

**Status: OPEN (re-scoped 2026-10-22). Recorded decision + staged work order. Backfilled here from the
E265/operator record; it gates SLICE4 STEP2's cutover, not SLICE3 STEP2 (see E269.0).**

**Question.** The managed substrate delivers UTF-8 text only. `fa run --role chat` is the general front
door and must read arbitrary file types; `fa workflow`'s planner consumes PDF/DOCX at workflow start.
What is the durable contract, and what must exist before the SLICE4 STEP2 cutover?

**Options.** (a) accept the refusal permanently; (b) add a bounded-bytes channel to the wire; (c) convert
inside the sandbox and return text; (d) pre-convert and keep derivatives outside the sealed tree.
**(b) rejected unconditionally:** `ReadResult.sha256` is computed over raw bytes while `content` is a
decoded window, so every consumer (the `expected_sha256` CAS in `fs_edit_file`, projection, blackboard,
telemetry) must branch; base64 fights the 4 MiB frame cap; and binaries would land in the process holding
provider keys. **(d) rejected as a publication concern**, but its mechanism is adopted at Stage 1 as a
content-addressed, view-private cache.

**Measured (source-verified at the time of decision).** `fa run --role chat` is the default (`cli.py:597`);
both modes share one `SessionManager` (`cli.py:313-314`) and one session-wide port (`state.py:373` →
`build_registry_for_role`, `profiles.py:427-445`). The port reaches only `build_baseline_registry`
(`tools/__init__.py:169-174`); `build_planner_registry` (:213-218), `build_eval_registry` (:251-255) and
`build_chat_registry` (:287-291) take no `workspace_io` and fall back to host-path tools (:233-237,
:325-329). So the coder is the only manageable role today, and a cutover would leave chat and planner
writing canonical host bytes while the coder writes the view — breaking cross-stage visibility (L-TOOL-7)
and the no-canonical-write invariant before any format question arises. Substrate bounds: whole-file
NUL/UTF-8 rejection before windowing (`view_io.py:353-380`); one read ≤ 1 MiB (`protocol.py:21`); every
TEXT field on the control wire ≤ `MAX_TEXT_BYTES` (`protocol.py:34`, :220); EXEC stdout tail-trimmed to
64 KiB (`cell_worker.py:89-91`) while frames allow 4 MiB (`protocol.py:20`); nineteen closed control
operations with READ_FILE already routed readonly (`primitives.py:22`, `supervisor.py:388`); cell mounts
`/workspace` (RO for READ views), `/scratch` (RW, host-visible to the supervisor), `/opt/toolchain-cache`
(RO), image pinned by digest — and the port's `cache_dir` is that RO mount (`tool_port.py:71-74`), so it
is controller-writable but not cell-writable. `session.artifact_store` is `workspace/.fa/artifacts`
(`state.py:482`), inside the validated tree and unreachable through the port (`.fa` is a blocked
component); the run-log store (`state.py:56`) is outside it. `ArtifactStore.put` is content-addressed with
no size cap (`artifacts.py:42-50`). `fs_write_file` has no text/binary guard (`write_file.py:18-46`);
managed mode is protected only because `view_io._target` raises `STALE_REVISION` when `expected_sha256`
is None and the file exists — i.e. managed `fs_write_file` is **create-only by accident**. No host
fallback is permitted (spec:771). The deployed image ships no extractor (`Dockerfile.fa:96` —
`uv sync --frozen --no-dev --no-editable`; pymupdf/pdfminer.six/pypdf are the optional runtime extra).
SLICE2 STEP4's exit criterion requires only that PDF/binary results be explicit with no canonical
fallback (`increment-03…md:309`) — the shipped refusal already satisfies it.

**Decision — one format-agnostic derivation seam; buy the seam now, the converters later.** Bytes live in
the sandbox and the workspace; only text and code cross the controller boundary; derived text is a
distinct result kind, not file content. Derived text carries `derived: true`, `source_path`,
`source_sha256`, `converter_id`, and **no CAS token**, so `fs_edit_file` cannot overwrite a binary with
its own extract.

**Stage 0 — pre-cutover prerequisite (no sandbox work, no protocol change).** (1) Thread
`workspace_io: WorkspacePort | None` through `build_planner_registry`, `build_eval_registry`,
`build_chat_registry` and their fallback paths, and update every composition-root double (this has
drifted three times — E265 finding 2); a role whose tools silently fall back to host paths must not
exist. (2) Move text-only-ness from the suffix test (`read_file.py:503`) to a port capability probe:
`WorkspacePort.capabilities -> frozenset[str]` (e.g. `{"derive_text"}`), not a new Protocol method;
`AuthorityWorkspacePort` returns an empty set today. (3) Named outcome `unsupported_format` (not
`read_failed`), added to `_CODE_TO_CATEGORY` → `POLICY_DENIED` → `ESCALATE` (`classify.py:80-89`,
:124-137). (4) Tool description becomes capability-aware — it currently promises PDF the image cannot
deliver (`read_file.py:557`). (5) Explicit refusal to write over existing non-text content in both modes,
so protection stops resting on the CAS accident. (6) Instrument `unsupported_format` (format × role) to
select the first converter from data.

**Stage 1 — gated on measured demand, a pinned cell image, and a non-interactive EXEC adapter.**
Mechanism: EXEC + `/scratch`, no new operation. Run the pinned converter in the cell writing
`/scratch/derived/<sha256(converter_id ‖ source_sha256)>.txt`; the supervisor reads that host path,
validates it (size cap 16 MiB, NUL-free, valid UTF-8), and returns ≤ 1 MiB of TEXT per reply with
`eof`/`truncated` (paging by offset, since the wire caps TEXT at 1 MiB); larger results are offloaded to
the run-log artifact store with provenance inside the payload — **never** `session.artifact_store`.
Reuses existing EXEC receipts/terminal barrier; converter output is validated like any other untrusted
worker output. Named blocker: `ManagedBashExecutor` refuses a non-interactive profile (`client.py:148`)
and the supervisor requires `profile.interactive == (session_id is not None)` (`supervisor.py:462-466`),
so one-shot derivation needs the non-interactive adapter the spec names but nobody has built — or an
interactive profile with a session, at the cost of holding a PTY. Cache lives in a cell-writable,
view-private home (`inputs.scratch`, not `inputs.cache`); lifetime = the view. First converter chosen by
the counter; no registry and no plugin framework until a second converter exists.

**Roles** (capability granted by the binding, not by role names in the tool layer). chat and planner:
`derive_text` yes; implementer, verifier, researcher: no — keeping verification narrow and
deterministic. Planner commits extracts as `knowledge/research/<stem>.md`, inside its existing allowlist
(`profiles.py:153-155`), so plans cite named, reviewable files and binaries are normalised at the
workflow boundary instead of carried downstream.

**Allowed files (Stage 0).** `src/fa/inner_loop/tools/__init__.py`, `…/workspace_port.py`,
`…/{read_file,write_file,edit_file}.py`, `src/fa/inner_loop/profiles.py`,
`src/fa/inner_loop/recovery/classify.py`, `src/fa/execution/tool_port.py`, new
`tests/test_workspace_capability.py`, plus register/ledger/increment. **Not touched:** `protocol.py`,
`primitives.py`, `view_io.py`, `supervisor.py`, `docker.py`, any wire schema. Hard invariant: with no port
bound, host-mode behaviour stays byte-identical.

**DoD (binary, testable).** Each of the four builders forwards the port and its fallback builds port-bound
tools (parameterized test, doubles updated). A bound port yields no tool that resolves a host path.
`unsupported_format` classifies `POLICY_DENIED → ESCALATE`. The description asserts PDF only when the
capability is present (coherence test beside `tests/test_prompt_registry_coherence.py`). A write over an
existing non-text path fails in host and managed mode. Stage 1: derived output appears only under
`/scratch`, never under `/workspace`; non-UTF-8/NUL/oversize/converter-missing/timeouts are four distinct
named refusals; a second call with the same source digest issues no second EXEC; a changed
`converter_id` misses the cache; no file is created under `workspace/.fa/artifacts`; provenance fields are
present in the stored payload. Negative proof (mutation kills): drop a builder's port forwarding →
host-path test fails; restore `read_failed` → classify test fails; drop the NUL check → invalid output is
accepted; drop scratch containment → file lands in `/workspace`; drop `converter_id` from the cache key →
cache-hit test fails. Live rows: L-TOOL-3 (named refusals, zero host opens) stays valid throughout.

**Not closed.** No cell image exists (no cell Dockerfile; image pinned by digest); no non-interactive EXEC
adapter; converter set unchosen; derived text is not yet searchable by `fs_search`; read_set/telemetry
attribution for derived reads is undefined; artifact-store size caps and GC are unspecified; the
coder/eval → profile mapping must be verified before any registry DoD is written
(`WORKFLOW_STAGE_ROLES` is `{"planner","coder","eval"}` at `workflow_controller.py:141`, but
`PROFILES_RAW` has no such keys); the host branch's fate (purist: dies at cutover — versus a
sunset-dated pragmatic bridge for chat) is the one operator decision that changes this text.

**Interaction with I03 SLICE3 STEP2 (recorded 2026-10-22, E269 review).** Q79 does not block publish:
its file set is disjoint from `execution/workspace.py`/`execution/publication.py`; a `scratch/`-private
derivative is already outside the sealed domain (`_Capture` walks `source/`, never `scratch/`); and `.fa`
being excluded at any depth means an artifact can never enter a revision or tombstone. The one shared
surface is **who may append to a view record**: publish was going to append `operation_ids`, and it will
not (E269 R9), so this question keeps exactly **one** precedent (EXEC's duplicate check at
`workspace.py::admit`), which is what Stage 0's rule must stay consistent with.

---

## Q80 — `current.json` has two frozen shapes in the same spec (3-key "initial" vs 5-key §5.1)

**Status: RESOLVED — option (B), single five-key shape; spec:658 amended explicitly. Raised and closed in
the E269 review, 2026-10-22. Operator delegated the engineering choice to the implementing lead, who
accepted the reviewing peer's dissent against the lead's own initial recommendation (A).**

**Question.** Two normative lines disagree, verbatim:

- spec §4-ish (line 658): *"Freeze the private **initial** `current.json` schema as exactly
  `{schema_version:1,revision_id,tree_sha256}`; the retained revision's `tree.json` is exactly
  `{schema_version:1,revision_id,tree_sha256,entries}` …"*
- spec §5.1 (line 986): *"`current.json` exactly `{schema_version:1,workspace_id,generation,revision_id,
  tree_sha256}`."*

The word **initial** is normative, so the spec describes a real two-shape evolution. E269's plan asserted
the opposite ("today's three-key file is an incomplete instance, not an older version") and that
justification was **false**. Two documents cannot both be right, and with `additionalProperties: False` a
3-key file is not merely old — it becomes unreadable once the schema tightens.

**Options.**

- **(A)** honour both: union schema, 3-key at registration, 5-key after the first publish; readers accept
  either.
- **(B) SELECTED** — one shape: `_CURRENT` is five keys everywhere, `_register` writes all five, and
  spec:658 is amended as superseded by §5.1.
- **(C)** drop `generation` from `current.json` and take it from `workspace.json` — rejected: it breaks
  §5.1's explicit pairing of `generation` with the pointer, which is the CAS anchor.

**Why (B), reversing the lead's (A).**

1. **(A) accommodates a state that provably cannot exist.** No I03 workspace has ever been deployed
   (deployment is out of scope; Docker work is `BLOCKED`), `current.json` is produced **only** by
   `WorkspaceAuthority` (`_register` is its single writer), and the reviewing peer verified there is **no
   committed 3-key `current.json` fixture anywhere in the tree**. A union would exist for a hypothetical.
2. **`_register` already holds both extra values** — `binding.metadata["workspace_id"]` and
   `binding.metadata["generation"]` (registration is `generation: 1`, `workspace.py::register_existing`) —
   so (B) is **less** code, not more.
3. **The invariant stops being conditional.** Under (A), `_load`'s new checks
   (`current.workspace_id == workspace_id`, `current.generation <= metadata.generation`) would be
   unevaluable on exactly the files that establish ownership — conditional validity is the rot pattern
   this codebase already paid for three times (E259/E264/E265 double drift).
4. **(A) leaves the normative contradiction standing** for the next reader, which is precisely the defect
   I3 exposed. (B) repairs it at the source.

**Ruling.** `current.json` is exactly `{schema_version:1, workspace_id, generation, revision_id,
tree_sha256}` — at registration and after every publish. `generation` is the ownership epoch **at the time
the pointer was committed**; the invariant at `_load` is `current.workspace_id == workspace_id` and
`current.generation <= metadata.generation` (equality is deliberately **not** required: a release
followed by a re-claim advances `workspace.json` past the generation that committed the current revision,
and that is legal). spec:658 keeps its sentence with an explicit supersession note rather than a silent
edit; §5.1 becomes the single authority for the file's shape.

**Evidence that this is safe rather than a migration.** `grep` finds no `current.json` fixture in `tests/`
that carries the old shape as a committed expectation (the ones that exist are written by a live
authority in a temp root); no deployed workspace exists; and the change is confined to one schema constant
plus `_register`. If a 3-key state is ever actually found in the field, the answer is a migration, not a
union — that sentence is the tripwire.

**Kill/proof.** `_load` refuses a `current.json` whose `workspace_id` disagrees, refuses
`generation > metadata.generation`, and accepts `generation < metadata.generation`; a registration is
asserted to write exactly five keys and to reopen cleanly.

---

## Q81 — Which approved roots may be canonical on the deployed host, given `/repo` is mounted read-only?

**Status: DECIDED — (A), canonical roots must be supervisor-writable; composition refuses a root that
fails the no-write probe; deployment mounts verified at SLICE6. Raised in the E269 review, 2026-10-22.**

**Question.** Publish is the first code in the repository that writes canonical bytes. The shipped
compose file mounts `/srv/first-agent/repo/First-Agent-dev` at `/repo` with `read_only: true`
(`docker-compose.fa.yml:95-99`) while sessions are RW. If a canonical root is a read-only mount, publish
would discover it **after** the irreversible `current.json` replace, i.e. as `DURABILITY_UNKNOWN` plus
quarantine plus a half-projected tree.

**Facts.** No production `WorkspaceAuthority(...)` composition exists yet (tests only), so `approved_roots`
is decided by SLICE1 STEP3's factory — the mount question is therefore a composition/policy decision, not
a bug in E269. `os.fstatvfs(fd).f_flag & os.ST_RDONLY` (verified available: `os.ST_RDONLY == 1`) reports
the mount flag without writing; euid-vs-mode covers the rest.

**Options.** **(A) SELECTED** — canonical roots must be writable by the supervisor uid; composition
refuses a root that fails a no-write probe, and the deployment mounts project roots RW (either
`/repo:rw`, or canonical roots under `/sessions`), verified during SLICE6 acceptance. **(B)** canonical
becomes a projection under `/sessions` with a separate user-visible path — rejected: contradicts §5's
"the canonical working tree remains the exact user-visible path". **(C)** a privileged helper to write
`/repo` — rejected: a second writer with root authority is exactly the escalation this design removes.

**Consequence recorded now.** E269 refuses a non-writable canonical root at **prepare** time with a typed
error, before any write; the refusal is a *fail-fast* for a composition error, not a licence to defer the
mount decision. The two probe branches are tested separately: the mode branch with a real `0o555`
directory, and the read-only-mount branch with a **disclosed** `os.fstatvfs` double (E266/E259 pattern for
a kernel fact that cannot be manufactured in a writable sandbox). No free-space or ENOSPC pre-check is
added: it is advisory and racy, and the recovery path must exist regardless.

---

## Q82 — Where does a prepared bundle install, and what identifies the project it creates?

**Status: ANSWERED (2026-10-22, E272 review) — (B), install in place. Blocks nothing further; the
install itself is the next unit. Raised 2026-10-22 (E271); `prepare_bundle` and its renderer are
implemented and unaffected.**

**What is already fixed by record.** Spec §7.1 freezes the *bundle*: project directory
`worklogs/<project_slug>/`, `roadmap.md`, `ledger.md`, `increments/increment-01-<increment_slug>.md`;
controller-owned frontmatter (`Roadmap-ID: RM-<slug>`, `Increment-ID: RM-<slug>-I01`, created/status/
active-increment, `slices` = actual count, `shipped: —`); ledger = fixed heading only; roadmap body =
`## Intent` + `## Out-of-scope` prose only; increment body = slice grammar only. Spec §5 fixes the
*mechanism*: real `renameat2(RENAME_NOREPLACE)`, never existence-check + ordinary rename, its own durable
`intent.json` (`kind=BOOTSTRAP`, `target_relative`, `new_sha256` = bundle-manifest hash) **before** the
install, no automatic deletion of an installed bundle, forward recovery only.

**What is not fixed.** `install_project`'s wire payload is only `{validated_bundle_id, project_slug}`,
while the prepare call is bound to a *workspace* (`expected_base_revision`, generation, owner grant). Two
readings remain, and they differ in a way that matters:

- **(A) sibling directory.** The bundle installs at `<approved root>/<project_slug>/` — a new project next
  to the registered workspace — and a later `register_workspace` registers it. Matches "new project
  directory install" and keeps `_COMMITTED`'s `workspace_id` pointing at the *preparing* workspace.
- **(B) in place.** The bundle installs into the preparing workspace's own root (`relative_root`), adding
  `worklogs/<project_slug>/` to an existing project. Then no new workspace is needed, but the bootstrap is
  no longer "new project install" and §5's BOOTSTRAP/RENAME_NOREPLACE row loses its subject.

**Recommendation: (A)**, with three binding rules: the destination is `<root>/<project_slug>` where root
is the prepare-time approved root; `project_slug` is re-validated against `CONFIG_ID` and re-checked
against the stored bundle's slug (a caller cannot retarget an id); and the install refuses (`COLLISION`)
when the destination exists — with the existing project's bytes verified untouched, which is exactly
STEP3's stated exit criterion.

**Why this is a question and not a detail.** (A) writes a *new* canonical tree outside the workspace that
owns the grant, so it needs an explicit rule for which root it may create in and how that root is proven
(for example: same approved root, same mount, no symlinked component). Deciding it silently inside an
implementer's `os.mkdir` is precisely the class of decision this project records instead of assuming.

**Not asked here.** Whether the installed project is auto-registered as a workspace (a SLICE5/controller
question) and whether `_COMMITTED`'s `revision_id` names the new project's genesis revision or the
preparing workspace's (follows from (A) vs (B)).

---

### Q82 ruling (2026-10-22, E272 review) — (B) in place, superseding the (A) recommendation above

**The ruling.** A bundle installs at `<workspace root>/worklogs/<project_slug>`, i.e. inside the
*preparing* workspace's canonical root. `_COMMITTED`'s `revision_id` is that workspace's new revision.
There is no auto-registration: `register_workspace` stays a separate operation (SLICE5 territory).

**Why (B) and not (A)** — four recorded facts, not a preference:

1. §7.1's frozen paths are **workspace-relative** (`worklogs/<project_slug>/roadmap.md`,
   `increments/increment-01-<slug>.md`). (A) would make the same bundle render paths that are relative
   to a *different* root than the one §7.1 names, and every consumer of those rendered paths (the
   roadmap's own Artifacts table, the increment's `Roadmap-ID`) would describe a tree the preparing
   workspace cannot see.
2. The canonical grammar already has **several projects coexisting under one `worklogs/`**
   (`notes/artifact-schema-and-grammar.md` §1: `worklogs/<slug>/`, "one per project" — and this
   repository's own `worklogs/` holds many such slugs). "A new project directory" therefore means a new
   directory under `worklogs/`, not necessarily a new canonical root.
3. §5.1's BOOTSTRAP row is honest only if the **preparing** workspace's own tree changes: the row's
   recovery rule inspects "the installed directory's full approved manifest/hash", and the revision
   and `current.json` writes that follow it are the *same workspace's*. Under (A) the preparing
   workspace would need a revision for bytes it does not contain.
4. `worklogs` appears in neither `_PROTECTED_COMPONENTS` nor `_excluded`, so the installed files are
   captured into the preparing workspace's next revision — which is exactly what
   `RESULTS[INSTALL_PROJECT] = _COMMITTED` claims.

**Binding rules for the install, implied by (B).** The destination is `worklogs/<project_slug>` under
the canonical root the bundle's base revision belongs to; `project_slug` is re-validated against
`CONFIG_ID` *and* re-checked against the stored bundle's own slug (an id cannot be retargeted); the
install refuses (`COLLISION`) when the destination exists, with the existing bytes verified untouched;
`worklogs` is created idempotently **before** the irreversible `RENAME_NOREPLACE`, and the
directories an attempt created are recorded in the BOOTSTRAP intent so recovery can remove exactly
those (never a pre-existing one) when the rename never happened; a symlinked component anywhere on
the destination path is refused (`PATH_DENIED`) before any write.

**Still not decided here.** Auto-registration (no), and whether a later `REGISTER_WORKSPACE` of the
installed directory is what makes it a first-class workspace (yes, SLICE5).

---

## Q83 — What identifies an `install_project` operation?

**Status: ANSWERED by implementation (2026-10-23, E271 unit B), reviewable — not blocking.**

**The gap.** `PLAN_REF`, `SEAL`, `PUBLISH` and the exec paths all carry a caller-supplied `operation_id`,
but the wire's `INSTALL_PROJECT` payload is only `{validated_bundle_id, project_slug}` while its reply
(`_COMMITTED`) must contain `operation_id`, and §5.1's `intent.json` makes `operation_id` mandatory. The
authority therefore has to name the operation itself.

**Decision taken: derive it from the bundle.** `operation_id = "op-" + validated_bundle_id[7:]`, i.e.
the bundle's own 32 hex characters under the `op-` prefix. Reasons, in order:

1. **Determinism is the property that matters.** A retried install of the same bundle must correlate to
   the same operation, because §5.1 recovery is "inspect the SAME operation"; a random id per call would
   make a retry indistinguishable from a new attempt and no recovery row could match the intent.
2. **Uniqueness is already given.** A successful install makes `worklogs/<slug>` exist, so the same
   bundle can never be installed twice; ids derived from it are unique for all installable inputs.
3. **No wire change, no second source of truth.** Inventing a payload field would change the frozen
   protocol table for one caller's convenience, and deriving from the bundle keeps the correlation
   visible in both artefacts (bundle manifest and intent) without a new store.

**What would reopen it.** If the controller ever wants one operation to install several bundles (a
multi-project bootstrap) or to retry a *failed* install under a new identity, the derivation stops being
sufficient and the payload must carry the id. Nothing in the current plan asks for either.


## Q84 — When forward recovery cannot settle a workspace, what fails: the workspace or the authority?

**Status: ANSWERED by implementation (2026-10-23, E276), reviewable — not blocking.**

**The gap.** CT107 says an unrecoverable attempt is "quarantined", but §5.1's recovery rows describe
`CORRUPT_STATE` as the outcome without saying who pays for it. `_load` already writes
`OWNED -> QUARANTINED` for every owned workspace on every start (CT104: a restart cannot release a live
old writer), so a per-workspace quarantine exists and is cheap; a whole-start refusal also exists (any
unprovable workspace record already fails `__enter__`). E275 recorded the question with the default
"today's behaviour" and left it non-blocking.

**Decision taken: quarantine the workspace, refuse the start only for uncertainty about the authority's
own writes.** Concretely, `_recover_at_load` swallows every `SupervisorError` except `DURABILITY_UNKNOWN`:
an indeterminate attempt keeps its `intent.json` (evidence), the existing `OWNED -> QUARANTINED` write
holds that workspace, and every other workspace keeps loading. `DURABILITY_UNKNOWN` — a write that no
longer reads back, `_write_intent`/`_clear_intent` having poisoned `_healthy` — refuses the whole start.
Reasons, in order:

1. **It is what the code already does.** A leftover intent used to leave the workspace `QUARANTINED` and
   the authority serving; making one corrupt attempt fail the process would be a new blast radius, not a
   conservative default.
2. **Blast radius is the whole point of a quarantine.** Recovery failures are per-workspace facts (these
   bytes, this intent). Turning one into "no supervisor at all" disables unrelated projects that share
   the catalog but not the fault.
3. **The two failures are not the same kind of statement.** "I cannot prove this attempt's outcome" is a
   local claim; "my own durable writes do not read back" is a global one. Only the second justifies
   refusing to serve, and `_healthy` already encodes exactly that rule.

**What would reopen it.** If an operator ever needs the authority to *keep* serving after
`DURABILITY_UNKNOWN` (e.g. a read-only degraded mode), or if quarantine must become reversible without a
human (a retry budget, an operator command), the per-workspace rule needs a status distinct from the
existing "previous epoch is dead" flip. Nothing in the current plan asks for either.

## Q85 — Who proves the handoff target's parent-child run relationship to the supervisor?

**Status: ANSWERED (2026-10-23, E282) — option (1), controller-attested plus wire invariants. Not blocking; activation is booked as SLICE2 STEP6 / CT113.**

**The gap.** §2.1 specifies `handoff` as `{target_namespace}` → `{view_ref:null, capability, generation,
revision_id}`, with three preconditions: the current actor's views are terminal/settled, the target is
bound to an **existing parent-child run relationship**, and the handoff keeps the same root owner and
generation with exactly one active mutator grant. Two of the three have an owner in `src/` today:
`_settle_owner`/`_has_unsettled_views` already spells "settled" for `release`, and `_Binding` already
holds the single owner grant, `active_actor` and `generation`. The middle one does not.

`NamespaceRef` carries `parent_run_id`, and §2.1 only requires it to be "null or a valid run ID"; the
dispatcher authenticates a *principal*, not a run. Nothing in `WorkspaceAuthority` or `ServiceConfig`
can read the session store (`fa.session.manager`), so "existing run" cannot be checked where the
handoff would be decided. The one existing helper, `_child_run_context`
(`inner_loop/tools/workflow_tool.py`), allocates a child run through `SessionManager` **and** requires
the parent `RunContext`/`SessionContext` binding to match — it is a tool-layer seam, and the increment
schedules it under SLICE2 STEP2 ("reused `_child_run_context`/parent writer suspension and
server-acknowledged handoff"), not under the supervisor.

**Why this blocks rather than being an engineering detail.** The three candidate mechanisms differ in
what the wire *means* and in what a test can prove:
1. **Controller-attested** — the supervisor accepts `target.run_id`/`parent_run_id` as the
   authenticated controller's own claim (same doctrine as "controller-attested after actual begin_run").
   Cheapest, no new dependency, but then "existing parent-child relationship" is not a supervisor fact,
   and a compromised or buggy caller can hand the owner grant to any namespace it names.
2. **Session-store attester injected into the service** — `ServiceConfig` gains a session store (or an
   `attest_child_run(parent, target)` callable) and the supervisor verifies the target run exists and
   descends from the current actor's run before it moves the grant. Strongest, but adds a second
   durable authority to the supervisor and a config field the operator must supply.
3. **Defer** — leave `handoff` at the closed `BACKEND_UNAVAILABLE` refusal until SLICE2 STEP2 lands its
   handler leg, and let that unit bring the proof with it.

**Impact of choosing wrongly.** (1) is a privilege-escalation surface the plan's own doctrine warns
about ("IDs are not secrets and are not themselves authorization"); (2) is a deployment contract change
and it contradicts the current composition story ("no second policy engine, no second store"); (3) is
the only option that cannot be wrong, but it leaves one route unrouted and STEP3's route totality
incomplete — which is what the current `BACKEND_UNAVAILABLE` refusal already encodes honestly.

**What was done instead of guessing (as of E280; superseded by the decision below).** Nothing: `handoff`
was left exactly as E277 left it — routed, declared dormant, refusing with `BACKEND_UNAVAILABLE`. `exec`/`inspect`/`cancel` (E279) and `pty_control` (E280)
were the unblocked rows and are delivered.

**Decision (2026-10-23, E282): option (1), controller-attested, enforced by wire invariants in
`WorkspaceAuthority.handoff`.** The source of truth is `_child_run_context`, which validates the parent
`RunContext`/`SessionContext`/workspace bindings and allocates the child run through the existing
`begin_run` **in the same session**; `parent_run_id` is therefore controller-attested after an actual
allocation (spec §7.1), and the supervisor proves the *link it was told*, never the run's existence.
Concretely, in this fixed order: `_owner_only(peer, namespace, capability)`; settlement identical to
`release` (every WRITE view `PUBLISHED`/`REJECTED`, no `intent.json` → `WORKSPACE_BUSY`); the live writer fd
this process opened (else `STALE_GENERATION`); then the invariants `target.session_id == caller.session_id`,
`target.parent_run_id == caller.run_id`, `target.run_id != caller.run_id` (else `INPUT_POLICY`). The commit is
one fsynced metadata replace: `active_actor := target`, `owner_namespace`/`generation`/`status`/`revision_id`
unchanged, a fresh `secrets.token_hex(32)` capability minted. **Generation is not advanced** — a handoff is
not a new write epoch — so existing pins and the child's views keep their generation. The old capability dies
with that replace (fresh work with it is `UNAUTHORIZED`, and the dispatcher's `op-<request_id>` reservation is
not a bypass) while Q75 replay of the same request id returns its own cached original reply.

**Both conditions that "would settle it" are answered.** (a) The grant moves by *replacing* it in the same
metadata write, so the old proof is dead the moment the new one exists — it is not revoked *before* and it does
not need to be: there is no window in which two mutator capabilities are live. (b) An unsettled
`SEALED`-but-unpublished view blocks a handoff exactly as it blocks `release`: both use
`_settle_owner`'s predicate, and `PUBLISHED`/`REJECTED` are the only settled states.

**Why not the round-1 alternative (a narrow read-only attester injected into the service).** It inverts the
E263 session→execution dependency, adds an `FA_STATE_ROOT` mount contract and filesystem IO on the hot path,
and buys no privilege boundary the controller cannot already cross: a compromised controller can already
`exec` as the owner.

**What this does not prove, and why that is acceptable.** The supervisor cannot verify that the named child
run exists. A controller that names a nonexistent run can therefore strand the workspace's own grant until
`release` or restart — self-inflicted denial of service, not escalation, because the caller must already hold
the single owner grant and the named target gains nothing the caller could not do itself. The crash window is
equally bounded: after the metadata replace and before the reply the workspace is `OWNED` by a namespace whose
capability nobody holds, and restart quarantines it exactly as for `acquire_writer`; the attempt is never
reconstructed from the journal.

**What would reopen it.** A requirement for cross-session or cross-workspace handoff (the invariants forbid
both), for nested depth limits enforced by the supervisor rather than by the workflow layer, or for a
supervisor-side proof of run existence — the last would mean deliberately giving the supervisor a session
store, i.e. reopening option (2). Implementation and evidence: SLICE2 STEP6/CT113, `tests/test_execution_handoff.py`,
register row `I03-LIVE-27`.

---

## Q86 — Which I03 E2E package path is canonical?

**Status: RESOLVED (2026-10-23) — canonical path is `worklogs/planning-topology-and-executable-contracts-loop/e2e/`.**

**Operator ruling.** Use the project-scoped package path, not repository-root `/e2e/`. Different projects
may reuse increment and case IDs; scoping under `worklogs/<project-slug>/e2e/` keeps their artifacts and
ownership separate. Move the package once and update its code, tests, schema, plan and documentation
references together. Do not retain a duplicate root package.

**Resolution evidence.** The package has been moved to the canonical path; checker/test paths, package
links, schema reference, active I03 plan and design note are aligned. No live result depends on the old
location. Historical evidence remains untouched.

**Options (historical).** A was to keep root-level `e2e/`; B was to use `worklogs/<project>/e2e/`.
The operator selected B.

---

## Q87 — How should I03-LIVE-26 describe sealing after E278 adds the local cgroup observer?

**Status: DEFERRED pending operator disposition (2026-10-23).** The other agent's I03 work is now merged and the E283 cgroup/handoff facts are available for review. The incoming branch refreshed the `I03-LIVE-26` oracle to describe the composed `OwnedCellTermination` path while keeping the case `PLANNED / UNEXECUTED` and requiring host proof of a real empty cgroup. No operator selection between the recorded options is present; live E2E remains deferred.

**The gap.** The E277 LIVE-26 oracle said `seal` refuses `TERMINALITY_UNKNOWN` until a cgroup observer exists and concluded a full stage could not be completed through the surface. E278 then added the cgroup-v2 reader and `OwnedCellTermination`; the composed service now installs that adapter. E278's evidence is explicitly local: the cgroup path and kernel `populated 0` were exercised with a doubled Docker seam, not a live container or approved-host run. The reconciled register row now says the composed path uses that observer, but still requires host proof that a real cgroup emptied; the live status remains `PLANNED / UNEXECUTED`.

**Impact.** The incoming wording corresponds to option A's clarification, but the recorded options have no operator disposition. Treating the merge itself as authorization would decide a planner question by implication; reverting it would also discard the other agent's work. The host must still prove the cgroup fact, and no row may be promoted from E278's local result.

**Options.**

- **(A) Clarify the oracle** to require `seal` success only after the approved host's real observer proves
  `populated 0`, with the exact fail-closed refusal retained for nonempty/unreadable/unknown state.
- **(B) Preserve the conservative current oracle** as a live-host blocker until the independent approved-
  host barrier proof exists, and record any full-stage success as follow-up evidence rather than relaxing
  the existing requirement.

**Operator disposition (2026-10-23).** Confirmed: `I03-LIVE-26` already exists in the package index and
master sheet as `PLANNED / UNEXECUTED`. At the time, defer the oracle question until the other agent's
work is complete. That work is now merged and its register refresh is recorded above; no follow-up
operator selection between A and B has been recorded, so this question remains pending. Keep the row
`PLANNED / UNEXECUTED`; the refresh is not a live result and does not authorize live execution.

No option authorizes live execution before I01–I03 are merged to `main` and deployed. Do not change the
case again until planner/user disposition.

---

## Q88 — How should I01 live obligations be mapped into final I03 acceptance?

**Status: RESOLVED (2026-10-23; operator selected A).** Final I03 acceptance still requires live-host
E2E for all project changes in I01–I03; resolution of the mapping does not assign a live verdict.

**Selected model: explicit I01-origin case IDs.** The project package now contains `I01-LIVE-01`,
`I01-LIVE-02`, and `I01-LIVE-03` in `worklogs/planning-topology-and-executable-contracts-loop/e2e/I01/`.
Their planned oracles cover (1) real skill/prompt → model-authored plan → parser/admission → verify,
(2) parser records/accessors and persisted workflow behavior, and (3) the precheck diagnostic matrix
and fail-closed coder-admission control. The separate I01 baseline maps all 42 declared I01 CTs and
D1a/D1b/D2/D3/D4/D5/D8 to these cases. D6 is excluded as I04-owned; D7 is excluded as historical E19
baseline disposition. Existing I02-origin/I03 baseline IDs and frozen snapshot are unchanged.

**Evidence boundary.** All three I01 cases are `PLANNED / NOT RUN`; no fixture/helper exists yet. STEP7
independent review must precede STEP8 fixture/helper implementation. No live E2E may run before I01–I03
are merged to `main` and deployed. The operator will supply host evidence for joint evaluation before
any result is marked.

**Historical options.** A was to add explicit I01-origin IDs; B was to reuse I02/I03 IDs only where the
oracle actually proves I01 behavior. The operator selected A. Q87/LIVE-26 remains separately deferred.

---

## Q89 — How does the wire `publish` express a plan (CANDIDATE) publish?

**Status: RESOLVED — operator selected option 1 with refinements R1–R6 (2026-10-30).** The contract decision is implemented at the component/test level in E288; production `run_workflow` composition remains fail-closed until the managed session supplies the trusted execution publisher. The original alternatives and rationale below are retained as history; E287 is the pre-implementation plan.

**The gap.** Two records settle the *semantics* of a candidate publish and neither settles its *encoding*.
Spec §5 (`i03-execution-workspace-spec-2026-10-15.md`, CANDIDATE grants) says: "On seal, validate bounded buffer with
existing pure I02 validators; **publish of CANDIDATE uses PLAN intent at the scoped canonical PlanRef path**, never
imports a candidate directory. Parent/model cannot choose a promotion destination." Increment SLICE3 STEP3 says the
wire route is "the existing `publish` with a CANDIDATE-view ledger, **not a new operation**". What exists today is a
route that cannot carry that shape:

1. `protocol._PUBLISH` payload is `{sealed_manifest_id: ^seal-[0-9a-f]{32}$, expected_base_revision: ^rev-…$}`, both
   **required** (`protocol.py:126`). A CANDIDATE view is never sealed — `seal_view` requires a stopped WRITE view with
   a terminal receipt — so the first key is inapplicable by construction, not merely unused.
2. The reply shape `_COMMITTED` is `{workspace_id, revision_id, tree_sha256, operation_id, projection_complete}`
   (`protocol.py:138`). `publication.PlanPublishResult` returns those **plus `plan_ref`**, and §5 makes that ref "the
   one a caller must record" — so the reply is missing the only field the controller needs.
3. `publication.publish_plan(authority, …, plan_ref, buffer, deadline)` takes both from its caller. On the wire neither
   is caller-supplied: the buffer is the candidate's ONE supervisor-owned staged file (E259,
   `candidate_scope.candidate_path`) and the ref is the one pinned in `candidate_scope.plan_ref` at `create_view`. The
   supervisor must therefore read both from the view it was handed, which is also what forbids a caller-chosen
   destination.

**Options.**
1. **(recommended) One operation, purpose-validated.** `sealed_manifest_id` becomes nullable and must be `null`
   exactly when the request's `view_ref.purpose` is `CANDIDATE` (a seal id there, or a null elsewhere, is
   `INPUT_POLICY`); the reply gains `plan_ref` (nullable; non-null only for a plan publish). `service._publish`
   branches on the purpose, proves the view through the authority, reads the staged buffer, and calls
   `publication.publish_plan` with the view's pinned ref. No bytes and no destination travel on the wire.
2. **Purpose-scoped payload members.** Add optional `expected_plan_sha256`/`plan_ref` payload keys and leave the reply
   alone. Closed-schema growth, and the controller would have to learn the new canonical hash from the journal record
   or a later `read` instead of from the reply that performed the change.
3. **A separate `publish_plan` operation.** Cleanest schema, but it contradicts STEP3's "not a new operation", takes
   `Operation` from 19 to 20 (route totality, register, and every derived count change), and re-creates the second
   plan writer the whole Q58/R3 line exists to delete.

**Impact of choosing wrongly.** Option 1 edits two closed v1 shapes for every client (one member's nullability, one
member's addition) but keeps one route, one reply and one writer. Option 2 splits the truth about which plan is
current across two places. Option 3 undoes the single-writer property by making the plan path a second operation with
its own reservation/replay semantics.

**Operator decision — option 1, with binding refinements (R1–R6).** The wire remains the single existing
`Operation.PUBLISH`. `sealed_manifest_id` is nullable only for a CANDIDATE `view_ref`: it must be null for
CANDIDATE and non-null for an ordinary sealed WRITE publication. PUBLISH receives its own closed reply schema
with nullable `plan_ref`; ordinary publication returns null, candidate PLAN publication returns the exact new
ref, and `INSTALL_PROJECT` keeps the original `_COMMITTED` shape.

- **R1 — closed-view proof and private buffer.** Candidate publication must use a view-capability proof that
  tolerates the already-closed view and read the private candidate buffer inside the authority transaction.
  `read_candidate`'s normal open-work path is not callable after closure.
- **R2 — view capability, not OWNER substitution.** Authenticate the candidate view grant and retain binding
  checks for `status == OWNED`, `active_actor == namespace`, and generation. Do not require or replace the view
  proof with the independent OWNER grant.
- **R3 — reply isolation.** Define a PUBLISH-only result containing nullable `plan_ref`; do not widen the
  `_COMMITTED` schema used by `install_project`.
- **R4 — dispatcher identity.** Thread the dispatcher's `op-<request_id>` through the PLAN intent and reply.
  Because `operation_id` is in the plan manifest hashed by `_derive_revision_id`, regenerate affected revision
  IDs and pinned expectations. Do not add a content-hash idempotency scheme; exact replay remains the supervisor
  journal's responsibility.
- **R5 — seal-equivalent barrier.** Candidate publishing requires a closed gate, no active work, and a matching
  `terminal.json`, followed by the existing I02 plan validators. `record_terminal` by itself does not drain work.
- **R6 — base pin.** Require `binding.current["revision_id"] == view_ref.base_revision` before committing the plan.

The existing candidate-buffer methods also need to be reachable through the existing `WRITE_FILE` route for a
CANDIDATE view, with exact `candidate_path` scope enforcement; this is transport for the already-authorized
buffer, not a new wire operation. Keep ordinary sealed WRITE publication unchanged. Delete the live
`plan_promotion.publish_plan_buffer` writer in the same cutover. Do not reopen options 2/3.

**Historical deferrals.** The question was raised after E273. E276 later delivered CT107 forward recovery; E277–E280 delivered the service composition and dependencies. E287 recorded the source-verified implementation plan. These entries preserve their state at the time and are superseded by E288 below.

**Implementation result (E288, component-level; no production activation).** The implementation now:

- applies the PUBLISH-only nullable `plan_ref` result and the strict seal-null/CANDIDATE cross-field rule, leaving install's `_COMMITTED` untouched;
- routes CANDIDATE buffer reads/writes through the exact scoped private-buffer methods, then publishes with the view capability through the closed-view-tolerant authority transaction, seal-equivalent barrier, I02 validators, base equality and dispatcher `op-<request_id>`;
- stages through `ExecutionClientPlanPublisher` and has `run_workflow`/`WorkflowContext` accept the publisher port; missing injection is a closed `prepare-failed`, not a local fallback;
- deletes `plan_promotion.publish_plan_buffer` and tests ordinary sealed publication separately.

The transport/service path has an end-to-end AF_UNIX test. Targeted checks: protocol/service 112 passed; workspace publication/recovery/purposes 135 passed; the full `test_verify_gate_live.py` bank 572 passed (with the workspace venv on `PATH`); Ruff check/format, Mypy (7 source files), compileall and `git diff --check` passed. Two targeted mutants were caught: removing the candidate base-revision comparison let the stale-base test publish, and replacing the PLAN manifest's dispatched operation ID broke the revision-ID assertion. No live-host run, frozen I03-LIVE-23 edit, CT/STEP tick, or claim of deployed readiness is made.

**Remaining composition boundary.** The ordinary CLI/session composition does not yet create or inject an `ExecutionClientPlanPublisher` with the managed namespace, workspace ID, owner capability and current revision. Until that SLICE4/managed-session integration exists, candidate repair/replan attempts fail closed; this option-1 contract is available only to a caller that supplies the trusted port. Do not treat the fake publisher used by controller tests as a production writer, and do not reconcile or rewrite I03-LIVE-23 without planner approval and later host evidence. This is recorded as the separate integration blocker Q90; it does not reopen Q89's wire decision.

---

## Q90 — Which managed composition supplies the trusted candidate publisher to `run_workflow`?

**Status: OPEN — implementation dependency; Q89's protocol contract is already resolved.**

**Context (source-verified).** E288 gives `WorkflowContext`/`run_workflow` an explicit `CandidatePlanPublisher` port and provides `ExecutionClientPlanPublisher`. The ordinary CLI/session composition currently has no `ExecutionClient` owner or publisher. `_session_manager_for_args()` supplies `workspace_preparer` but no `workspace_provisioner`; `RunContext` contains lifecycle IDs and paths, not managed execution identity or an `ExecutionBinding`; `_cmd_workflow()` passes lifecycle contexts to `run_workflow()` without a trusted publisher. The controller therefore fails closed when the port is absent; the host-path writer is deleted and must not be restored.

There is also a contract gap in the existing adapter: `ExecutionClientPlanPublisher` currently accepts and stores an OWNER capability, while I03 §7 requires a frozen internal `ExecutionBinding` with identity/client references but no token fields, and requires `ExecutionClient` alone to cache and select raw grants privately. The current `ManagedProvisioner` registration result supplies workspace/revision/tree identity, but registration is not itself the active run's OWNER grant. Bind only after the managed workspace is validated and the supervisor has supplied the current run's grant and revision. `_child_run_context()` allocates a fresh child `RunContext`; it does not yet establish child execution authority, which must follow the supervisor's handoff contract rather than reuse the parent binding.

**Impact.** Managed candidate repair/replan cannot yet publish through the new route from the ordinary CLI. The component, protocol and service paths are locally tested, but Q89 is not production-enabled and SLICE3 STEP3/SLICE4 remain open. Live host evidence remains deferred; I03-LIVE-23's frozen OWNER-grant oracle is not evidence for this route.

**Options for the planner/managed-session owner.**

1. **Preferred: use the managed lifecycle as the trusted identity boundary, with construction in its adjacent runtime composition.** After managed workspace registration and a fresh run admission, the managed composition validates the supervisor-backed workspace identity and obtains the current run-scoped grant/revision. It constructs a typed binding and publisher for that run. `SessionManager` remains responsible for lifecycle identity; it does not own/persist bearer capabilities. The publisher advances its confirmed base only from a confirmed PUBLISH result.
2. **Compose at the CLI boundary only as a placement variation.** The CLI may assemble the adapter only from the same validated typed binding supplied by the managed lifecycle. It must not discover, mint, reconstruct, or infer the namespace, workspace identity, grant, or base revision. Under this constraint option 2 is not a separate trust boundary; it is a different location for adapter assembly.
3. **Keep promotion disabled until that composition lands.** The current fail-closed port remains; no host writer or alternate protocol is reintroduced. This is the safe interim state, not production completion.

**Engineering recommendation (not yet a resolution).** Choose option 1 with the ownership boundary stated above. Thread the spec's explicit `ExecutionBinding` through `WorkflowContext` and `SessionState`; keep raw OWNER/view grants inside `ExecutionClient`; use the supervisor's confirmed identities rather than CLI path inference; and give each nested run a fresh binding established through the specified handoff. Keep the existing `CandidatePlanPublisher` seam as the controller port, but make its production adapter operate through the binding/client rather than hold a capability. Missing, stale, mismatched, or uncertain authority remains fail-closed; do not add a host-path fallback, ambient `ContextVar`, second writer, or new wire operation. This recommendation does not itself mark Q89 production-enabled or resolve the implementation owner/step.

**Evidence to plan (not executed).** Add deterministic lifecycle/service integration coverage for registration → run-scoped grant → binding → candidate PUBLISH, including a durable ledger append and the resulting authoritative revision. Negative cases should cover absent/stale/cross-run bindings, stale base, uncertain PUBLISH, and proof that raw grants do not enter `RunContext`, `SessionState`, events, or model-visible output. Plan any live E2E under the canonical `worklogs/planning-topology-and-executable-contracts-loop/e2e/` package; keep it deferred until I01–I03 are merged to `main` and deployed, then evaluate only with host evidence. Do not change frozen E2E baselines or substitute a host test for the ownership decision.

**Requested resolution.** Planner assigns the implementation owner/step and chooses the recommended option-1 architecture (or an option-2 adapter-placement variant that satisfies the same binding and token-custody contracts); option 3 remains active meanwhile.

**Resolution (2026-11-01, Q99, operator: "делай, как правильно по логике на будущее использование системы").** The custody
contract is **option A with the invariant written down**, not a re-architecture. The sentence above ("`ExecutionClient`
alone caches and selects raw grants") described a design SLICE7 deliberately did not build, and the reasoning that settled
it is about lifetime, not about hiding: a bearer capability should live with the component whose lifetime *is* the
authority's grant — `ManagedExecution` acquires the writer when the run opens and releases it when the run closes, and a
capability that outlives its release path is the defect, not a feature. Two consequences are now contract:

1. **One run, one grant, one holder.** `ManagedExecution` holds it; `BoundPlanPublisher` reaches it only through
   `managed`; the client stays stateless and is handed the grant explicitly for each operation. That makes every use
auditable at the call site, and the release has exactly one caller.
2. **The boundary is what must never leak, not what must never be reachable in-process.** No grant in `RunContext`,
   session state, events, logs or model-visible text; anything inside the trusted composition may hold it.

Option B (a private run-scoped grant store inside the client) was rejected on purpose: it would make the client stateful,
move `publish_plan`/`release` off their written STEP6-STEP7 contract, and still not hide the token from in-process
introspection — only from accidental reach, which is exactly what the reachability test now checks
(`test_the_writer_capability_lives_in_exactly_one_place`, one path per CLI-owned object, a second copy fails).

**Current-source audit (2026-11-02; E408; implementation remains open).** The older Q90 option text and the SLICE5
STEP2 draft predate the landed SLICE7 composition and need to be read with these corrections:

- `_drive_stage_with_managed_workspace` (`src/fa/cli.py`) creates the parent `PROJECT` WRITE view, calls `drive()`
  while that view remains live, and publishes/stops it only after `drive()` returns. A synchronous `invoke_workflow`
  therefore cannot hand off the writer from inside its handler until it has an explicit parent-view suspend/settle
  seam. After child return, the already-built registry still holds fixed-view `ClientWorkspacePort` and
  `ManagedBashExecutor` instances; there is no current parent-view reopen/rebind or resume marker.
- `_make_workflow_ctx_provider` does not receive the active `ManagedExecution`; its context has no managed binding.
  `run_workflow` called by `workflow_tool.handler` receives neither `managed_execution` nor `plan_publisher`.
  `_child_run_context` calls `SessionManager.begin_run` only. `managed_execution_for_run(child_context)` is not the
  nested-child acquisition path: it registers/acquires a writer, which would compete with the parent instead of
  consuming the HANDOFF grant.
- The existing authority route already supports the lineage needed for a child: a target namespace must carry the
  caller's `run_id` as `parent_run_id`; return is restricted to the exact recorded parent. `tests/test_execution_handoff_return.py::test_return_and_child_client_verbs_over_real_socket`
  proves a child grant opens a WRITE view, publishes a PLAN and returns the grant. `RunContext` has no parent field,
  so the nested composition must construct and retain the exact child `NamespaceRef` separately; do not broaden the
  seven exact `active_actor` comparisons unless a new source-backed test proves that necessary.
- The actual adapter is `BoundPlanPublisher(managed, binding)` (`src/fa/execution/composition.py`), not the older
  `BoundPlanPublisher(client, binding)` wording. A child publisher must reach the child-scoped `ManagedExecution`,
  whose grant was received by HANDOFF; it must not call the ordinary child writer-acquisition factory.
- `tests/test_execution_handoff.py::test_the_route_rotates_the_capability_and_reserves_exactly_one_record` proves exact same-request-id replay
  of HANDOFF with its original proof returns the recorded grant; a fresh request id with that old proof is rejected.
  A client-side reconciliation may therefore use only the same request id, payload, namespace and proof. If that
  remains indeterminate, do not dispatch the child, release the writer, invent a grant, or resume the parent on its
  stale view. Return to the parent only after a confirmed reverse HANDOFF and a fresh parent view. Preserve Q114's
  no-auto-PUBLISH-retry rule; do not change Q108 or legacy direct `fa workflow`.

The resolved contract is sequential single-writer ownership: settle the parent WRITE view before HANDOFF; dispatch
only after the child grant is confirmed; settle child views before reverse HANDOFF; then reopen the parent at the
returned revision and make the chat explicitly refresh its workspace understanding. The trusted stage/tool boundary
must provide suspend/resume and view rebinding without exposing grants through `RunContext`, session state, logs or the
model. Failure to prove either transfer is fail-closed and must not RELEASE an owner whose location is unknown. This
is a source-backed implementation contract, not a claim that Q90/CT108 or the live nested path is complete.

---

## Q112 — readiness-failure scope for managed `fa-entrypoint` auto-run

**Status: RESOLVED — operator selected `auto_run_only`; narrowly amended by Q118 (2026-11-02).** A failed
managed cell-local readiness check blocks active-workspace publication and `fa run`. The path may first create a
provisional, non-active manifest/DB and reserve exactly one provisioning run, as specified by Q118; that run ID
is never reusable. No workflow `event_log` events are appended on refusal. An explicit command override remains
available as a diagnostic path, including when `FA_AUTO_RUN=1`; it must not run the auto-run provisioner. When
auto-run is disabled, the existing standby behavior remains.

**Source conflict.** `scripts/fa-entrypoint.sh::_prepare_entrypoint_workspace` returned success after every
`workspace_bootstrap ensure` failure. The managed auto-run path then published `.active`, provisioned a
session, and launched `fa run`. At the same time, existing
`tests/test_fa_entrypoint.py::test_entrypoint_readiness_degradation_warns_and_continues` deliberately
requires a failed readiness check not to suppress an explicit command override. The planned R02 oracle's
phrase "no project command without backend" was broader than this existing distinction, while SLICE4 STEP2b's
fail-open removal names the managed CLI cutover rather than this shell entrypoint.

**Options considered.** (1) block managed auto-run only, preserving explicit command override; (2) block all
commands, including diagnostic overrides; (3) keep fail-open and narrow R02's contract. The operator selected
(1). Only a freshly created, unpublished clone may be removed after the refusal; a resumed workspace is
preserved.

**Implementation boundary.** Readiness must run inside the admitted managed EXEC cell; host-side
`workspace_bootstrap ensure`, a config-presence check, or HEALTH is not EXEC-readiness proof. On refusal, retain
the non-reusable run reservation/tombstone; do not publish `.active`, launch `fa run`, or append workflow events.
Cleanup may remove only unregistered session-owned workspace state and must never delete supervisor-registered
bytes. This contract does not claim the managed route is implemented or proven: R02 and S4P1 remain open until
their named production/host evidence exists. No Docker or live-host run is implied.

---

## Q113 — W0/S4P1 exit versus managed-negative dependency on W1

**Status: RESOLVED — strict applicable-row closure (option 2, 2026-11-02), with Q126-A/E469, Q131-C/E477, Q132-D/E481, and Q133-B/E482 scope amendments.** W0 remains open until every active/applicable S4P1 row passes its named managed-backend production-caller oracle. Q126-A retires R23 as NOT APPLICABLE TO MANAGED W0 only after its two-path audit and supported-route cleanup; it is a disposition, not a test PASS. Q126-A's initial active set was R01–R22 and R24–R28 (27 rows). By explicit Q131-C, E477 removes the dormant R21 helper/export and retires R21 as NOT APPLICABLE TO MANAGED W0, not PASS. Q132-D/E481 defers R24 to W2 (OPEN, not PASS/N/A); Q133-B/E482 then defers R25/R26 to W2 and R28 to W1, also OPEN and not PASS/N/A. The current active W0 gate is R01–R20, R22, and R27 (**22 rows**). W1 may start only after those 22 pass; R28 must pass before W1 closes, and R24–R26 must pass before W2 closes. These scope updates do not authorize early closure of any other active row.

**Source conflict.** The increment's execution order is W0 → W1 → W2; W0 includes S4P1's inventory rows, and the S4P1 table says to close each row with a current source line, caller, and nodeid. The inventory note separately says no S4P1 row closes until its named negative oracle runs against a managed backend, identified as SLICE4 STEP2/W1. Current source makes the dependency concrete: R27's `_cmd_run` builds the tool registry without `workspace_io`, and the planned live-chat canonical-tree negative is absent; R28's host-bootstrap isolation negative also depends on managed Bash; Q112/R02's separate backend-availability oracle is likewise not supplied by `workspace_bootstrap ensure`.

Therefore, if W0 requires every S4P1 *row* to be closed, its stated evidence gate requires W1's managed composition first. If W0 requires only inventory completion (source/caller/current or planned nodeid and explicit dependencies), the negative-oracle executions can remain open and run during W1 without changing the wave order. The current plan text uses both formulations; this record does not decide between them.

**Options for the operator/planner.**

1. **W0 means inventory readiness.** Complete the source/caller/oracle map for every S4P1 row; leave rows explicitly OPEN until the managed negative oracles run in W1. W0 may exit on that inventory criterion, then W1 begins in the written order. This clarifies the wave exit without marking any S4P1 row closed or weakening its acceptance test.
2. **W0 requires row closure.** Keep every managed-negative result as a W0 exit criterion; authorize a managed-composition prerequisite before W0 exit or explicitly re-sequence the required W1 work. The dependency order changes and must be recorded before implementation.

**Resolution (2026-11-02; operator selected option 2, strict row closure).** W0 cannot exit until each S4P1 row's named negative oracle passes. The operator authorizes the managed-composition prerequisite needed to run those oracles before W0 exits; remaining W1 regression/cutover work stays after W0. This permits only the required prerequisite, not early row closure or live-host claims.

**Guardrails.** No row is PASS/CLOSED without its named negative oracle; no live-host evidence is inferred from local source checks; no Docker is started before the planned post-merge host phase. Keep W0 open while prerequisite work and row oracles are incomplete.

---

## Q114 — How is an indeterminate candidate PLAN PUBLISH settled and reclaimed?

**Status: RESOLVED — operator selected option 1/A (2026-11-02); implementation and acceptance remain OPEN.** This architecture direction is for the managed-run path and does not authorize changing legacy direct `fa workflow` behavior in the current scope. R25 remains OPEN until its uncertainty/lifecycle acceptance is implemented and reviewed. At the time of this Q114 decision, no wire change for candidate-PUBLISH settlement/reclaim was authorized; the later Q108 scope clarification below is limited to Q60 inventory metadata and does not alter this decision.

**Source-grounded behavior (E407, 2026-11-02).** `ExecutionClient.publish_plan` makes one PUBLISH request. If its result is indeterminate, it sets `uncertain=True`; its `finally` deliberately skips `_release_view`, and the exception leaves the method without returning the locally held `ViewRef` or view grant. `ManagedExecution` has no pending-candidate/recovery field. The CLI's `_cmd_workflow` `finally` still calls `_settle_writer_release`/`ManagedExecution.close` after `run_workflow` returns.

A real local UDS composition probe injected `DURABILITY_UNKNOWN` at the start of `WorkspaceAuthority.publish_candidate_plan` (before its commit body). The controller classified it as `PlanPromotionError("durability-unknown", replaced=True)` and sent no second PUBLISH or candidate-view RELEASE. However, `WorkspaceAuthority._has_unsettled_views` treats a view as unsettled only when `access != READ`; the CANDIDATE purpose is an `Access.READ` view. Consequently the CLI's owner RELEASE succeeded: `workspace.json` became `AVAILABLE`, while the view record and supervisor-private `candidate` bytes remained on disk with the view in `STOPPING`. The probe initially expected `OWNED` and failed (pytest exit 1); a temporary diagnostic expectation of `AVAILABLE` allowed the full oracle to pass (1 passed). The probe test and its extra import were removed afterward; no test now codifies this behavior as desired.

`_closed_candidate_reader` requires the binding to remain `OWNED`, the active actor to match, and a live writer. After release, the old candidate view cannot publish; a later writer claim advances generation. `release_reader` needs the view ref and capability, which the unwound client call does not expose or persist. `_load` performs workspace/intent recovery but does not rehydrate or sweep persisted candidate-view records. Thus the current composition demonstrably permits an orphaned, private, non-publishable candidate view after an uncertainty-classified result. The PLAN itself may be either old or committed on a genuinely uncertain post-send outcome; do not assert old PLAN bytes as a general uncertainty invariant.

**Impact.** R25's determinate refusal proof remains valid, but uncertainty handling does not yet define an end-to-end settlement/reclaim path. Repeated ambiguous candidate PUBLISH operations can leave private view records/buffers after the run owner is released; the authority has no caller-held view proof to publish or explicitly release that record. This affects failure recovery and resource lifecycle, not Q108 wire semantics, and is a demonstrated code/plan gap rather than a presumed R27/R28 blocker.

**Bounded options for planner/operator.**

1. **Retain run ownership and pending proof in the trusted managed execution.** Keep the exact candidate `ViewRef`, view grant and PUBLISH request identity privately in `ManagedExecution`; do not release the writer while that operation is unresolved. Reconcile using exact same-request replay where the existing journal permits, then release only after the candidate is proven `PUBLISHED`/`REJECTED`. Define process-death behavior explicitly (likely workspace quarantine/recovery); no host fallback and no model-visible grant.
2. **Move reconciliation/cleanup to durable supervisor authority.** Persist enough operation↔candidate linkage for startup/runtime recovery to prove whether commit occurred, settle the candidate view accordingly, and only then permit owner release. Reuse existing exact operation replay if sufficient; if a new query/message or wire representation is required, stop at Q108 and obtain that decision rather than inventing it.
3. **Accept orphaned candidate views under an explicit bounded lifecycle policy.** Define safe retention/expiry and garbage collection, but delete/reject only when journal and canonical PLAN/intent evidence prove the outcome; if outcome is still unknown, keep an authority-level fence rather than making the workspace AVAILABLE with an unpublishable view. This option requires explicit storage/availability tradeoff approval.

**Engineering recommendation (not resolved).** Prefer option 1 for the in-process trusted-controller boundary already selected under Q61: the same `ManagedExecution` that owns the writer should own the unresolved candidate proof, keep the owner fenced, and reconcile without a second writer or new worker/IPC architecture. Confirm exact replay inputs and process-death/quarantine behavior against the operation-journal contract before implementation.

**Resolution (2026-11-02; operator selected option 1/A).** For managed runs, the run-scoped `ManagedExecution` is the holder of pending candidate proof and owner authority. An indeterminate publication must not trigger a host write or release the writer before reconciliation. Do not automatically retry PUBLISH; use only the exact-request replay/reconciliation semantics already permitted by the operation journal, and preserve fail-closed state if the result remains unknown. If the process dies before reconciliation, the workspace remains unavailable/quarantined for recovery; this selection does not promise autonomous restart recovery. No second writer, worker/IPC architecture, or new wire operation for candidate-PUBLISH settlement/reclaim is authorized by this Q114 resolution; the separate Q108 scope clarification below governs the Q60 inventory metadata operation only.

**Scope and remaining work.** Legacy direct `fa workflow` behavior is unchanged in the current scope. Its observed orphan-view behavior remains an R25 acceptance gap, not an approved policy. The managed-run implementation must separately prove each uncertain candidate-saga phase (including lost CREATE_VIEW response), pending-handle ownership, no premature RELEASE, exact replay safety, and restart/quarantine behavior before claiming Q114 implementation complete. Do not assert that uncertainty means unchanged PLAN, do not treat `DURABILITY_UNKNOWN` as determinate refusal, and do not claim R25/S4P1 uncertainty coverage from the decision alone.

**Q108 scope clarification (2026-11-02).** After the operator separately selected Q108 route B, the no-new-wire-operation constraint above is clarified as applying to Q114 candidate-PUBLISH settlement/reclaim. The only separately authorized wire addition is Q60's bounded `LIST_PROJECT_ARTIFACTS` metadata operation under protocol v2, on a pinned READ/PROJECT view. It does not query or settle PUBLISH, alter writer retention, introduce automatic retry, change process-death quarantine, or otherwise reopen Q114. This scoped exception is not implementation or acceptance evidence.

---

## Q115 — Canonical roadmap section heading for Q60 bootstrap

**Status: RESOLVED — operator delegated the engineering choice; option A selected (2026-11-02).**

**Source conflict.** The managed-acquisition specification §7.1 named the required sections as “Intent and Out of scope”, while the existing supervisor-side `execution.publication.render_bundle` and its fixtures required `## Out-of-scope`. The spelling is part of the model-authored bootstrap input contract; silently accepting both would weaken the strict two-heading schema, while changing it affects the existing renderer and tests.

**Options.** (A) Use the literal Q60 form `## Out of scope` and update the existing renderer plus its regression fixtures. (B) Preserve `## Out-of-scope` and amend the Q60 managed-acquisition contract to match.

**Resolution.** The operator delegated the choice and said to use the recommended option if spaces caused no issue. Select A: the space is valid Markdown heading text and does not affect file paths, IDs, metadata, or bundle identity except as part of the intended body bytes. The renderer accepts exactly `## Intent` and `## Out of scope`; `## Out-of-scope` remains rejected. Existing three-file rendering, controller-owned metadata, bundle hashing and install authority are unchanged.

**Scope.** This resolves only the heading spelling. It does not close the managed-acquisition parser/resolver/runtime, authorize accepting alternate section forms, change legacy `fa workflow`, or provide live-host ledger append evidence.

---

## Q116 — Increment bootstrap metadata: is `slug` an allowed frontmatter key?

**Status: RESOLVED — operator selected option B (2026-11-02).**

**Source conflict.** The managed-acquisition spec §7.0 names the canonical increment metadata keys as `Increment-ID`, `Roadmap-ID`, `status`, `slices`, and `shipped`; the existing `execution.publication.render_bundle` additionally emitted `slug`. A strict metadata parser following §7.0 would reject the renderer's own output unless one side changed.

**Options.** (A) Amend the schema to allow optional `slug`, validate it against the canonical relative path, and preserve the renderer output. (B) Preserve the exact §7.0 field set and remove `slug` from the increment frontmatter emitted by the renderer.

**Resolution.** The operator selected B. Increment metadata uses only the five listed fields; project/increment slugs remain encoded in the canonical relative paths and are not duplicated in increment frontmatter. Roadmap `slug` remains part of the roadmap schema. The renderer and literal fixtures change in lockstep.

**Scope.** This resolves only the increment metadata key set. It does not authorize path guessing, weaken YAML parsing, or close managed selection/bootstrap runtime, admission, ledger append, supervisor integration, or live-host evidence.


## Q117 — What managed prerequisite can prove EXEC availability before entrypoint project effects?

**Status: RESOLVED — operator directed implementation now, using existing seams and avoiding HEALTH-only proof (2026-11-02).** The narrow injection seam alone is insufficient; pursue the actual managed provisioning/cell-readiness path under Q113 rather than adding a second HEALTH or wire-operation surface. `REGISTER_WORKSPACE{create:true}` and the existing PROVISIONING view/provisioner are the intended seams. Q118 resolves the temporal conflict by permitting one provisional, non-active run reservation before cell-local readiness. No S4P1 row or W0 is closed by this direction.

**Source evidence (2026-11-02).** R02's named oracle is `test_entrypoint_runs_no_project_command_without_backend`, which requires no host project effects when managed execution is unavailable. `scripts/fa-entrypoint.sh:193–239` currently clones/configures/runs workspace readiness before invoking the manager provision command at `:270–290`. E415 fixed the module CLI's missing provisioner injection, but it is necessarily reached after those shell effects. A proposed early `Operation.HEALTH` check is insufficient: `src/fa/execution/service.py::_health:570–582` returns `self._authority.ready` and does not attest EXEC worker/cell readiness. The existing remote provisioner also rejects `ProvisionMode.PROVISION` at `src/fa/execution/composition.py:470–474` until the SLICE3 publication join. Moving the current session-provision command ahead of readiness would conflict with Q112's accepted readiness-before-session-provisioning order.

**Impact.** A config-presence or HEALTH-only gate can block an initially absent supervisor, but it cannot prove that the managed EXEC path can own/run the workspace, nor eliminate the host-side project effects and race window. Strict R02/W0 closure therefore requires a managed new-root/session composition and a cell-local readiness route, or a change in the already ratified wave ordering. No runtime implementation or oracle weakening is authorized by this question itself.

**Resolution options.**

A. **Keep the strict target (recommended):** expand Q113's pre-W0 managed-composition prerequisite to include the production new-root provisioning join and the minimum cell-local entrypoint readiness route needed for the R02 negative oracle. Preserve Q112's explicit-command and readiness refusal behavior; do not count HEALTH alone as proof. This is a broader dependency than the earlier narrow injection seam and must be source-mapped before implementation.

B. **Reopen the schedule, not the safety contract:** leave R02 and W0 OPEN until the planned W1 SLICE4 STEP2 provisioning/readiness cutover, then run every named oracle. This revises Q113's strict pre-W0 closure timing but does not weaken the no-project-command contract.

The operator selected option A: preserve the strict R02 target and expand the pre-W0 managed-composition prerequisite to include the production new-root join and minimum cell-local readiness route. No option permits marking R02 complete from a health-only check. Implementation and all named oracles remain OPEN.


## Q118 — May managed readiness create provisional run state before the session becomes active?

**Status: RESOLVED — operator selected option A (2026-11-02).** Permit only the existing lifecycle's provisional,
non-active session manifest/DB and one provisioning-run reservation before managed cell-local readiness. The
reservation is durable and its run ID is a non-reusable tombstone if provisioning/readiness fails. Failure must
not publish `.active`, launch `fa run`, or append workflow `event_log` events. Explicit-command override and
standby behavior under Q112 are unchanged.

**Source conflict.** Q112 requires a readiness failure to stop managed auto-run before session provisioning, `.active` publication, or `fa run`; the live proposal L-ENTRY-1 expects no manifest, `session.db`, run binding, run directory, or `event_log` append on readiness refusal. But the existing managed lifecycle seam needs an admitted `RunContext` for provisioning and cell execution: `SessionManager._new_session` creates a `provisioning` manifest and `SessionDatabase`, calls `begin_run`, then invokes `workspace_provisioner` and readiness (`src/fa/session/manager.py:350–391`). A cell-local bootstrap/readiness operation therefore needs namespace/run authority before the session can be promoted. No current API supplies an EXEC-capable cell for an unprovisioned session without this run context; HEALTH is insufficient (Q117).

**Historical impact before resolution.** The existing manager/provisioner ordering creates provisional state
before readiness. Preserving Q112's former zero-state wording would have required a separate preflight identity and
lifecycle, adding a second orchestration surface and risking unbound run IDs. Q118 resolves this by authorizing the
narrow provisional state; it does not weaken the no-host-project-command target.

**Resolution options.**

A. **Amend Q112 narrowly (recommended for lowest surface).** Permit a provisional, non-active session manifest/DB and one reserved provisioning run while managed cell-local readiness executes. On readiness failure, never publish `.active`, never launch `fa run`, never append workflow `event_log` events, retain the provisioning run ID as a non-reusable tombstone under existing reservation rules, remove only the unregistered session-owned workspace/session namespace, and never delete supervisor-registered bytes. Update L-ENTRY-1/L-ENTRY-5 to assert these exact state transitions. Explicit command override and standby behavior remain unchanged.

B. **Preserve Q112's zero-session-state rule.** Design and authorize a distinct preflight namespace with a durable source of identity/run reservations, a managed root/view, and a no-session cleanup/quarantine contract; only after readiness succeeds may the ordinary SessionManager create the user session. This avoids the provisional user session but creates a second lifecycle seam and should be scoped explicitly before coding.

The options above are retained as decision history; option A is selected. This resolves only the temporal contract,
not the implementation or evidence. R02/S4P1/W0 remain OPEN until the managed EXEC readiness route and named
negative oracles are demonstrated.


## Q119 — How should the wrapper preserve workspace selection when moving to the isolated controller?

**Status: RESOLVED — operator selected option A (2026-11-03); full Q119-A command/workspace matrix, hostile-CWD/PYTHONPATH wrapper-to-installed-controller composition, and R01 Arena-local W0 closeout are recorded in E462. Deployed-host acceptance remains separate and NOT RUN.**

**Source evidence (2026-11-03).** `scripts/fa:36–45` reads the path named by `sessions/.active` and supplies it as Docker Compose's `-w`; `:76–82,178–181` dispatch ordinary product commands as `first-agent fa`. `pyproject.toml:97–100` maps that console script to `fa.cli:main`, not the isolated `fa.controller_entry`. The wrapper's help is currently fail-closed, so the existing ordinary route is preserved pending this decision. In `src/fa/cli.py`, `_session_manager_for_args` resolves workspace roots using `FA_WORKSPACE_ROOT`, an explicit `--workspace`, or its `/sessions`/CWD defaults; parser-level `--workspace` options exist for `inner-loop-smoke`, `run`, `workflow`, `stats`, and `authoring-check`, but workspace selection is not uniform across product commands. The required isolated entry must run from a trusted CWD; using `.active` as Compose's process CWD is not an acceptable substitute for deciding product workspace authority.

**Impact.** Replacing only the executable while preserving Compose `-w` does not establish the trusted-CWD contract and may alter commands whose workspace comes from an explicit parser argument, session manager, or CWD. Conversely, removing `-w` without a replacement can silently point CWD-relative commands at the trusted installation directory rather than the active project. Do not wire ordinary commands to the isolated entry or change CLI/parser defaults until the workspace policy and command coverage are explicit. All wrapper help remains disabled until the installed-controller help seam is available.

**Resolution options.**

A. **Command-aware explicit workspace adapter (recommended for a narrow, fail-closed migration).** From the trusted controller CWD, resolve/validate the active workspace through the accepted session authority, pass it only through each command's existing explicit workspace interface, and fail closed for any project command whose workspace semantics are not mapped. Add a source-backed command matrix and negative oracles before enabling each route. This preserves active-workspace intent where an existing contract supports it, but may temporarily refuse unmapped commands.

B. **Common controller-level workspace context.** Define and implement one validated, controller-owned active-workspace context consumed by all project-oriented commands, including those currently dependent on CWD. The wrapper passes a reference/context input, not a project CWD. This can preserve a uniform implicit-active behavior, but requires a broader CLI composition and trust-boundary change with explicit validation and fallback rules.

C. **Remove implicit active-workspace selection.** Invoke the isolated controller from trusted CWD and require explicit workspace/session selection for every project command. This is the smallest implicit-authority surface, but intentionally changes the legacy wrapper behavior and needs user-facing migration/error handling.

**Target-contract audit (2026-11-03).** The authoritative I03 execution/workspace specification §2 requires `/opt/fa-venv/bin/python -I -m fa.controller_entry` to run from a trusted CWD, not from the active project, and the inventory target says project selection must be carried explicitly. A command-aware adapter can meet that boundary; `docker compose exec -w .active` cannot. However, A as originally phrased is only a safe *migration strategy*: keeping project commands permanently refused because they are unmapped would not demonstrate the full target behavior if those commands are in R01's required product surface. Temporary refusal is a rollout safeguard only. Before R01 acceptance, provide a source-backed matrix for every ordinary wrapper product command, preserve each supported command's intended workspace/session semantics through an authorized explicit interface, and either classify non-project commands as workspace-independent or add their required explicit contract. Do not weaken existing per-command session resolution or silently fall back to trusted CWD.

The separate accepted boundaries remain: direct `fa workflow` is the legacy manual/controller path; `invoke_workflow` is chat-only; managed `run_workflow` admission must precede coder dispatch. This wrapper routing question does not authorize changing those paths or conflating them.

**Engineering recommendation (selected).** Option A with full-coverage acceptance: resolve/validate the active selection through session authority, invoke the isolated controller from trusted CWD, map every product command to its existing or explicitly added workspace/session interface, and fail closed only for unmapped commands during migration. Close R01 only when the command matrix shows no required project command was silently redirected or left permanently unavailable, and wrapper-to-installed-controller composition plus hostile-CWD/PYTHONPATH tests pass. Before implementation, prove `.active` is an authorized session reference rather than trusting its file contents alone. The operator selected this policy; option B is not the chosen contract.

**Resolution (2026-11-03; operator selected A, with the target-contract refinement above).** Keep the controller CWD trusted and carry project selection explicitly. Preserve `.active` intent by validating it through session authority and mapping every required product command to an explicit workspace/session or path interface. Fail closed for unmapped routes only during migration; R01 acceptance must not leave required product commands silently redirected or permanently unavailable. Relative path inputs whose prior meaning depended on active CWD must be resolved explicitly against the validated selection, not against trusted controller CWD. Direct `fa workflow` remains the legacy manual/controller path; `invoke_workflow` remains chat-only; managed `run_workflow` admission precedes coder dispatch.

**Source audit (2026-11-03; resolver primitive implemented, production caller still OPEN).** `scripts/fa-entrypoint.sh:_publish_active_workspace` publishes only a workspace path; the managed entrypoint's path is `/sessions/$SESSION_ID`, but `.active` contains no session ID. `src/fa/cli.py:_session_manager_for_args` uses `FA_WORKSPACE_ROOT`, an explicit workspace, `/sessions`, or CWD; it does not read `.active`. The `run` and `workflow` parsers expose optional `--workspace` and `--session-id`; the manager's `resolve_workflow_workspace` and `create_or_attach_session` validate explicit inputs but do not provide reverse lookup. New `SessionManager.resolve_active_session_for_workspace` in `src/fa/session/manager.py` now performs a read-only unique-active-manifest and DB-identity lookup for an explicit workspace; it does not mutate timestamps, provision, prepare, or reserve a run. Its result is not a lease: the future caller must revalidate through the ordinary attach/run lifecycle. Tests cover a path whose basename differs from its session ID, no side effects, no/ambiguous owners, containment/missing paths, and missing DB. This helper has **no CLI or wrapper caller yet** and is not R01 production-caller evidence. Therefore do not derive session ID from `.active`'s basename or pass the active path alone and assume the intended session is selected. At the time of this audit, CWD-based project surfaces included `chunk`'s path argument and `inner-loop-smoke`, `stats`, and `authoring-check` workspace defaults; Q127-A later reclassifies `inner-loop-smoke` as a dev-only disposable-workspace diagnostic outside the active managed matrix. The remaining user-supplied relative config/plan/manifest/model paths still need explicit interpretation. `inject`, `help`, `selfcheck`, `routing-check`, `probe`, and `conformance` have no project-workspace selector in their current parser and require classification/path-default review in the full matrix. `egress-proxy` is classified as Compose-internal under Q120-A and is refused by the host wrapper before generic product dispatch; direct in-container behavior is unchanged.

**Source command/path matrix (current parser and callers; 2026-11-03).** Host verbs from `scripts/fa` remain host/Compose routes; parser-known commands below describe only the default `first-agent fa` route. A future adapter must preserve path meaning without setting the controller CWD to the project:

| Command | Current workspace/session behavior | Inputs whose old CWD meaning must be preserved explicitly |
| --- | --- | --- |
| Host verbs: `logs`, `proxy-logs`, `status`, `up`, `down`, `restart`, `rebuild`, `shell`, `update`, `clean-rebuild`, `commit-traces`, `sessions` | Host/Compose or host scripts; do not route through the controller. | Preserve existing host argv and working-directory rules; not product workspace selection. |
| `chunk` | No workspace option; the positional `path` is opened relative to process CWD. | Positional path: anchor relative values to the validated active workspace (or require absolute input). |
| `inner-loop-smoke` (Q127-A: dev-only, not an ordinary active-workspace route) | Requires an explicit absolute existing `--workspace`; rejects wrapper-selected active state and targets overlapping managed/source roots before writes. Without `.active`, `scripts/fa` routes it through the installed controller from trusted CWD. | `--workspace` must identify a disposable/non-managed directory; relative `--input`/`--output` remain rooted under that explicit directory. |
| `run` | Optional `--workspace`/`--session-id`; standalone `_cmd_run` keeps its existing manager/CWD defaults. Under wrapper `.active`, Q128-B validates workspace identity through SessionManager before lifecycle dispatch. | Omitted selection maps to the active manifest owner. Explicit relative workspace is resolved from active root; any existing unique owner is reused when ID is omitted, and explicit `--session-id` is preserved/revalidated. An unowned path may start a session only under the approved root and disjoint from all active/provisioning roots; overlapping/nested paths fail before allocation, with supervisor physical-root overlap as final authority. Relative `--config` anchors to former active CWD. |
| `workflow` | Optional `--workspace`/`--session-id`; lifecycle goes through SessionManager. The `scripts/fa` wrapper invokes the installed controller from trusted CWD and, when `.active` exists, resolves it to the manifest-owned session before attach. Direct in-container `fa workflow` remains the same CLI/pipeline route. When `--plan` is supplied, workspace preflight still requires an explicit workspace/session. | Explicit workspace/session pair; relative `--plan` is admitted under the validated workspace and relative `--config` is anchored to the prior active CWD. |
| `inject` | Read-only inspection; no workspace/session allocation; the wrapper's generic product route invokes the installed controller. | With wrapper `.active`, relative `--config` is resolved from the validated active root; omitted/default config stays parser-declared. |
| `help` / global `--version` | `fa help` and global `--version` use the installed controller; wrapper top-level no-args/`--help` remains its shell usage path. | No project path; help/version render from installed controller code and do not resolve `.active`. |
| `selfcheck`, `routing-check`, `probe`, `conformance` | No project-workspace selector; wrapper generic product dispatch invokes the installed controller. These consume model configuration/provider state. | With wrapper `.active`, user-supplied relative `--config` resolves from the validated active root; defaults remain parser-declared absolute paths. `probe`/live `conformance` retain their existing provider side effects. |
| `stats` | `--workspace` defaults to CWD when run directly; with wrapper `.active`, omitted/relative workspace is resolved under the unique manifest-owned workspace for the dead-zone fallback. Source discovery remains rooted in FA state/session authorities; explicit `--session-id` still selects data independently. `--global-history` and `--calibration` remain workspace-independent. | Preserve workspace and session-selection semantics separately; never inject or replace `--session-id` merely because `.active` exists. Absolute explicit workspace stays explicit; relative explicit workspace is contained under the validated active workspace. |
| `authoring-check` | Standalone `--workspace` defaults to CWD; `--manifest` is passed to the checker. | Under wrapper `.active`, omitted `--workspace` selects the manifest-owned workspace; relative `--workspace` is contained beneath it. Relative `--manifest` resolves from the active root (the former active CWD), not a relative `--workspace` subdirectory; absolute paths stay explicit. Invalid active selectors or relative escapes fail before marker/checker reads. |
| `egress-proxy` | Not an agent-workspace or operator-wrapper route: Compose runs it as the separate `fa-egress-proxy` service (`docker-compose.fa.yml` command); `scripts/fa` now refuses it before generic product dispatch under Q120-A. | No wrapper-side path interpretation. Compose remains the sole production launcher; direct in-container invocation and its service-mounted `--models`, `--secrets`, and `--token-file` inputs are unchanged. |
| `clean` / unknown subcommand | `scripts/fa clean` delegates, but current `fa.cli` has no `clean` parser; unknown commands are rejected by argparse. | Preserve the existing rejection unless a separate command contract is approved; do not invent workspace behavior. |

This is the full parser-known command inventory and a source-based CWD/path checklist, not proof of the future argv adapter. Q127-A (2026-11-05) reclassifies `inner-loop-smoke` as dev-only and excludes it from ordinary active managed-workspace acceptance; its manual disposable-workspace contract is recorded in the table and E456. In particular, the adapter must not add a `--session-id` to `stats` automatically, must not run `egress-proxy` in `first-agent`, and must preserve `run`/`workflow` lifecycle admission. Relative-path normalization, controller help, and command-specific argv insertion still need caller tests.

**Acceptance boundary.** Q120-A now classifies the proxy route and `scripts/fa` refuses it before product dispatch; this closes only that route-classification question, not an R01 row. Host-only commands and direct in-container `fa` remain unchanged. R01, S4P1, and W0–W2 remain OPEN until command-specific normalization/mapping, production integration of the resolver with lifecycle revalidation, wrapper-to-installed-controller composition tests, and row-specific gates are satisfied.


## Q120 — Is `fa egress-proxy` a wrapper route or a Compose-owned service entry?

**Status: RESOLVED — operator selected A (2026-11-03); wrapper implementation and targeted tests are recorded in E436. R01 remains OPEN.**

**Source conflict (as observed before the Q120-A wrapper change).** `src/fa/cli.py` exposes `egress-proxy` as a CLI subcommand and `_cmd_egress_proxy` starts a listening server while reading model, secret, and token files. `docker-compose.fa.yml` already launches that command in the dedicated `fa-egress-proxy` service with service-mounted paths. At the source audit, `scripts/fa` had no `egress-proxy` host branch, so the generic default dispatch sent `fa egress-proxy ...` to `first-agent fa`, not the proxy service. The agent service intentionally does not receive the real provider secrets, and starting a second listener in the agent is not the documented deployment route.

**Impact.** Q119-A requires a complete matrix, but routing this command to the installed agent controller would violate the component boundary; blindly routing it to the already-running proxy service could start a duplicate listener. Its `--models`, `--secrets`, and `--token-file` path arguments also have service-specific rather than active-workspace semantics. No code should infer the intended behavior from the parser command's existence alone.

**Resolution options.**

A. **Treat it as Compose-internal (recommended).** `fa egress-proxy` is not an operator `scripts/fa` product route. The wrapper fails closed with a stable “managed by Compose” diagnostic; Compose remains the sole production launcher in `fa-egress-proxy`. Direct in-container invocation and service configuration stay unchanged. This explicitly classifies it out of the wrapper product surface rather than leaving it mapped to `first-agent`.

B. **Authorize a separate proxy-service wrapper operation.** Define a dedicated, non-duplicate service-management action (for example, inspect/restart through Compose) and its argument/path contract. Do not implement it as `docker compose exec ... fa egress-proxy`, since the service already runs that server. This expands host wrapper surface and needs its own no-effect/production-caller tests.

**Resolution (2026-11-03; operator selected A).** `fa egress-proxy` is Compose-internal, not an operator `scripts/fa` product route. The host wrapper now refuses it with exit 2 and a stable “managed by the fa-egress-proxy Compose service” diagnostic before Compose or product dispatch. Help forms still fail closed through the wrapper-help diagnostic. Compose remains the sole production launcher; Compose configuration and direct invocation inside the proxy container are unchanged. No duplicate `docker compose exec ... egress-proxy` route is added.

**Acceptance boundary.** Q120 is resolved and the wrapper route behavior is covered by targeted refusal/no-dispatch and help-position tests (details in E436). This closes only the Q120 route-classification decision, not an R01 row; R01, S4P1, and W0–W2 remain OPEN.

---

## Q121 — What managed subagent contract and workflow/chat execution architecture should R13 adopt?

**Status: RESOLVED — operator superseded the earlier W0 option A with full R13 implementation in W0 (2026-11-04).** This records implementation scope, not acceptance: R13 remains OPEN until its production callers and row-specific oracles pass; Q113 still requires every S4P1 row before W0 closes.

**Clarified contract (operator, 2026-11-04).** The two primary surfaces are ordinary `fa run chat` and the heavier workflow invoked from that chat. A subagent may be called directly from ordinary chat and from workflow `planner` and `coder` roles. The stable contract is: one restricted generic toolset shared across parent roles in the first slice; stateless Bash (no inherited stateful parent shell); only the delegated task as conversational input, not the parent's transcript/context overhead; and a completion report returned to the caller. The parent role determines the task/prompt; per-role flags gate admission and do not create different child toolsets. Tool policy and scoped execution authority may be supplied as system/runtime metadata, but must not become replay of parent history. The operator also wants a limited, read-oriented same-session chat while a workflow continues; this is a requested experience to evaluate, not a ratified I03 requirement.

**Operator refinement (2026-11-04).** All subagents are read-only for existing project files; a subagent may write new artifacts/notes only in a private scratch area. The subagent does the investigation/analysis; the main agent receives the report and applies/persists it. This avoids concurrent mutations. The legacy role names are not capability profiles; the subagent is generic, and the parent role (chat/planner/coder) determines the task. The coder subagent is disabled by default; each role has its own capability flag, default off, in the config file. The child uses the chat provider chain.

**Decision.**

- **R13/W0 sequencing — full behavior in W0 (operator supersedes prior option A; equivalent to full-child option B).** Implement the real generic managed child now for ordinary chat and workflow planner/coder callers; do not ship a temporary deny-only placeholder. The child uses the S-C read-only/scratch contract and the minimum Q122 per-view profile binding needed for a stateless READ child. Through the production caller, the W0 negative oracle performs one bounded child READ `EXEC` request to a real local supervisor configured to refuse before worker/cell launch: `exec_requests=1`, `exec_allowed=0`, `cell_launches=0`, `host_subprocesses=0`, `proxy_credentials=0`, `project_writes=0`. The positive local composition proves that an approved supervisor can run the read-only child and return a bounded report. Missing read-only profile or disabled role flags fail closed without parent-shell/host fallback. W1 remains after all W0 rows close and contains no second implementation of R13.
- **Subagent execution — S-C restricted first rollout + private scratch.** The subagent receives a pinned READ view of the latest published revision and a writable private scratch for new artifacts/notes. It cannot write to existing project files. There is no writer handoff and no concurrent mutation. The main agent applies/persists the report. The coder main agent retains the write capability; the coder subagent is read-only/scratch for diagnosis and is disabled by default. S-A writer handoff remains the next step if a write-capable coder subagent is explicitly funded; it is outside this slice.
- **Per-role capability flags.** Add `subagent.chat.enabled`, `subagent.planner.enabled`, and `subagent.coder.enabled`, all default `False`, to the existing `feature_flags:` block, plus the master `subagent_spawning_enabled` (default `False`). The managed tool is available only when the master and the parent-role flag are both true.
- **Observer — W-A first, W-B target, W-C reject.** W-A is a separately addressable read-only observer attachment for the same session/workflow; it reads bounded durable status/event rows and pins the latest published revision. W-B is the post-I03 product target: a durable workflow child plus a same-session read-only chat lane, with a restricted observer profile, event cursors, revision pins, owner/capability separation, admission/close behavior, and explicit tool-registry restriction. W-C is incompatible with the one-writer contract. The observer is post-I03 and is not an implicit side effect of adding subagents.

**Plan.** The detailed plan is [notes/r13-managed-subagent-plan-2026-11-04.md](r13-managed-subagent-plan-2026-11-04.md). The wave impact is recorded in `increments/increment-03-execution-workspace-foundation.md` and `roadmap.md`. The R13 inventory row is updated in `notes/i03-execution-call-inventory.md`.

**Acceptance boundary.** This direction does not close R13. The named test `test_subagent_commands_carry_no_proxy_credential` is still absent. R13 remains OPEN until the managed-backend negative oracle passes through the production caller. W0 remains OPEN until every S4P1 row's named negative oracle passes. Q123 is RESOLVED by the full-child-in-W0 decision; R13 implementation and acceptance remain OPEN until tested. W1 starts only after W0 closes. The observer remains post-I03. No runtime change, test, or row closure follows from this entry.


## Q122 — How should the supervisor support both interactive parent stages and non-interactive read-only child cells?

**Status: RESOLVED — option A (profile set per view), operator selected 2026-11-04; implemented and locally accepted in R13/W0 (2026-11-04).** Global W0 remains OPEN until Q113's remaining row oracles pass; do not start W1 before that exit.

**Selected architecture — profile set per view, no new service/authority.**

- **`ServiceConfig`:** add `read_only_profile_id: str | None`; keep `view_profile_id` as the write profile; validate both against `config.profiles`; require the read-only profile to be non-interactive (`interactive is False`) and the write profile to be interactive (`interactive is True`). The supervisor identity digest must bind both profile definitions and the role mapping (`view_profile_id`, `read_only_profile_id`). Current `profile_set_sha256()` hashes profile definitions only, so update the canonical identity and health checks; changing the role mapping with the same profile set must change the identity.
- **`WorkspaceAuthority`:** replace the single `self._view_profile` with `self._profiles: Mapping[str, ExecutionProfile]`, `self._view_profile` (write), and `self._read_only_profile`; add `view_profile(view_ref)` that reads the view record's `profile_id` and returns the profile. `create_view`/`pin_reader` select the profile based on access/purpose: READ -> read-only profile; WRITE -> write profile. The view record gets `"profile_id": profile.profile_id`; the `_VIEW_RECORD` schema gets `profile_id`; `_view_record_compat` fills the default write profile id for old records. `admit` uses `view.record["profile_id"]` to select the profile and validates `payload["profile_id"]`, `payload["timeout_ms"]`, and `profile.interactive != (payload["session_id"] is not None)`. The `approved_profile` property remains the write profile for backward compatibility.
- **`CommandReceipts._profile(view)`:** use `self._authority.view_profile(view)` instead of `approved_profile`; the receipt's `profile_id`/`image_digest` bind to the view's profile; `require_binding` checks the view's profile.
- **`OwnedCellTermination`:** take a `profile_resolver` callable (or a `profiles` mapping + `view_profile` resolver); use the view's profile in `stop_cells`/`cells_terminal`; the `SupervisorService` passes `self._authority.view_profile`. The `ViewStopper` passes the resolver; no new entity.
- **`SupervisorService`:** select `self._view_profile` (write) and `self._read_only_profile` (read-only) from `config.profiles`; pass both to `WorkspaceAuthority`; pass the resolver to `OwnedCellTermination`.
- **CellBackend/recovery:** replace every view-specific use of `approved_profile` with `view_profile(view)`, including episode lookup, CANCEL, PTY control and startup reconciliation; keep `approved_profile` only as a write-profile compatibility property.
- **`ManagedExecution`:** add `read_only_profile: ExecutionProfile | None`; `managed_execution_for_run` selects it; the child runner uses it. If `read_only_profile_id` is absent, W1 child admission fails closed before view/EXEC admission; never fall back to the interactive write profile.
- **`ManagedBashExecutor` read-only variant:** use the read-only profile; `session_id=None`; READ view; the supervisor's `admit` validates it against the view's profile.
- **`ViewRef` wire unchanged;** the view record's `profile_id` is internal; no new wire operation.

**Why this is the minimal surface.** It reuses the existing `ServiceConfig.profiles`, `ViewRef`, view record, `ExecutionProfile`, `ManagedBashExecutor`, `CellBackend`, `WorkspaceAuthority`, `ViewStopper`, and `OwnedCellTermination`; it adds one config field (`read_only_profile_id`), one internal view-record field (`profile_id`), and a profile resolver; it does not add a new service/authority or a new wire operation. Option B (separate authority) adds a second authority and a shared-state problem; option C violates stateless Bash.

**Tests.**

- `test_view_profile_binding`: READ view -> read-only profile; WRITE view -> write profile; `admit` validates the view's profile; a write profile on a READ view is rejected; a read-only profile on a WRITE view is rejected.
- `test_view_record_profile_compat`: old record without `profile_id` -> default write profile; new record -> its profile.
- `test_owned_cell_termination_profile`: read-only view's cell stopped with the read-only profile; write view's cell with the write profile.
- `test_receipt_profile_binding`: receipt's `profile_id`/`image_digest` match the view's profile; `require_binding` passes.
- `test_service_config_read_only_profile`: read-only profile must be non-interactive; write profile interactive; config validation; changing role assignment changes the supervisor identity digest.
- `test_backend_uses_view_profile`: READ and WRITE views use their own profile for episode lookup, CANCEL/PTy control, receipts and terminality/recovery; no interactive fallback for a READ child.

**Impact.** Q122's per-view profile work is pulled into R13/W0 so the real child has a non-interactive READ authority. The observer remains unaffected and post-I03.

**Acceptance boundary (updated 2026-11-04).** Q122 per-view profile binding and its reader/view/backend/service regression coverage passed in the R13-local suite. This closes Q122's implementation acceptance for the R13/W0 local row; it does not close global W0. Q113 still requires every S4P1 row before W0 exits or W1 starts. Live-host acceptance remains reserved for the final wave.

## Q123 — What must R13/W0 prove when the managed subagent route is deny-only?

**Status: RESOLVED — operator selected full desired R13 behavior in W0 (2026-11-04), equivalent to option C below; this supersedes Q121's earlier deny-only option A.** Q113 remains strict: the R13 production caller must exercise a real child-managed EXEC refusal with row-specific no-effect evidence. The actual child runner, non-interactive per-view profile, and bounded report path are part of this W0 R13 slice; no temporary route-only denial is accepted as completion.

**Source-verified conflict.** In the current managed registry, the legacy
`fs_spawn_subagent` builder is only added when `workspace_io is None`; the
managed role-registry path has no managed child executor and currently skips
the legacy builder (`src/fa/inner_loop/profiles.py:198-220, 469-474`). A pure
deny-before-exec route can prove unavailable/no host/no token through `drive_session`,
but cannot by itself prove that the supervisor refused an EXEC. Sending a request
from the parent's interactive/write executor would not prove stateless READ-child
behavior and is not an acceptable substitute.

**Resolution options.**

A. **Zero child EXEC requests.** Keep Q121 option A strictly deny-before-exec;
prove the actual production caller invokes the registered route and assert
`exec_requests=0`, `exec_allowed=0`, `cell_launches=0`, `host_subprocesses=0`,
`proxy_credentials=0`, and `project_writes=0`. This requires an explicit
R13-specific adjustment to Q113/W0: a production-caller route denial, rather
than supervisor refusal, is the managed negative for this row.

B. **One supervisor-rejected child EXEC.** Keep Q113 strict; specify an exact
production R13 caller edge, view/access/profile and bounded request that reaches
the real supervisor and is rejected before any cell/worker launch. It must not
reuse the parent's interactive shell/profile. This may require bringing a minimal
Q122 profile-binding prerequisite into W0 or defining another existing-authority
denial seam; decide the dependency impact explicitly before code.

C. **Real child in W0.** Implement enough of W1's real child lifecycle to submit
the read-only EXEC and observe supervisor refusal. This expands W0 and changes
Q121 sequencing; do not do it without explicit re-sequencing authority.

**Historical recommendation (superseded).** The operator chose full child behavior in W0 to avoid a deny-only phase followed by a second implementation. The exact refusal path is now the real child Bash tool on its non-interactive READ view; it must use one bounded EXEC request and the real supervisor must refuse before cell launch in the negative oracle.

**Impact (updated 2026-11-04).** Q123's full-child contract is implemented and accepted for R13's Arena-local W0 row: chat/planner/coder production callers pass configured-supervisor negative and approved-local positive oracles with row-specific counters. R13's local row is CLOSED; global W0 remains OPEN under Q113 until unrelated S4P1 rows pass. Do not start W1. Final-wave host evidence remains NOT RUN.


## Q124 — What enforceable writable-scratch quota should the managed R13 child receive?

**Status: RESOLVED — operator selected A (64 MiB per child, 2026-11-04).**
Q121/Q123 authorize full child behavior in W0 and Q122 selects per-view READ
profiles. Runtime implementation and acceptance remain OPEN until this selected
quota is mechanically enforced by the supervisor.

**Source-verified gap.** `ExecutionProfile` enforces memory, PID and command-time
budgets but has no scratch-size field. `ExecutionProfile.create_spec` mounts the
supervisor-owned view scratch as a writable bind at `/scratch`. A bounded Bash
command can still fill the backing filesystem. The cap and the over-limit result
must be deterministic and enforced at the supervisor/container boundary, not by
the model or a post-hoc size check.

**Resolution options.**

A. **64 MiB per child (recommended).** Enforce an ephemeral per-cell `/scratch`
quota at the supervisor boundary. On exhaustion, the command receives the
filesystem's deterministic limit error, the child reports a structured bounded
failure, and the parent remains the only project writer.

B. **256 MiB per child.** Same enforcement and fail-closed behavior as A, with a
larger allowance for generated notes/artifacts.

C. **Operator-configured quota.** Add a required positive scratch limit to the
approved READ profile/config; refuse child admission if the supervisor cannot
enforce it. This adds an operator/deployment setting and a profile-identity
change.

D. **Other.** Specify a different hard limit and required overflow behavior.

**Resolution (2026-11-04; operator selected A).** Each managed child gets
a hard 64 MiB writable `/scratch` quota enforced at the supervisor/container
boundary. Exceeding it must produce an observable bounded command/child failure;
cleanup is required after confirmed terminality. If the selected cap cannot be
enforced, fail child admission closed. No host-backed fallback or project write
is permitted.

**Acceptance boundary (updated 2026-11-04).** R13's Arena-local W0 acceptance
for the chosen limit is CLOSED: approved production-caller tests verify the
64 MiB bounded scratch write, nonzero inner overflow attempt, bounded child
report evidence, exact tmpfs request, read-only project mount, confirmed local
terminal cleanup, zero project writes, and no host fallback. The local API peer
and worker do not prove Docker-daemon ENOSPC or tmpfs release. Actual
ledger-append and deployed-storage E2E remain NOT RUN and are reserved for the
final wave; they are not a W0 Docker prerequisite. Q113 global W0 still requires
all other row oracles, and W1 remains blocked until that gate closes.

## Q125 — How should the optional R12 runtime satisfy Q113's W0 production-caller oracle?

**Status: RESOLVED — option A selected by the operator on 2026-11-05. R12's Arena-local W0 row is CLOSED; global W0 remains OPEN under Q113.** This is a W0 acceptance/scope resolution, not authorization to add a runtime caller.

**Source-verified gap (2026-11-04).** R12 covers the optional public
`fa.runtime` import, the optional FastAPI PTY server, and
`RemoteRuntimeExecutor`. The scope-reduction decision classifies the server as
cell-internal/optional and explicitly says the future remote client is not a
security component: it has no approved-profile launch, ownership fencing,
process-tree stop, or sealing. A source search found no production reference to
`RemoteRuntimeExecutor`; the `run_bash` production resolver wraps
`session.pty_pool` in `InProcessPtyExecutor`. The existing R12 C1 tests stub the
HTTP transport and are component coverage, not evidence of a managed execution
caller. On 2026-11-04 the focused bank ran with CPython 3.13.16: 9 passed and 6
C1 tests skipped because the runtime-server extra is deferred. Thus the current
record has no non-skipped R12 managed-backend negative oracle through a
reachable production caller, as Q113 requires.

**Resolution options.**

A. **Keep the runtime optional; narrow R12 to the reachable production boundary.**
Amend Q113's R12 oracle to a local test through the actual managed CLI/chat
caller with the optional server unavailable, proving the managed refusal and
zero host fallback. Treat HTTP client/server tests as component-only; make no
claim that `RemoteRuntimeExecutor` is wired or secure. Specify the exact caller,
nodeid, and no-effect counters before implementation.

B. **Keep Q113 strict and defer R12 pending a separately approved integration.**
Do not add a caller in this step. First define an approved production composition
that makes the runtime reachable through existing managed execution authority,
then implement and test its row-specific refusal. This keeps W0 open until that
work is authorized and completed; `RemoteRuntimeExecutor` must not itself become
a second management/security authority by implication.

C. **Explicitly defer/exempt R12 from the W0 all-row exit.** Amend Q113 and the
increment's W0 exit to record R12 as an outstanding deferred acceptance item;
keep R12 OPEN and do not describe the revised W0 exit as satisfying the original
all-row condition.

**Resolution and acceptance boundary (2026-11-05).** The operator selected option A: keep the HTTP runtime optional and narrow R12 to the existing managed production boundary. The Arena-local oracle is `tests/test_execution_composition.py::test_r12_production_managed_chat_never_uses_remote_runtime_when_server_unavailable`; it drives the real `fa run --role chat`/managed Bash caller to a local UDS supervisor refusal with the optional app absent, and asserts non-retryable `execution_unavailable`, `BACKEND_UNAVAILABLE`, zero remote-runtime construction/run, HTTP-server starts, host fallback/PTy, proxy credentials, cell launches, and project writes. Its producer-selector and `_cmd_run` caller-edge mutants are killed and restored. R12's local W0 row is CLOSED on this scoped evidence. The existing HTTP tests remain component-only; this does not claim `RemoteRuntimeExecutor` is wired or secure, nor certify the optional server. Live E2E remains NOT RUN until the final wave after W3. Global Q113 W0 remains OPEN until every other S4P1 row passes; W1 has not started.

## Q126 — What is the disposition of the legacy R23 worktree row?

**Status: RESOLVED — Option A implemented; R23 is RETIRED / NOT APPLICABLE TO MANAGED W0 (2026-11-06; E469), not PASS.** The two-path call-graph audit found no product caller for the dormant isolated Git-worktree producer; the factory and actual `SessionState` caller refuse isolated mode. The distinct legacy host-runner was removed from supported product registries. Managed R13 remains the only supported subagent route, and its real caller still fails closed without a host fallback. Shared/artifact safeguards and direct legacy characterization tests remain. At E469, Q113 gated the 27 applicable rows R01–R22 and R24–R28. Subsequent Q131-C/E477 retires R21 as NOT APPLICABLE TO MANAGED W0 (not PASS); at E477 the then-current active set was 26 rows, R01–R20, R22, and R24–R28. Q132-D/E481 deferred R24 to W2 (still OPEN, not PASS/N/A), initially leaving 25 active W0 rows. Q133-B/E482 then defers R25/R26 to W2 and R28 to W1, also OPEN and not PASS/N/A; the current 22 active W0 rows are R01–R20, R22, and R27. Global W0 remains OPEN until all 22 active rows pass; R28 is required before W1 closes, and R24–R26 before W2 closes.

**Source-verified scope.** `IsolatedWorktreeManager.create_subagent_workspace:196–248` contains host Git operations, but no current production caller of that method was found. `SessionState.create_subagent_workspace` calls `ensure_subagent_artifact_root` directly; the legacy `spawn_subagent` reaches that artifact-root method, not the isolated manager. `WorktreeManagerFactory.from_flags` accepts only `shared` and refuses `isolated`; `IsolatedWorktreeManager` is retained for tests/backward compatibility. The managed child is R13 and does not use this manager. Do not treat this source fact as a disposition or row closure.

**Options.**

A. **Retire R23 as legacy.** Record that the managed child is R13; R23 is a historical host-worktree candidate, not a managed route; close/retire the row with a disposition note. No host-Git oracle is required for the managed path.

B. **Keep R23 as a historical candidate.** Keep the row OPEN; require a separate host-Git negative oracle if the operator wants to preserve the legacy worktree path. It is not the managed child and does not block R13.

**Recommendation (not a decision).** A. The managed child is R13; R23 is legacy; retiring it avoids a false dependency and a host-Git oracle for a path the managed product does not use. If the operator wants to preserve the legacy worktree path, B is the safer historical record.

**Operator direction (2026-11-05; historical, superseded below).** Defer the disposition and continue with other independent R rows. Keep R23 OPEN and do not remove it from Q113's all-row W0 exit; global W0 cannot close while this remains unresolved.

**Operator decision (2026-11-06).** Select Option A: retire R23 as a legacy worktree candidate and move all supported subagent scenarios to managed R13. The proposed `RETIRED / NOT APPLICABLE TO MANAGED W0` disposition is not a test PASS. Before applying it to Q113's active-row count, inspect the two distinct legacy paths and remove unsupported host-runner routes from supported product registries without deleting shared/artifact safeguards or weakening R13 fail-closed behavior. Until that scoped implementation and evidence are complete, R23 stays OPEN in the strict W0 exit; Q113's all-required-rows rule is unchanged.

**Acceptance boundary (E469; current denominator amended by E477/E481/E482).** Q126's disposition and narrow supported-route cleanup are complete. R23 is retired from the managed W0 active set and is not a PASS; R13's prior local close remains separate. At E469, global W0 remained OPEN on 27 active applicable rows; Q131-C/E477 later retires R21 separately, not as a PASS, leaving 26 active rows at E477. Q132-D/E481 then defers R24 to W2 (OPEN, not PASS/N/A), initially leaving 25 active rows. Q133-B/E482 defers R25/R26 to W2 and R28 to W1, also OPEN and not PASS/N/A; the current W0 active set is 22 rows, R01–R20, R22, and R27. Global W0 remains OPEN until all 22 pass; W1 has not started, R28 must pass before W1 closes, and R24–R26 remain required before W2 closes. No Docker/live-host or deployed-host acceptance is claimed. See [`R23/Q126-A call-graph closeout`](r23-q126a-callgraph-closeout-2026-11-06.md).

## Q127 — What is the allowed workspace contract for `inner-loop-smoke`?

**Status: RESOLVED — option A approved by the operator on 2026-11-05; implementation and local verification recorded in E456.** The historical failure remains valid evidence; the accepted contract removes active managed smoke from the ordinary product surface rather than making its writes managed.

**Observed production-caller conflict (2026-11-05).** `fa inner-loop-smoke` builds a baseline registry for the selected workspace and persists smoke state/events and related artifacts directly under that workspace; this is not an admitted managed-workspace write through the supervisor's one-writer boundary. A local production composition attempt selected a real manifest-owned active workspace, ran smoke with only the provider-facing `run_session` stubbed, then invoked the actual workflow lifecycle/SessionManager attach. Smoke created workspace-local state, and the subsequent managed attach was refused with `workspace_corrupt: managed provisioning refused: CORRUPT_STATE`. This is a real cross-command failure, not a test-helper-only observation. E454's isolated selector test did not exercise the subsequent lifecycle attach and is superseded by E455.

**Approved option A and implemented boundary.** The operator described `inner-loop-smoke` as one of the first CLI commands for basic checks and “closer to legacy than to a needed feature,” then explicitly approved A. The command is therefore classified as a legacy/dev-only diagnostic and is excluded from Q119's ordinary active managed-workspace matrix. `scripts/fa` now refuses before Compose whenever `.active` is non-empty (conservatively, even if the file is stale); without `.active`, it routes only to the installed isolated controller. The CLI requires an explicit absolute existing `--workspace` and refuses before registry/artifact creation when `FA_WRAPPER_ACTIVE_WORKSPACE` is set or the resolved workspace overlaps the configured managed workspace root or canonical source root. This preserves the one-writer boundary without adding a host fallback or second writer. Direct smoke behavior remains available only against an explicit disposable path outside those protected roots.

**Options.**

A. **Classify smoke as a dev-only disposable-workspace diagnostic.** Explicitly exclude it from Q119's ordinary active-workspace product-command acceptance. Refuse wrapper invocation when `.active` identifies a managed session; permit only a clearly identified disposable/non-managed workspace. Preserve the direct diagnostic only under that boundary. This requires the operator to approve the product-surface reclassification; it is not implicit in the current plan.

B. **Keep smoke in the ordinary product matrix and make it managed.** Route all project reads, writes, Bash, smoke/event state, attempt history, and learning-trace effects through the existing managed authority/admitted workspace view, with explicit publication/cleanup semantics and no host fallback or second writer. Then re-run the full production-caller composition sequence and prove a following managed attach remains valid. This may require prerequisite R-row work; do not weaken W0 to fit the command.

C. **Keep smoke as an explicit disposable-workspace operation without active-session defaulting.** Define an explicit input/output contract for a disposable copy and prove that canonical managed workspace bytes/state are unchanged. This changes current semantics and requires operator approval plus Q119 matrix updates.

D. **Provide another explicit contract.** The operator may specify a different disposition, but it must preserve the W0 one-writer boundary and state whether smoke remains a required ordinary product command.

**Operator decision (2026-11-05).** Option A is selected. The diagnostic remains manually usable on an explicit disposable/non-managed workspace; it is not required to run against an active managed workspace.

**Acceptance boundary.** Q127's policy choice is resolved and the approved local refusal/dispatch boundary is implemented and verified in E456. This does not close R01 or any other W0 row, does not resolve Q126/R23, and does not authorize W1 or live-host acceptance. R01 still requires the remaining Q119-A command/workspace matrix, hostile-CWD/PYTHONPATH checks, and its other DoD.

## Q128 — How should wrapper `run --workspace` resolve against an active owner?

**Status: DECIDED — the operator selected option B on 2026-11-05; E461 records implementation and its initial compatibility-run evidence. E462 records successful standard CPython 3.13.16/installed-controller verification and R01 Arena-local W0 closeout.**

**Source-backed ambiguity.** With `FA_WRAPPER_ACTIVE_WORKSPACE` set, `_apply_wrapper_session_workspace` first resolves the active manifest/DB owner, then currently assigns a relative `--workspace` as `active_session.workspace_path / Path(value)` but leaves `args.session_id` unchanged. `_cmd_run` reaches `_resolve_cli_run_context`, which calls `SessionManager.create_or_attach_session(session_id=None, workspace_override=...)` when no ID was supplied. That enters the new-session path, which may create a provisional manifest, DB, and run before the managed provisioner settles workspace ownership. Thus `--workspace .` does not currently mean a read-only alias for the already-selected active session; it can enter a second-session lifecycle against the same path. An unowned relative child path also raises the policy question of whether nested new managed roots are allowed. No second writer may be introduced, and no path-basename session-ID inference is allowed.

**Operator clarification (2026-11-05).** The operator's conceptual model is that the workspace is the persistent physical directory/git tree, while a session is an accumulating agent-context binding across consecutive `fa run` calls. Repeated runs in the same active session match the current implementation: one manifest/DB session owns exactly one `workspace_path`, and each run is separately bound in that session. Correction to my earlier source interpretation: `SessionManager._read_manifest` accepts only `active` and temporary `provisioning`, and no session close/deactivate transition was found. Therefore multiple historical session identities on the same workspace at different times are **not proven/currently supported by the inspected lifecycle**; a single session spanning multiple workspace paths is also not supported. The operator's sequential-session model is a plausible future contract, not an R01 behavior to invent here. R01 will only reuse a current unique owner and create sessions for a distinct disjoint unowned workspace under selected option B.

**Options.**

A. **Resolve existing manifest-owned paths only.** Resolve a relative workspace against the validated active root, then require it to have a unique manifest/DB owner via SessionManager. When `--session-id` is omitted, use that owner's identity; preserve an explicit ID and let lifecycle revalidation reject a mismatch. Reject unowned/ambiguous relative destinations before lifecycle effects. This makes `--workspace .` reuse the current context without a second session and permits selecting another already-managed workspace.

B. **Owner-aware reuse plus safe creation for a distinct workspace.** If the normalized path has a unique active owner, reuse that owner when `--session-id` is omitted and preserve/revalidate an explicit ID. If unowned, permit new-session creation only when the destination is inside the approved workspace root and is disjoint from every active managed workspace (neither equal, nested, nor an ancestor); refuse overlap before session/DB/run creation. A same-path new context remains unavailable while the prior owner is active; sequential reuse after release remains possible. Supervisor registration remains the final independent owner check.

C. **Reject relative `--workspace` whenever wrapper `.active` exists.** Require omission to use the active owner, or an absolute explicit workspace/session selection under the existing CLI contract. This is fail-closed but narrows the former relative-path interface.

D. **Other explicit contract.** The operator may define another behavior, but it must specify identity resolution, unowned destinations, effect ordering, and the no-second-writer proof.

**Engineering recommendation (not a decision).** B best matches the workspace/session distinction while maintaining one active owner per physical workspace. At minimum, the exact active path (`--workspace .`) must reuse its active manifest/DB owner, never start a second session. Creating a session for another unowned relative path requires a new pre-effect overlap oracle because SessionManager currently checks exact-path ownership, not ancestor/descendant overlap.

**Operator decision (2026-11-05).** Option B selected: reuse an existing unique owner; permit creation only for a distinct unowned workspace within the approved root and disjoint from active/provisioning managed workspaces. Preserve/revalidate explicit `--session-id`; exact active path (`--workspace .`) reuses the current owner. No second session on an actively owned path. The separate conceptual desire to retire one session and start another on the same workspace is outside this R01 decision because the current manager exposes no close/deactivate transition.

**Acceptance boundary (E462 verification update).** Q128-B's composition, workspace/session matrix, and targeted mutations were re-run under CPython 3.13.16; the final related R01 bank passed **270 passed, 12 ShellCheck-only skipped, 1 expected xfail**. Q128 does not alter Q126/R23. R01's Arena-local W0 row is CLOSED by E462, but global W0 remains OPEN because other rows, including deferred Q126/R23, remain open. W1 has not started; no live-host acceptance or final-wave ledger append is claimed.

## Q129 — What is the managed contract for workflow eval's advisory project diff?

**Status: DECIDED — Option A, managed sealed-revision metadata (2026-11-06).** R16's Arena-local W0 row is closed per E466/E468: the production caller, local refused/no-effect oracle, and producer/caller-edge mutation evidence passed and were revalidated after remote-branch integration. This is not Docker/live-host acceptance; global W0 remains OPEN. Q126-A's R23 retirement disposition is verified in E469 and is NOT a test PASS. The operator retained the current roadmap. The current eval remains an LLM judgment, mechanical verify remains separate, and the future L1/L2/L3 successor remains deferred.

**Initial source-backed constraint (before E466).** At question opening, `workflow_controller._eval_evidence_block` requested `git diff HEAD --stat`, `git diff HEAD`, and `git status --porcelain` through `_git_output` against `ctx.workspace`. The workspace snapshot excluded `.git` (`execution/workspace.py::_Capture._excluded`), while managed publication exposed only a tree digest (`StagePublication.tree_sha256`); the then-existing `WorkspacePort` had bounded file reads/writes and a narrow artifact listing, but no arbitrary revision enumeration/diff. Running Git in the cell was not equivalent because `.git` was absent, while simply dropping the advisory evidence would change eval input. E466 resolves this gap with the selected managed sealed-revision metadata operation and removes controller-side project Git.

**Recorded managed metadata contract.** Option A is selected as a read-only v2 `DIFF_REVISIONS` operation over retained sealed revisions in the same workspace. The target is the authenticated `READ/PROJECT` pinned view; the base is a retained revision ID. The authority compares complete manifest entries and returns only sorted `path` plus `added|modified|deleted`, `total_changes`, and an explicit `truncated` bit, capped at 128 returned records. No file bytes, host paths, project Git, or workspace mutation cross this operation. The workflow captures the coder's managed base immediately before stage dispatch and the published/current managed revision after it. The eval block receives path metadata and directs the judge to `fs_read_file` for relevant current file bodies. Missing, refused, malformed, timed-out, or uncertain metadata is explicitly **unavailable**, never “no changes”; no host Git fallback. This contract preserves the current LLM-eval/mechanical-verify split and does not deliver the deferred successor.

**Operator decision (2026-11-06).** Keep current roadmap and proceed with the bounded managed metadata contract above. Option B (retiring evidence) and Option C were not selected. The actual `fa workflow` production-caller, Arena-local no-effect oracle, and producer/caller-edge mutation evidence are complete per E466. This local acceptance does not imply Docker/live-host acceptance or global W0 closure.

**Options (historical; A selected).**

A. **Add an authority-owned sealed revision-diff contract.** Define and implement a bounded API over the before/after immutable workspace revisions, without Git or host-path access. Specify added/modified/deleted path semantics, textual/binary and symlink handling, deterministic ordering, size limits/truncation, and how the eval prompt represents unavailable/oversized evidence. The production workflow must bind the coder's base and published revision and use this managed result. This preserves file-change context but requires a new authority/client contract and tests.

B. **Retire the advisory file-diff evidence.** Remove stat/diff/status from eval input and explicitly state that eval receives plan/verification context only. Preserve the workflow and all other evidence. This is a product behavior change and requires operator approval plus updated tests/DoD; the controller must still have no host Git route.

C. **Other explicit contract.** The operator may specify another design, including any required change to snapshot policy, provided it preserves managed authority, no host fallback, one-writer semantics, and a production-caller no-effect oracle.

**Acceptance record (2026-11-06).** E466 and both R16 inventory entries record the inspected `cli._cmd_workflow` → workflow controller → stage caller, the production-path Arena-local refused/no-effect oracle, and killed producer/caller-edge mutations. The local UDS result is not Docker/live-host acceptance. R16's Arena-local row is closed; global W0 remains OPEN, and W1 must not start until every required W0 row passes.

---

## Q130 — What complete managed snapshot should drive IntentGuard without controller Git?

**Status: RESOLVED by operator policy (2026-11-06); R19 Arena-local W0 row CLOSED by E473.** Runtime IntentGuard is retired from every production `fa run` path; no active-writer snapshot/API is required. E473 supplies the named production-caller oracle and killed producer/EDGE mutants for R19 only. This does not close global W0 or authorize W1; Q113 remains strict until every applicable W0 row passes.

The source findings, missing-snapshot analysis, and options below are the historical E472 state. The selected policy and current acceptance boundary are recorded after those options.

**Source-to-caller trace.** `IntentGuard._default_git_runner` (`src/fa/inner_loop/hooks/intent_guard.py:272–281`) executes `git diff --cached --name-status` against `repo_root`. `_project_call` (`:166–203`) also resolves/stat-checks the controller's canonical path (`Path.resolve()`/`is_file()`) to classify A/M. The managed `cli._cmd_run` composition reaches `build_registry` → `_build_run_hook_registry` → `IntentGuard`; it passes only `managed_workspace: bool`, not the admitted `WorkspacePort` or a managed snapshot provider. `drive_session` reaches `HookRegistry.dispatch` before each gated tool execution. `managed_subagent.py` has a separate observe-only IntentGuard instance and must be included in the final caller inventory.

**Current tests and gap.** `tests/test_intent_guard.py::test_intent_guard_silently_allows_when_git_fails` injects a failing runner and explicitly asserts allow; it is component-only and proves neither absence of host Git nor a managed snapshot. The proposed `tests/test_intent_guard.py::test_intent_git_failure_never_bypasses_view_admission` is absent. No production-caller R19 nodeid currently proves the managed backend source or no-effect boundary.

**Why the replacement is not yet determined.** The I03 execution workspace spec §6 requires `mutation_guard._base_commit`, the run_bash write-set lookup, the IntentGuard Git runner, and related enumeration to use “supervised private metadata or approved snapshot data”; it also prohibits controller canonical-source probing. The current `WorkspacePort` exposes bounded file read, narrow project-artifact listing, and write, but not the complete delta of an active writable view. `ManagedExecution.revision_changes` compares sealed revisions, not unsealed per-tool writer changes. `SessionState.transaction.write_set` is not a complete substitute: managed `run_bash` deliberately skips the host-Git write-set collection, and the set does not encode the full staged status semantics needed for mixed-intent/test-edit validation. Disabling IntentGuard, injecting an empty staged list, or retaining canonical `Path`/Git probes would respectively weaken behavior or violate the managed boundary; none is assumed here.

**Historical decision point (superseded by the operator resolution below).** At E472, the unresolved proposal was to specify the complete source and semantics of the snapshot consumed before a gated managed tool call. At minimum decide whether it is the authority-derived delta of the active WRITE/PROJECT view against its admitted base, or another explicitly approved complete snapshot; how prior tool and managed EXEC effects are represented; the closed path/status vocabulary and completeness bound; and what happens on unavailable, stale, refused, or truncated metadata. The safety constraints remain: relative project paths/status only, no content or host paths, no controller Git/filesystem fallback, and fail closed before the target tool executes when the required metadata cannot be proved. Preserve unmanaged/legacy behavior unless separately authorized to change it.

**Options.**

A. **Preserve full IntentGuard semantics with authority-owned active-view metadata (recommended).** Define a bounded complete-or-unavailable path/status snapshot for the current admitted writer view. It must account for earlier accepted file-tool and managed EXEC effects plus the proposed current call, preserve existing classifier/test-edit protections, and be returned under the existing writer/view binding. If this requires a protocol/API addition, explicitly authorize and specify that surface; no host fallback.

B. **Approve a narrower managed IntentGuard contract.** Define exactly which existing guard checks remain at tool admission and which are enforced by another already-approved managed boundary. Explicitly accept any loss of aggregate staged-diff, mixed-intent, or test-edit visibility; do not silently disable the guard or call an empty snapshot equivalent. This is a security-behavior change and needs an identified replacement and no-effect oracle.

C. **Other explicit contract.** Specify the authoritative snapshot, failure behavior, preserved/changed IntentGuard obligations, and how both the producer and caller-edge mutants will be killed.

**Historical engineering recommendation (not selected).** Option A best matched the then-current I03 spec's supervised-private-metadata requirement and avoided conflating a mutable writer view with sealed `DIFF_REVISIONS`; the operator instead selected runtime-gate retirement. The local R19 production oracle should drive a real managed `fa run` through local UDS `SupervisorService`/`WorkspaceAuthority`, trap both controller Git and canonical-path probes, observe the approved metadata, and prove either a permitted tool effect in the view or a metadata-refusal no-effect result before publication. Producer kill target: re-enable `_default_git_runner`/canonical probing. EDGE KILL-CHECK: remove the managed snapshot binding at `cli._cmd_run` → `_build_run_hook_registry`; the production test must hit the trapped producer and fail at its named assertion.

**Operator resolution and acceptance boundary (2026-11-06).** Retire runtime IntentGuard from all production `fa run` routes, including managed child sessions; do not add a complete active-view snapshot API, empty-snapshot fallback, or controller Git/path fallback. `pr_prepare` remains an optional human-readable note: no pre-write precondition, no mutation authorization from its content/provenance, and failure/absence does not gate a later mutation or scoped-stage success. Runtime test-edit protection is intentionally removed; the existing commit-msg hook and shared classifier/test-edit validation remain. Any new plan-bound test-edit policy is deferred until after I03 and is not authorized here. R19 remained OPEN at the policy decision pending caller evidence. R18 remains CLOSED by E471 and revalidated in E472. Global W0 remains OPEN; W1, Docker, and live-host acceptance remain gated/not claimed.

**E473 R19 closeout (2026-11-06; Arena-local).** The production audit now finds no IntentGuard constructor/registration in the common `fa run` builder or managed-child builder; only the retained component class/export remains. `tests/test_execution_composition.py::test_managed_coder_first_write_needs_no_pr_prepare_and_never_calls_intent_guard` drives parsed `fa run --role coder` through `_cmd_run`, `drive_session`, and a real local UDS `SupervisorService`/`WorkspaceAuthority`. It verifies an admitted PROJECT/WRITE view, a first `fs_write_file` without `pr_prepare`, one authority `WRITE_FILE`, a later authority `PUBLISH`, no canonical visibility before publication, unchanged `.git/index`, and zero IntentGuard Git/path producers. The re-registration producer mutant failed at the authority-write assertion; the host-only registry-edge mutant failed at the canonical/authority boundary; both were hash-checked/restored. Managed-child production composition asserts no IntentGuard seat. Commit-msg validation and negative cases remain active. R19's Arena-local row is CLOSED by E473; the Q113 27-row global W0 gate remains OPEN and W1 has not started. No Docker/live-host acceptance is claimed; details and exact commands are in `ledger.md` E473.

## Q131 — What is the W0 disposition of the dormant R21 Git-list helper with no production caller?

**Status: RESOLVED — operator selected option C; the unused helper/export were removed and R21 retired from managed W0 by E477 (2026-11-06).** R21 is RETIRED / NOT APPLICABLE TO MANAGED W0, not PASS. This is separate from Q126-A/R23 and E474/R20; neither row is reopened.

**Source-to-caller audit (2026-11-06; pre-removal).** `fa.inner_loop.tools._common.git_ls_files` (`src/fa/inner_loop/tools/_common.py:22–53`) invokes bare `git ls-files`. Repository source search finds only its definition, doc/example, and `__all__` export; `run_bash.py` imports other `_common` helpers but does not import or call this function. Production `fs_search` uses the separate `fa.memory._safe_walk._git_ls_files` producer (R20). `tests/test_tools_common.py::TestGitLsFiles` calls the helper directly, and the file bank passes 31 tests; this is component evidence, not a production caller or managed-backend oracle.

**Why a decision was required (pre-resolution).** Q113 then counted R21 among its 27 active applicable W0 rows. The W0 rule requires a source→reachable production caller→named production oracle and non-vacuous producer/caller-edge mutation evidence. No supported production call edge exists to exercise. Adding one merely to obtain a test target would introduce a new route and behavior; deleting the public helper/export would change a compatibility surface. A test asserting the helper is unused would not kill its producer or prove a managed effect/no-effect boundary. Therefore no R21 PASS, N/A, or product-code change is inferred from the grep/test result.

**Options (presented before resolution; option C selected).**

A. **Classify R21 as `DORMANT / NOT APPLICABLE TO MANAGED W0`, not PASS.** Keep the helper/export and component characterization tests unchanged; retain the historical candidate in the inventory, remove it from Q113's active denominator only after the explicit decision, and document that this does not attest to any future caller. This matches the current source graph without inventing product behavior.

B. **Keep R21 active and keep W0 blocked.** Make no code change. Require a real supported production caller to be identified and approved before implementing the managed no-host-Git boundary and C1 producer/EDGE oracle. Do not start W1 while the active W0 gate remains unsatisfied.

C. **Authorize removal/deprecation of the helper and its export.** Treat that as a public API compatibility decision; specify whether direct consumers/tests are preserved or migrated, then prove no product route and record a retired/N/A disposition. No such deletion is authorized unless selected.

D. **Other explicit contract.** Specify the desired helper/API compatibility and W0 accounting without inventing a production caller or claiming a PASS from component-only coverage.

**Historical engineering recommendation (not selected).** A would have preserved the dormant component API. The operator instead selected C and authorized removal/deprecation of the helper/export; the implementation and R21 disposition are recorded below.

**Operator clarification (2026-11-06; product contract, not R21 disposition).** Workflow stages must retain the tool set assigned to each role, and those tools must function through the managed architecture; this includes the existing `fs_search` product affordance. Do not remove or expose a nonfunctional tool merely to satisfy a no-host-Git row. The planned implementation is the existing cell-local `project_tools`/EXEC seam in spec §4.2 and W1: execute against the active writer view or exact immutable reader pin, preserve the existing public tool schemas/results, keep index state process-local, and fail explicitly on unavailable/over-bound results without host/canonical fallback. This does not authorize wiring `_common.git_ls_files` into production or starting W1 before the full W0 gate.

**Operator decision (2026-11-06).** Select option C: remove the unused `git_ls_files` helper and its `__all__` export, along with its direct component tests. Preserve the rest of `_common.py`, the `fs_search` public tool and all role-assigned workflow tool corpora. This does not authorize wiring the removed helper back into production; the managed search implementation remains the cell-local W1 path recorded above.

**Implementation and acceptance (E477).** Removed the helper and its now-unused `subprocess` import/export; retained the other shared helpers and added a focused test that the removed symbol is absent. Updated the obsolete `_safe_walk` comment that compared against the removed helper. Source-reference review finds no remaining production caller. The producer-restoration mutant was killed by the API-removal test; a temporary reintroduced helper wired into the actual managed `profiles._build_fs_search` edge was killed by the R20 C1 no-host-Git oracle. Both were restored byte-exactly. R21 is therefore **RETIRED / NOT APPLICABLE TO MANAGED W0, not PASS**; at E477 Q113's then-current active set was R01–R20, R22, and R24–R28 (26 rows). Q132-D/E481 later deferred R24 to W2 (OPEN, not PASS/N/A), initially leaving 25 active W0 rows. Q133-B/E482 then defers R25/R26 to W2 and R28 to W1, all still OPEN and not PASS/N/A; the current active W0 set is R01–R20, R22, and R27 (22 rows). R19 remains CLOSED by E473; R20 remains CLOSED by E474; R23 remains separately RETIRED / NOT APPLICABLE under Q126-A/E469, not PASS. Global W0 is still OPEN and W1 has not started. R28 must pass before W1 closes; R24–R26 must pass before W2 closes. No Docker/live-host acceptance is implied; exact commands are in `ledger.md` E477.

## Q132 — How can R24 close under strict W0 ordering when managed verification is placed in W2?

**Status: RESOLVED — operator selected the W2 deferral (option D) on 2026-11-06; initial Q113 scope amendment recorded by E481 and current 22-row gate by Q133-B/E482.** R24 remains OPEN and required, but is excluded from the W0 active denominator as DEFERRED TO W2 (not PASS/N/A). E481 initially left 25 active rows; Q133-B/E482 subsequently deferred R25/R26 to W2 and R28 to W1, leaving 22 active W0 rows. W1 must not start until those 22 pass; R28 must pass before W1 closes. W2 cannot close until R24–R26 pass their managed production acceptance.

**Traceability and source facts.** Q113 requires every active/applicable S4P1 row to pass its named managed-backend production-caller oracle before W1. At Q132 opening, R24 was active; Q132-D/E481 now defers it from the W0 denominator while preserving its W2 requirement. The R24 inventory/audit identifies `slice_verification._run_one` and its verify/kill-check/eval callers as a host-`subprocess.run` route; the named managed-verification target is pinned-source/PlanRef/profile execution with private scratch and receipt/report parsing through managed `exec`. Existing `tests/test_verify_slice.py` and `tests/test_mutation_overlay.py` are component banks, not the required production-caller oracle. The 2026-11-04 R24 audit explicitly leaves the row OPEN because managed verification is S4P3/W2. The increment places S4P3 in W2, which starts only after W1; this conflicts with Q113's W0-before-W1 gate.

**Required invariant.** Do not claim R24 from component/helper tests, do not invoke host pytest as a managed fallback, and do not add a second writer/executor. Under the subsequent Q133-B/E482 amendment, start W1 only after the current 22 active W0 rows pass; R24 is deferred, not retired, and remains required for W2 closure alongside R25/R26. R24's eventual managed oracle must name the exact production caller/nodeid, prove row-specific effect/no-effect through the managed boundary, bind verification to the intended pinned source/PlanRef/profile, and fail explicitly rather than reporting PASS on missing, stale, skipped, timed-out, oversized, or uncertain evidence.

**Options.**

A. **Preserve strict Q113 and resequence R24's managed-verification deliverable before W1.** Move the R24-scoped S4P3 work needed for its named managed production-caller oracle into the W0 prerequisite. Keep W1 blocked until all active W0 rows pass. This does not authorize starting the rest of W2, implementing unrelated S4P3/S5 work, weakening report/receipt integrity, or claiming host acceptance.

B. **Keep the current S4P3/W2 placement and hold the gate.** Make no implementation or Q113 change now. R24 and W0 remain OPEN; W1 does not start. Resume only after an explicit dependency-plan decision supplies a strict-Q113-compatible R24 route.

C. **Other explicit sequence that preserves the contract.** Specify the exact pre-W1 production caller, managed effect/no-effect boundary, evidence binding, and dependency change. A helper-only test, static scan, host pytest invocation, or active-row exemption is not sufficient.

D. **Defer R24 to W2 by explicit Q113 amendment.** Keep the managed-verification implementation in S4P3/W2, mark R24 `DEFERRED TO W2` (still OPEN, not PASS/N/A), and change Q113's current W0 active set to R01–R20, R22, and R25–R28 (25 rows). W1 remains blocked until all 25 pass; W2 remains blocked until R24's managed production-caller oracle and producer/EDGE checks pass.

**Pre-decision engineering recommendation (historical).** A was the strict-Q113-preserving route considered before the operator decision. Q132-D/E481 instead selects the W2 deferral with an explicit active-set amendment; no R24 code route is authorized before W2.

**Producer / EDGE kill-check reservation.** No mutation was run for this documentation-only sequence decision. When R24 enters W2, the producer target must be the actual managed verification command dispatch (the implementation name/call site must be refreshed from source before editing; `_run_managed_command` is currently absent), and the EDGE target must be the production workflow-controller binding/call that routes verify/kill-check into that managed dispatch. Both must be killed by the same named production-caller oracle; helper-only kills do not close R24.

### Detailed source feasibility audit (2026-11-06; pre-E481 sequence analysis)

**Existing reusable boundary.** This is technically implementable without adding a second supervisor or new wire operation. `ViewPurpose.VERIFICATION` already exists in `execution.types`; `_PURPOSE_MATRIX` admits only `Access.READ` with a required PlanRef; `ManagedExecution.open_view` can request that purpose against the authority's current revision while retaining the existing single writer; and `WorkspaceAuthority._create_read_view` pins that immutable current revision after PlanRef validation. The authority denies generic writes through a VERIFICATION view. `Operation.EXEC` is already a typed operation with a terminal receipt bound by the executor to namespace, view, profile, source revision, and PlanRef. This is the viable base for a one-shot verification call.

**Existing sandbox.** The read-only `ExecutionProfile` mounts `/workspace` read-only, provides a private `/scratch` tmpfs capped at `READ_SCRATCH_BYTES` (64 MiB), mounts the optional prepared environment read-only, disables networking, and applies the existing CPU/memory/PID/rootfs/seccomp policy. The current checkout's `src` plus `scripts` payload is about 7.8 MiB, so the source-only mutation overlay fits this configured scratch ceiling in this checkout; test-generated scratch use still needs explicit cap/error coverage and is not proven by that size comparison.

**Missing production wiring.** `ExecutionBinding` already exists in `execution.composition`, and `WorkflowContext` already carries `managed_execution` and `managed_plan_ref`; however, `capture_test_nodeids`, `verify_plan`, `verify_slice`, `run_commands`, and `_run_kill_check` currently take host `Path`/deadline values and have no managed execution binding. The real coder-stage caller in `workflow_controller._run_stage` invokes nodeid capture and `verify_plan` directly after coder completion. There is no `_run_managed_command`. The current `ReadOnlyManagedBashExecutor` is not yet a drop-in verifier: it accepts `PIN_READER`/`ViewPurpose.PROJECT`, whereas a verification run needs the `CREATE_VIEW`/`ViewPurpose.VERIFICATION` grant. A narrow verification executor or validated executor generalization plus explicit binding threading is therefore required. Missing binding/profile/view/receipt must produce ERROR/`BACKEND_UNAVAILABLE`; it must never fall through to `_run_one`'s host `subprocess.run`.

**Scratch and report handling.** Run commands and mutation overlays inside the one-shot read-only cell: keep pinned source under `/workspace`, create only the allowlisted `src`/`scripts` derivative under private `/scratch`, run tests against the immutable declared `tests/` paths, and direct caches/reports/temp to `/scratch`. Persist only a validated compact result into the controller's run log after the execution receipt is checked; do not make the cell write controller artifacts or publish its scratch. The existing `CommandReceipts` tail is 64 KiB per output channel, while `_parse_junit_report` currently reads host report bytes without an explicit size limit. The spec already requires bounded per-test phase outcomes and makes missing, stale, malformed, oversized, skipped-only, timed-out, and uncertain reports ERROR, not kill. Implementation must set and test an explicit bounded report envelope compatible with current receipt ceilings (overflow is ERROR); a larger result channel would need a separate reviewed contract rather than silent transport expansion.

**Wave feasibility (source audit, before the operator decision).** The R24 path does not require the W1 `project_tools` search/reach implementation: it can use the existing `ManagedExecution`/`Operation.EXEC` seam and a VERIFICATION-purpose pinned view. The managed-verification production caller, executor/view adaptation, receipt/report binding, explicit failure routing, and producer/EDGE tests are nevertheless real S4P3 work currently scheduled in W2. The operator chose to keep that correct architecture in W2 rather than pull it into W0. No additional policy blocker was found in the inspected source beyond this sequencing choice; bounded report/scratch overflow must be explicit and fail closed within existing limits.

**Operator decision (2026-11-06; option D selected; later sequencing amendment in Q133-B/E482).** Defer R24's managed-verification work to S4P3/W2 rather than implement a short-lived pre-W1 route. E481 initially amended Q113 to R01–R20, R22, and R25–R28 (25 rows); Q133-B/E482 later defers R25/R26 to W2 and R28 to W1, leaving the current W0 active set R01–R20, R22, and R27 (22 rows). R24 remains an OPEN I03 requirement marked DEFERRED TO W2, not PASS or N/A. W1 may begin only after all 22 current active W0 rows pass; R28 must pass before W1 closes. W2 may not close until R24–R26 pass their managed production acceptance, including R24's managed VERIFICATION/EXEC path with pinned evidence, explicit bounded reports/failure handling, zero host fallback, and killed producer/caller-edge mutants. This decision preserves the existing one-writer and legacy `fa workflow` constraints; it does not authorize Docker/live-host claims. See E481/E482.

## Q133 — How should Q113 order the remaining W0 rows whose required dependencies are in W1/W2?

**Status: RESOLVED — operator selected option B on 2026-11-06; active-set amendment recorded by E482.** This question does not mark any row PASS/N/A. R25/R26 remain OPEN and are DEFERRED TO W2; R28 remains OPEN and is DEFERRED TO W1.

**Traceability and source-grounded conflict (at Q133 opening, after E481).** The then-current Q113 W0 set was R01–R20, R22, and R25–R28 (25 rows). The existing R25 audit assigns managed plan promotion to S5P2/W2 and cites unresolved Q90 composition plus Q114-A uncertainty/lifecycle implementation; the ordinary production composition still lacks the trusted publisher, and uncertainty must not be treated as determinate refusal. R26 is also S5P2/W2: the current nested-workflow route lacks the complete child PlanRef/acquisition and managed production-caller proof, and the row cites Q90/CT108. R28's required `test_no_model_tool_can_reach_the_host_bootstrap` is absent and the audit explicitly says it requires the W1 managed-Bash cutover. These are not claims that the rows pass; they are documented cross-wave dependencies. R27 remains a separate W0 row with local direct-chat production evidence and broader acceptance still open.

**Why the sequence decision was required.** Keeping R25, R26, and R28 in the W0 denominator while retaining their S5P2/W2 or W1 prerequisites made the strict rule “all active W0 rows pass before W1” circular. Q90 remains OPEN as an implementation dependency; Q114's selected policy remains binding and its R25 managed uncertainty acceptance is unfinished. The R24 decision did not silently disposition these other rows.

**Options.**

A. **Keep the current 25-row gate and pull all required row work forward.** Preserve Q113's current set and complete the full named R25/R26 managed production acceptance and R28 no-model-route oracle before W1. Do not substitute component tests or weaken Q90/Q114, child-authority, or managed-Bash requirements. This explicitly resequences work currently assigned to W1/W2; no host fallback is allowed.

B. **Align each row with its planned wave (recommended).** Keep R25 and R26 OPEN and defer them to W2; keep R28 OPEN and defer it to W1. Amend Q113's active W0 set to R01–R20, R22, and R27 (**22 rows**). W1 may begin only after those 22 active rows pass. R28 must pass its managed-Bash production-caller oracle before W1 closes; R24–R26 must all pass their managed production acceptance before W2 closes. Deferred rows are not PASS or N/A, and Q90/Q114 remain mandatory for R25/R26.

C. **Hold without changing the denominator.** Keep the current 25-row W0 set, do no R25 implementation, and do not start W1 until Q90 plus the R25/R26/R28 dependencies have been fully resolved and their active-row oracles pass. This preserves the current gate but accepts that progress is blocked.

D. **Other explicit dependency plan.** Name the active-set amendment, exact wave placement, production-caller oracle for each affected row, and all required Q90/Q114/managed-Bash safeguards. Do not infer PASS/N/A or authorize a temporary host route.

**Producer / EDGE kill-check reservation.** No source or test mutation was run for this scheduling question. If option B or another deferral is selected, R25/R26 producer and caller-edge targets remain part of their W2 acceptance; R28's real managed-Bash registration/call edge remains part of its W1 acceptance. Mutation targets must be refreshed from source before those implementations. No helper-only kill may close any row.

**Operator decision (2026-11-06; option B selected).** Align each row with its planned wave. R25 and R26 remain OPEN and are DEFERRED TO W2, not PASS/N/A. R28 remains OPEN and is DEFERRED TO W1, not PASS/N/A. Amend Q113's current W0 active set to R01–R20, R22, and R27 (**22 rows**). W1 may start only after all 22 active W0 rows pass; R28's managed-Bash production-caller oracle must pass before W1 closes. W2 may not close until R24–R26 pass their managed production acceptance; Q90's publisher binding and Q114's uncertainty/lifecycle requirements remain mandatory for R25, and Q90/CT108 child-binding requirements remain mandatory for R26. No host fallback, second writer, child-authority weakening, or uncertainty shortcut is authorized. W0 remains OPEN; W1 has not started. See E482.


## Q134 — Does the existing per-file size ceiling count as a Q111 aggregate-budget overrun?

**Status: RESOLVED — operator selected “Keep the explicit exclusion” on 2026-11-06.** For managed `fs_search` and `fs_reach`, files larger than the established 200,000-byte per-file indexing ceiling remain outside the documented indexable corpus and must be counted/surfaced through the existing `skipped_large_files` / structural skipped-file reporting. They do not alone force whole-call refusal. This is not permission to silently truncate an aggregate discovery: exceeding any Q97 walk, candidate, aggregate source, AST/cardinality/index, output, or deadline quota remains whole-call non-success under Q111-A, with no partial/truncated result. Oversized candidates still count toward the bounded candidate inventory.

**Traceability.** `fs_search` already reports a `skipped_large_files` count; the legacy structural walk applies the same per-file ceiling. The managed strict rooted-reader route currently encounters an oversized lexical candidate as a refusal instead of applying that declared exclusion. The current checkout contains six search candidates over 200,000 bytes and `src/fa/execution/workspace.py` at 256,012 bytes; treating every such file as an aggregate overrun would make both managed discovery tools refuse on this tree. Q97/E506 therefore require a bounded preflight that identifies the established exclusion, reports the count, and never reads/indexes excluded bytes; aggregate quotas continue to be checked against the full eligible corpus. For reach, expose the skipped-file count in its existing stats/result surface without returning a partial result due to any aggregate quota.

**Producer / caller kill checks.** No code changed for this disposition. The producer kill must remove the oversized-file exclusion/counting and make the exact-size fixture read/index the oversized candidate; the caller-EDGE kill must bypass the managed Q97 executor/serial scheduling route and reintroduce a host or unbounded path. Both are to be killed by the named C1 production-caller oracle after implementation; no helper-only proof closes W1. See E506 and `notes/q97-w1-resource-contract-2026-11-06.md`.

---

## Q135 — How should the existing tool-batch safety probes be closed before dependent cutover?

**Status: BLOCKING for full F1–F4 closure. F1-only prerequisite is in scope; F2–F4 are deferred to live E2E after W3.** This source-grounded split follows E357/E358 and the operator direction to derive semantics from the current harness contracts, otherwise defer. It does not add CT/STEP, change the dependency order, close an acceptance row, or authorize dependent cutover. See the updated [Q135 application](i03-composition-and-batch-foundation-plan-2026-11-01.md#6-q135--f1-only-prerequisite-f2f4-deferred).

**Traceability and current evidence.** Preserve Q97/STEP2b → Q103. Existing source `src/fa/inner_loop/loop.py::_execute_batch_parallel` submits calls to a `ThreadPoolExecutor`, then its broad `except` sequentially dispatches every executable payload, including submitted/possibly completed calls. E356's recorded fault injection observed each of two handlers execute twice after a `wait` exception. E358 separately records synthetic probes: F2's wait timeout does not cancel a running thread and the executor waits before returning; F3 demonstrates a synthetic BEFORE hook rewriting a read call to a workspace tool without batch reclassification; F4 demonstrates duplicate `call_id` values aliasing results in a dictionary while the set-based provider pairing check accepts duplicates. These are local harness observations, not production-frequency or host acceptance evidence. The current production reachability of hook rewrites and duplicate provider IDs is not established.

**Impact.** A bookkeeping/submission error can repeat an effect. Timeout can be mislabeled as stopped work, creating unsafe retry expectations. A modified effective call may inherit an earlier scheduling classification, and duplicate IDs can make distinct calls share one result. Do not enable dependent production cutover while the applicable safety gate is unresolved; disabling concurrency by itself is not an approved or proved mitigation.

**Eight-point application.** See the linked §6 draft for behavior target, existing seams and candidate file allowlist, dependency map, safeguards, failure semantics, C0/C1/C3 tests, final live acceptance and producer/EDGE mutation DoD. The draft reuses `run_session`, `ToolRegistry.dispatch`, `HookRegistry`, and `drive_session`; it proposes no new scheduler. The proposed live multi-call witness is not a ledger-append path, so ledger-append E2E is not applicable. No host result is claimed.

**Source-grounded disposition under the operator direction:**

- **F1 — bounded prerequisite now.** E358 already supplies the invariant: never automatically re-dispatch submitted/started work; an unknown outcome is not retryable. The broad fallback in `loop.py::_execute_batch_parallel` violates it. Implement only this no-repeat behavior using the existing future/result seam, with a C1 caller-rooted oracle and producer/EDGE kill-checks.
- **F2 — defer until post-W3 live E2E.** `ThreadPoolExecutor` context exit waits for running workers, so the current 30-second `wait` is not a hard execution deadline. The code can report `exec_timeout` after a handler eventually completes, while no accepted contract defines whether late completion should return its actual result or a timeout failure. Do not invent cancellation or retry semantics now.
- **F3 — defer until post-W3 live E2E.** Current source has no production `Decision.modify` callsites. ADR-7/ADR-8 require effective payload schema and opted-in sandbox revalidation, but do not specify batch reclassification/order after a cross-class rewrite; the existing probe is synthetic.
- **F4 — defer until post-W3 live E2E.** `_build_tool_calls` and `_tool_calls_for_message` normalize missing IDs, but do not establish provider-wide duplicate-ID behavior; direct `run_session` callers also lack an agreed empty/duplicate-ID failure contract. Do not choose reject-versus-normalize without the deployed caller evidence.

Q135 remains BLOCKING overall. F2–F4 and every dependent production cutover stay OPEN until post-W3 live E2E and contract review. The local F1 slice is not host acceptance and does not close STEP2b or any row.

**F1-only local result.** `src/fa/inner_loop/loop.py` now settles retained futures without re-dispatch, only falls back sequentially when no submit attempt occurred, reports attempted-without-Future as non-retryable unknown, and reports never-attempted calls as retryable/not dispatched. The existing 30-second timeout behavior is unchanged; F2 remains deferred. C1 `drive_session` coverage plus `tests/test_tool_batching.py` passed **33 tests**. Ruff check/format passed; focused Pyrefly reported **0 errors**. The targeted producer mutant (re-dispatch retained futures) was killed by the exact-effect counter; the EDGE mutant (bypass `drive_session -> run_session`) was killed because no effects/results remained. These are local checks only: no live host acceptance, no ledger append, and no Q135/STEP2b closure.

**Producer / EDGE reservation.** For any approved implementation, producer mutations must kill the relevant no-repeat/future-settlement, effective-call safety, and ID-correlation decisions. The primary EDGE mutation must bypass `coder_loop.drive_session -> run_session` and fail a C1 oracle with actual handler call counts/results; any affected second caller must be inventoried and tested separately. The full live/deployed obligation stays with SLICE6 and is NOT RUN here.

---

## Q136 — How should the independent project Pylint gate findings be resolved?

**Status: BLOCKING for the project Pylint gate; independent of Q135/F1.** The configured gate is `pylint src/fa` (`justfile::_lint`), with only R0801 duplicate-code and R0401 cyclic-import enabled. This entry records a workspace gate failure, not a finding that the F1 batch change caused it.

**Evidence.** `./.venv/bin/pylint src/fa` exited **8** (rating 9.99/10): two R0801 pairs and 17 R0401 import cycles. The duplicate pairs are the similar `rebind` validation in `execution/client.py` vs `execution/tool_port.py`, and exception/error mapping in `execution/backend.py` vs `execution/termination.py`. The reported cycles include `execution.composition -> execution.types -> session.manager -> execution.composition`, the broader composition/service/workspace/termination graph, and `memory.managed_discovery -> memory.search_index` (the latter imports `MAX_SEARCH_FILE_BYTES` while `search_index` locally imports managed-discovery helpers). These source files were already modified/untracked outside the F1 slice. The changed `src/fa/inner_loop/loop.py` alone passes Pylint at **10.00/10**, exit 0. Project policy explicitly excludes `tests/` from Pylint; the related pytest suites passed 68 tests. Pylint's graph findings do not alone prove a runtime import failure, and the two R0801 pairs may encode intentionally distinct contracts.

**Impact.** The repository's configured Pylint stage is red; consequently the lint gate is not green. Consolidating security/lifecycle validation without confirming the owners could weaken distinct checks, while suppressing R0401 or blanket-waiving R0801 would mask structural findings without an approved rationale.

**Options.**

- **A — Resolve structurally (preferred only where source contracts show one owner).** Trace the import/consumer edges, extract or inject only already-shared contracts through their current owner, and consolidate duplicated behavior only where the validators/error mappings are semantically identical. Require targeted tests and re-run `pylint src/fa`.
- **B — Preserve intentionally separate validators.** Where the two `rebind` or exception-mapping paths must remain distinct, document the contract difference and use the repository-permitted file-level R0801 waiver with rationale. This does not waive R0401; the import cycles still need a source-grounded resolution or the gate remains blocked.
- **C — Defer to a dedicated execution/managed-discovery review.** Make no unrelated source edits now, retain the failing gate as BLOCKING, and do not claim `just lint`/Pylint PASS until the owners and cycle policy are resolved.
- **D — Other.** Specify exact module owners, allowed dependency direction, caller-level oracle, and waiver policy before code changes.

No code, tests, or increment were changed for Q136. Do not treat the 68 targeted test passes or the F1-only Pylint pass as closure of this independent gate.

## Q137 — Full pytest/Pyrefly gate findings and baseline disposition (2026-10-30)

**Status: BLOCKING.** W0 remains closed; W1 implementation remains paused. Operator selected **A — strict gate closure, best effort**. The original 88-failure/11-error gate and intermediate Pyrefly counts are historical; the latest immutable full `just test` before subsequent refactors was 37 failed / 7252 passed / 18 skipped / 4 xfailed / 11 errors (exit 1), not a test of the current source snapshot. Prior full Pyrefly reported 0 errors, and prior full mypy 3 errors in 3 files; neither full check has been rerun after the latest refactors. See [working inventory](q137-working-entry-inventory-2026-11-09.md) for exact IDs, fixes, targeted evidence and limitations, and [full gate triage](q137-full-gate-triage-2026-10-30.md) for earlier history. Live-host acceptance and managed-provisioner/readiness failures remain open; no direct-review deferral is acceptance.

**Impact.** The required gates are red, so W1 cannot be advanced or called ready. Current failure groups include managed-provisioner/profile preconditions, static/contract drift, assertions, test-only Pyrefly diagnostics, and the separate baseline TLS failure. Fail-closed behavior must be preserved; no fallback, blanket waiver, suppression, or weakened test is authorized by this evidence.

**Options.**

- **A — Strict gate closure (recommended).** Keep every current failure and diagnostic blocking. Continue in contract/dependency order: first map managed-provisioner/profile failures to their actual test caller seams and supply contract-conforming fixtures/adapters only where the test's intended class allows; retain production-route C1/C2 coverage. Then resolve each current static/contract/test finding and all Pyrefly diagnostics, including unchanged baseline diagnostics, without ignores. Address the TLS test environment separately without bypassing the integration contract. Re-run targeted checks/mutations and both full gates after each repair group.
- **B — Explicitly disposition only baseline/environment findings.** Keep the then-reported 43 current-only Pyrefly diagnostics and all current pytest failures blocking, but record the then-reported 21 unchanged HEAD Pyrefly diagnostics and the TLS-blocked baseline integration probe as separate accepted non-W1 findings. The full gates would still be reported red; no gate-readiness claim follows unless a later explicit acceptance rule permits it.
- **C — Other.** Specify the exact baseline/environment findings to disposition and the acceptance rule; current-only failures remain blocking unless separately resolved or explicitly dispositioned.

Q135 F2–F4 and Q136 Pylint are unaffected and remain independent. No W1 implementation was advanced by this triage record.

---

## Q138 — May the settlement predicate count an unsettled CANDIDATE view as blocking owner release?

**Status: OPEN — re-researched 2026-11-10; E509's premise was wrong and is corrected here. Research: `q138-candidate-settlement-research-2026-11-10.md`.**

**Reproduced behaviour (E509).** Replacing the determinate refusal in the S3P3 C1 test with `SupervisorError("DURABILITY_UNKNOWN")` — E407's exact injection point, before `publish_candidate_plan`'s commit body — leaves the CANDIDATE view at `purpose=CANDIDATE, access=READ, state=STOPPING` with its private `candidate` bytes on disk, while `workspace.json` reads `AVAILABLE`. With the original `INPUT_POLICY` the view is `REJECTED` and no `candidate` remains. Mechanism: `publish_plan` skips `_release_view` while uncertain (`client.py:594–599`), `ManagedExecution.close` fences only an unresolved HANDOFF (`composition.py:348–363`), and `_has_unsettled_views` skips every `READ` view (`workspace.py:1862`), CANDIDATE being `READ` (`:219`).

**Correction to E509's framing.** E509 called `access != READ` a defect against §2.1. It is not. §2.1's release row is scoped to **WRITE** views by design (`i03-execution-workspace-spec-2026-10-15.md:168`), and that scope is correct for the `PROJECT`/`VERIFICATION` read pins the system actually creates: their bookkeeping must not fence the next writer, and their pins are revoked separately by `release_reader`. The real invariant is not "access is WRITE" but **"this view owns uncommitted writer-private state"**. CANDIDATE is the only READ view satisfying the second and not the first, because its READ access exists precisely to keep the ordinary `write_file` path off the buffer.

Two facts bound the answer:

- The scenario is not "data loss". After an indeterminate PUBLISH the PLAN may already be committed, and Q114 forbids asserting otherwise. What is lost is *attribution*: the next claim advances `generation`, after which `_closed_candidate_reader` rejects the old view forever (`workspace.py:4023`), so nothing can ask "did this publish".
- Reconciliation is real but **not durable proof**. Same-request replay comes from a process-local, non-persistent reply cache (`supervisor.py:159–168`; a miss becomes `EXECUTION_UNKNOWN`, `:379–386`). It completes the ordinary in-process case; it cannot promise recovery — which is why Q114 puts process death in quarantine.

**Why this is a question and not a patch.** `_settled` (`workspace.py:1813`) is shared by `release_writer`, `release_unused_writer` **and `handoff`** (`:1736`, `:1747`, `:1774`), and the authority cannot distinguish a managed run from legacy direct `fa workflow`: both publish and release through the same client and `_settle_owner`. Any predicate change therefore changes legacy behaviour, which Q114 says must not happen in this scope. The blocker is a scope authorization, not a design problem.

**Impact.** The writer is released while a writer-owned artifact is unsettled — the condition already refused for `SEALED` on a WRITE view (`workspace.py:1843–1846`). The result is an unrecoverable, unattributable private buffer and an unanswerable ownership question for the next publisher.

**Options (revised; E509's option A is withdrawn as based on the wrong premise).**

- **A — Handle + same-id replay, no authority change (recommended).** `ManagedExecution` keeps the pending publication (the four `op-` ids, view ref and grant, source and candidate) and `close()` refuses while pending — the existing `_pending_handoff` pattern (`composition.py:348–353`). Reconciliation re-sends the same ids; `publish_candidate_plan` accepts **any** `STOPPING` CANDIDATE view of the same generation (`:4000–4040`), with `_already_published`/`_settle_view` (`:4061`, `:4591`) making the repeat safe and the view releasable. No wire change, no authority change, legacy untouched.
- **B — A plus a purpose-scoped fence.** Additionally require `state in {PUBLISHED, REJECTED}` for CANDIDATE in `_has_unsettled_views`. This is the only mechanism that can hold the owner when `close()` is never reached, but it also changes legacy direct `fa workflow`. Needs explicit scope sign-off.
- **C — A, authority untouched, residual gap recorded.** A run that dies between the uncertain error and storing the handle is covered only by `OWNED → QUARANTINED` at next load (`:1358–1360`). Must be recorded as an accepted gap, not as Q114 closure.
- **D — Leave as is and document.** Rejected on the research: it is the outcome Q114 explicitly refused, and the probe shows it is reachable and silent.

**Open sub-question (needed for A to be executable).** `publish_plan` does not surface its request ids on the exception path in storable form: it raises with only the last id (`client.py:585`, `:594–599`), while the earlier `CREATE_VIEW`/`WRITE_FILE`/`STOP_VIEW` ids stay local (`:525–570`). A needs all four captured on the pending record, i.e. threading them out of `publish_plan` — an internal client-method signature change, not a wire change. Confirm this is in scope for R25, or fold it into B's sign-off.

**Engineering recommendation (not resolved).** A, with C's residual gap recorded explicitly. The fence is not needed for process death (`_load` already quarantines `OWNED`) and is needed only for "reconciliation cannot run", which A cannot close by itself. B is preferable only if the operator authorizes the legacy-visible change.

**Scope.** Resolving this does not close R25, authorize a new wire operation or second writer, change legacy direct `fa workflow` behavior unless option B is chosen, or provide host evidence. W1's remaining `Q119-A` item is unaffected.

---

## Q139 — How is the mutation gate made to examine the code it claims to cover?

**Status: ANSWERED — operator chose A on 2026-11-11; the deciding evidence was not the layout. `no_tests` turned out to be a test-selection fact, and the real defect was worse. See also `mutation-scope-and-import-isolation-2026-11-10.md` §3–§5.**

**Context.** The operator authorized extending `[tool.mutmut].source_paths` to `src/fa/execution`, committed as `f7da7e0`. Measuring the result exposed defects in the gate that bound what any mutation claim means.

**Defect 1 — scope blindness (fixed, `f7da7e0`).** `run_targeted_mutmut._scope_to_changed` filtered every `execution/` file out and printed `nothing to do`, returning 0: a green result for an area never examined.

**Defect 2 — imports lost on an explicit run (fixed, `f7da7e0`).** In explicit mode `also_copy` came only from the CLI and `run_targeted_mutmut` passed none, so a staged run had no `src/fa` copy and imported the editable checkout; mutmut then reported "no test case for any mutant" for every mutant.

**Correction — the earlier "staged layout" diagnosis (defect 3) was WRONG.** This entry previously asserted that `mutmut.setup_source_paths()` inserted a non-existent `mutants/src`, that Python ignored it, and that `import fa` therefore resolved to the repository. That is disproved by direct probe: `_run` does `makedirs` → `copy_src_dir` → `copy_also_copy_files` → `setup_source_paths()` (`mutmut/__main__.py:1016–1021`), so the copy exists before the insert, and in a stage directory `sys.path[0]` is the staged `mutants/src` with `fa` resolving there.

`no_tests` is the pytest **exit code 5** ("no tests ran"), per `status_by_exit_code` (`:77–91`: `1→killed`, `0→survived`, `5→no tests`, `33→no tests`, `36→timeout`). The `no_tests=526` figure came from a probe that configured **one test file against six mutated modules**, so most mutants genuinely had no test. It measures the selection, not the layout.

**Defect 3 (real) — the selector never listed any execution suite (fixed, `8cf42cd`).** Chasing the correction found the actual hole, and it sits exactly in the scope `f7da7e0` added: `pytest_add_cli_args_test_selection` named no `tests/test_execution_*` file. A mutant under `src/fa/execution` would have run against sandbox tests that cannot import it and "survived" vacuously — a full-scope green that proves nothing. `type_check_command` and `[tool.pytest-gremlins].paths` had also drifted from `source_paths`, so T19's positional invariant was red. All three are reconciled, T19 is green, and `tests/test_slice_mutmut.py` is 21 passed.

**Operator decision (2026-11-11): A — fix the staged layout.** The operator accepted the cost with the reasoning that findings from unexamined places are hard to handle later but worth it. Recorded as taken; the staged-layout premise it was argued from did not survive the probe, and A's *intent* — the gate must actually examine the configured scope — is what `8cf42cd` implements.

**Still open, and honestly so.** The scope is correct but **unmeasured**: a configured-scope run attempted 2026-11-11 died with `mutmut run returned -9` (SIGKILL) before producing counts, i.e. the runner's memory bound. `mutants/scope-baseline.json` records `"verdict": "infrastructure_failure"`. Until a run completes, no closeout may claim coverage for `execution/`; that is option B's discipline, applied to the only bucket we cannot yet quote.

**Impact.** Every prior mutation claim in this repository means "the mutants that had a test stayed green", not "changed-path mutants were checked". Any closeout must quote `killed / (total − type_invalid − no_tests)` and name the selection that produced the denominator.

**Options as put.** A — fix the staged layout, re-baseline, re-quote the real kill rate. B — keep the layout, stop claiming coverage. C — revert the `execution/` extension until A lands. D — other. Operator chose A.

**Scope.** No change to the weekly workflow's advisory policy and no W-row is closed. The gate's correctness is now pinned by T19; its *coverage* is unmeasured until a full run completes.

## Q140 — Where does a managed verify command run, and where does its scratch go?

**Status: OPEN — operator decision required; raised 2026-11-11 by the W2 research note (`w2-remaining-steps-research-2026-11-11.md`). Blocks R24/S4P3's cutover, not its seam.**

**Context.** R24 replaces the host `subprocess.run` in `slice_verification._run_one` with managed execution. E509 flagged this as "one ambiguity that would force a guess"; the research note resolved the mechanics and left two questions.

**What is established by source and probe.** `ManagedBashExecutor` refuses any view that is not `Access.WRITE` (`client.py:1059`), and `ViewPurpose.VERIFICATION` is `Access.READ` *and* refuses writes outright (`workspace.py:217`, `:2747`). So verify cannot run in the purpose named for it. A `MUTATION` view — `Access.WRITE`, interactive-capable, plan-bound, confined to `_MUTATION_ROOTS = {"src", "scripts"}` — was probed end to end: it constructs the executor and reaches command dispatch, failing only on `BACKEND_UNAVAILABLE` because this sandbox has no Docker.

**Options.**

- **A — give VERIFICATION write-bearing scratch semantics.** Honest naming; widens a matrix that purpose tests pin, and duplicates MUTATION's capability.
- **B — run verify on a MUTATION view.** Reuses an admitted purpose; the only open sub-question is where scratch lives.
- **C — inject the executor into `run_commands` and change nothing else yet.** Not an alternative to A/B but a prerequisite for either.

**Engineering recommendation.** Do C regardless — it is the seam R24 needs and a behavioural no-op. Then B, with scratch declared explicitly: either inside an approved mutation root, or as a temp directory outside the canonical tree (the command runs with `cwd=workspace` but its scratch is never projected). Prefer B over A because widening a pinned purpose matrix to duplicate an existing purpose is how a security matrix stops being reviewable.

## Q141 — May a nested child's coder write project files under Q61?

**Status: OPEN — operator decision required; raised 2026-11-11 by the W2 research note. Blocks R26's gate removal.**

**Context.** `workflow_tool._requires_acquisition` refuses every coder-containing nested workflow with `acquisition_unavailable` (`:400–402`, `:611–616`), which makes the entire managed HANDOFF/return composition unreachable in production: only planner/eval-only nested workflows run. R26 is therefore not "build a handoff" — the handoff seam already exists and is exercised from the chat tool (`composition.py:134–160`, `workflow_tool.py:467, 498`) — but "remove the gate and prove it against a real authority".

**The question.** R26's DoD says "no child project write on denial", which implies writes are permitted on success, but it never states that positively. Under Q61 the trusted controller remains the parent, so the safe reading is that a child coder writes into its own managed view and the parent publishes — but that is an inference from a negative, not a decision.

**Options.**

- **A — child coder writes project files through its own bound view (parent publishes).** Full nesting; needs child PlanRef acquisition to exist first, which is S5.
- **B — nested coder remains plan-staging only.** Narrower; the gate becomes a permanent documented limit rather than temporary unavailability.
- **C — child coder writes only inside an approved mutation root** (same confinement as R24's option B), leaving project-level edits to the parent.

**Engineering recommendation.** A, sequenced after S5: the gate exists precisely because a nested coder would otherwise admit a session with no PlanRef, so removing it before S5 can produce a PlanRef would trade a clean refusal for a broken run. Whichever option is chosen, state it positively in the plan — "no write on denial" is not a policy.

**Scope.** Neither question authorizes a wire change, a second writer, a model-visible grant, or any change to legacy direct `fa workflow`.

## Q142 — How does a managed verify gate collect its JUnit evidence?

**Status:** OPEN — blocks R24 step 3 (wiring the caller). Steps 1–2 are committed and unaffected.

A managed run edits a revision the controller host never sees. R24 exists so the
verify gate judges *that* tree instead of a stale host copy. The substrate seam
(`238f75b`) and the read-only executor (`7e4dfcb`) are in place; passing the
executor down from `WorkflowContext.managed_execution` is the remaining wiring.

It cannot be wired yet, because the gate needs evidence to land **on the host**
and reads it there:

- `slice_verification.py:709` creates a host `TemporaryDirectory` for the JUnit XML;
- `:715–725` runs `NODEID_CAPTURE_COMMAND` with `--junitxml=<that host path>`, then
  `_parse_junit_report(report_path)`;
- `:1673–1686` does the same per kill-check (`fa-kill-junit-`), and copies source
  roots into a host overlay;
- `:555–565` decides what to run from `(Path(root) / path).exists()` — a host check.

Inside a cell that path does not exist, so every slice would record `ERROR`: a gate
that can never pass. Small, enumerable surface — but each item is a contract choice.

**Options**

- **A. Collect JUnit XML in-band** (write to stdout inside the cell, parse from
  `stdout_tail`). Cheapest wiring; but `TAIL_LIMIT` bounds the tail, and a truncated
  report is exactly the "not evidence" case the executor already refuses. Also
  redefines `stdout_tail` for every existing caller.
- **B. Report into the cell's private `/scratch`, read back through the port.**
  Evidence stays a real artifact inside the proven boundary. Costs a new port method
  — `ClientWorkspacePort.read_file` reads the **source** projection only
  (`workspace.py:2174–2194`), so `/scratch` is not reachable through it today — plus a
  `/scratch` sizing decision (64 MiB tmpfs).
- **D. Leave the gate on the host** and declare R24 to be "the seam only". Honest, but
  a managed run then verifies a tree the coder never touched, which is the defect R24
  was raised to remove.

**Recommendation:** **B**, for the reason Q140 chose C — it keeps the evidence an
artifact and keeps it inside the boundary the authority already proves. A is a
protocol change wearing a convenience's clothes; D leaves the managed gate
meaningless. **C (MUTATION view) stays withdrawn** — mutation roots *are* the
canonical source (`workspace.py:225`).

**Impact if deferred:** R24 stays two-thirds done: a managed verify still cannot run
on the authority, and the `executor` parameter has no production caller.

### Q142 addendum — B is not implementable; the audit for it found four more items

Re-checked the whole verification module instead of just wiring the recommendation.
**B is falsified by the mount table, not by taste:**

- a READ view mounts **exactly two things** — sealed source at `/workspace` (ro) and
  the toolchain cache (`profiles.py:108–113`);
- its `/scratch` is a **tmpfs inside the container** (`profiles.py:161–167`), with the
  authority's own instruction in the comment: *"Do not retry with the supervisor-owned
  host scratch bind if rejected"*;
- so the host scratch directory `_ensure_inputs` creates for a READ view
  (`workspace.py:5649`) is **not mounted** on that path at all. Nothing is written to it
  by an exec, and there is nothing on the host to read back.

B therefore needs a new v2 operation to expose scratch contents — the same escalation
the spec reserves for R16 `DIFF_REVISIONS`. That is a product/spec change, not wiring.

**The spec already answers the question** (`i03-execution-workspace-spec:1122`):
*"reports/cache/temp are private scratch, not source revisions or controller
artifacts"* — the controller is explicitly not meant to receive the artifact. Only the
verdict crosses. That is A's shape, and `:1107` names the runner as a managed
noninteractive operation.

**A's bound, measured rather than assumed.** One JUnit report for 52 tests is
15 826 bytes → **304 bytes/test**; the receipt carries the last 64 KiB
(`protocol.py:26`). So A holds ≈ **215 tests per report**, and the largest test file in
this repo declares 128. Overflow is loud, not silent: `cell_worker` sets
`truncated=True` when a stream exceeds its limit, and the adapter turns that into
`ERROR` (never PASS) — the same refusal already tested.

**Four more items the audit found, none of them B's:**

1. `_existing_test_paths` (`:555–565`) decides what to run from the **host** tree. In a
   managed run that is a *silent false pass*: a test file the coder created in the
   revision does not exist on the host, so the slice reads "no declared TESTS path
   exists at this snapshot" and is treated as vacuous, not as unproven. Must read the
   revision — `LIST_PROJECT_ARTIFACTS`/the manifest — under the same managed switch.
2. The adapter currently drops `env` (`del env`), which would also drop the
   recursion guard and kill-check marker (`FA_VERIFY_GATE_TEST_DEPTH`,
   `FA_VERIFY_GATE_KILL_CHECK`, `FA_VERIFY_JUNIT_RUN_ID`). The cell environment is the
   authority's to fix, so the honest mechanism is a command-prefix assignment
   (`VAR=value command`), not a process environment.
3. **The mutation overlay is its own increment, not R24 step 3**: it is a host
   `copytree` + `mkdtemp` + `write_text` (`:1096`, `:1149`, `:1155`) plus a git base read.
   The spec's destination for it is a *supervised derivative view* (`:1107–1112`,
   "materialize a derivative with the same supervised view primitives"), i.e. a v2
   write path — out of scope for verification and should be tracked separately.
4. Baseline capture (`capture_test_nodeids`) is part of R24 too — it is the T0 half of
   the same comparison, and it feeds on the same JUnit/`_existing_test_paths` mechanism,
   so items 1–2 apply to it identically.

**Revised recommendation: A**, with items 1–2 as part of the same step and item 3
promoted to its own question/increment.

## Q142 — RESOLVED: option A, plus the two fixes the audit found

Landed as `5e453b5` (evidence in the receipt, path resolution, marker prefix) and
`0ee4b27` (the caller and its single substrate). B was falsified, not deferred: a READ
view mounts sealed source and the toolchain cache only (`profiles.py:108-113`) and its
`/scratch` is a tmpfs inside the cell (`profiles.py:161-167`), so there is no
controller-side artifact to read back and no mount to expose one through.

**What the gate now does.** `_pinned_verify_substrate` pins one READ view of
`managed.current_revision_id` per verification and hands the same substrate to both
the T1 capture and `verify_plan`, so the comparison cannot be scoped to two different
trees. An unmanaged run yields `None` — the host tree is what it already is. A managed
run with no read-only profile raises rather than yielding `None`, because falling back
to the controller's copy is precisely the defect R24 removes. T0 keeps the host
substrate: it runs before the coder's view exists.

**Evidence.** The report travels in the command's own stdout between markers and is
parsed by the same function as the path-based mode (`_parse_junit_bytes`). Capacity is
measured: 304 bytes/test against a 64 KiB receipt tail, ≈215 tests, largest test file
here 128. Overflow is loud — the cell reports `truncated`, and the adapter turns that
into `ERROR`, never `PASS`.

**Two defects found by auditing the module, not the recommendation:**

1. `_existing_test_paths` consulted the host, so a test the coder created in the
   revision was invisible and the slice looked like it had nothing to prove — a false
   pass from a missing file. Host absence stays the documented empty-T0; on a snapshot
   an unconfirmable path is *unproven*.
2. The adapter dropped `env`, which would have silently disabled the recursion guard
   and kill-check marker on the managed substrate. Only harness-computed markers travel
   now, `shlex`-quoted, as a command prefix.

**Negative oracle** (`tests/test_verify_read_only_oracle.py`), proved against the real
authority: a READ view lives in `_readers`, and the writable lookup consults
`_projects`, so a write naming a pin is refused as `UNAUTHORIZED` before any policy
runs. Mutation confirms what it does *not* cover: removing `_purpose_write_policy`'s
purpose branch or relaxing `workspace.py:5374` does not kill it; admitting `_readers`
into the writable lookup does. Those two are second-order fences.

**Remaining, tracked separately (not R24):**

- the **mutation overlay** is still host `copytree`/`mkdtemp`/`write_text`
  (`slice_verification.py:1096,1149,1155`) plus a git base read. The spec's destination
  is a supervised derivative view (`:1107-1112`), i.e. a v2 write path — its own
  increment.
- C1 end-to-end on a live supervisor is still impossible in this sandbox
  (`BACKEND_UNAVAILABLE`: no Docker); only the client half is proved here.

## Q147 — how does a validated `PlanSnapshot` reach admission without a host plan path?

**Status: RETRACTED the same day — asked on a misreading; no decision required.**

The mechanism is already specified in I02 and already implemented in
`workflow_controller.py`. `PlanSnapshot(ref, utf8_bytes, text, ids)` is self-sufficient:
`snapshot_from_bytes(relative_path, raw, *, source_kind)` builds a complete snapshot from
bytes with no filesystem access, and `read_plan_snapshot` is a wrapper that reads bytes and
calls it (`plan_admission.py:133–160`). `_read_repair_candidate`
(`workflow_controller.py:2658–2681`) is that exact pattern already shipped for managed
repair — bytes from the authority's staged buffer via `ctx.managed_candidate_reader`, then
`snapshot_from_bytes`, then a digest comparison. `_WorkflowAdmission.snapshot` is typed
`PlanSnapshot`, and `_check_admission_source` returns early when no admission exists, so
the host re-read is only the host branch of an existing split, not a competing authority.
`i02-explicit-admission-spec-2026-10-15.md:88–92` fixes the order and already expects the
snapshot to be the authority; `admission_schema.py:143` reserves `EXISTING_SELECTION` and
`BOOTSTRAP` precisely for this internal producer.

My error: I reasoned from `run_workflow`'s public signature ("only `plan_path: Path | None`")
to a conclusion about the whole mechanism, while the controller's internal snapshot builder
was a different surface I had already seen and read past.

**Consequence:** no public signature change, no new parameter. S5P1 STEP2 is implementable on
existing seams. Full retraction, with the five source facts, is in
`q147-acquisition-internal-plan-snapshot-2026-11-12.md`.

## Q148 — how does a chat-only `invoke_workflow` reach the acquisition path that exists in the controller?

**Status: OPEN — needs a product/composition decision. Blocking the only part of S5P1
STEP2 that remains.**

### What is already true (measured, not inferred)

The controller path is complete and proven at the composition boundary (`e4e9561`,
E517): `run_workflow(acquisition=AcquisitionSubstrate(...))` admits a plan selected by an
in-run `PlannerDispatchKind.ACQUISITION` planner, with `admission-without-planner`,
clarification, bootstrap and unparseable-choice all refused before the coder runs;
`_pinned_acquisition_substrate` builds that substrate from a real `pin_reader(plan_ref=None)`
view and stops it in `finally`. 55 tests, mutation 4/4 + 6/6 + 5/5 + 4/4 + 5/5 + 8/8.

What does not exist: a caller. `workflow_tool.acquisition_refusal` still returns
`acquisition_unavailable` for a planner-first managed request, and `invoke_workflow` never
builds a substrate, because it has no access to one.

### The blocker, stated exactly

`_pinned_acquisition_substrate` needs `ctx.managed_execution` — the run's `ExecutionClient`
plus its `ExecutionBinding`. In `workflow_tool`, `WorkflowInvocationContext.managed_execution`
is populated from `parent_stage_lease.managed` (`cli.py:2491`), i.e. **the parent chat
stage's own writer grant**, deliberately, because `workspace.py` makes a second acquisition
of the same workspace `WORKSPACE_BUSY` by construction.

So the question is not "can we pass it" but which of two very different things the child
acquisition view is allowed to be:

**A — the child pins a READ view through the parent's client binding.** `pin_reader` takes
`peer`/`namespace` and mints a new `ViewRef` owned by `namespace.run_id`; it does not
acquire a writer. `_pinned_acquisition_substrate` already validates
`view.owner_run_id == managed.binding.namespace.run_id`, so it would accept a view owned by
the *parent* run and then read it on behalf of a *child* run — the same run identity used
for the child's admission record. That is either exactly right (§7's "parent remains the
trusted controller") or a real ownership leak across the child boundary. R26 exists
precisely to police child authority, so a reviewer cannot accept this by inspection.

**B — the child gets its own READ binding for acquisition**, and the parent's writer is not
shared across the suspension. This matches R26's "child PlanRef/acquisition ... without
child-authority leakage", but needs a composition change in the HANDOFF lifecycle
(`_begin_managed_child` / `_return_managed_child_to_parent`) and a decision about whether a
READ-only acquisition binding may coexist with the parent's suspended writer grant —
`WORKSPACE_BUSY` currently says no second *acquisition*, and whether a pure READ pin counts
is a supervisor policy question, not a controller one.

### Why this is escalated rather than chosen

Both options are defensible, they differ in what R26 must then prove, and the difference is
visible only on a live supervisor (`BACKEND_UNAVAILABLE` in this sandbox: no Docker). Picking
one now would also fix the shape of `acquisition_refusal`'s removal and of the Q146 view
lifecycle across a HANDOFF — three contracts decided by one convenience edit.

### Senior recommendation: **A**, scoped narrowly

Reasoning: §7 and Q61 keep the trusted parent as the controller, and the acquisition view is
read-only observation, which is the one capability that does not need to be duplicated to be
safe. Concretely: the child's acquisition stage would pin READ through the parent binding,
the resulting view stays owned by the **child run id** (so `_pinned_acquisition_substrate`'s
owner check keeps its meaning and R26's "no child-authority leakage" is about writes, which
stay parent-bound and suspended), and `acquisition_refusal` drops the managed branch while the
legacy branch keeps `acquisition_unavailable`.

If the operator prefers B, the HANDOFF lifecycle becomes this step's next task and the
controller code above is unchanged — which is the useful property of having built it as a
substrate rather than a thread through `invoke_workflow`.

Whichever is chosen, the following is **not** solved by either option and stays open:
bootstrap (`prepare_bundle` → `install_project` is authority-gated and served, but no
inner-loop path renders and installs a new project; there is no install caller and no
read-back-and-admit sequence).
