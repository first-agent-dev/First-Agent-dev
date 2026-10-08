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

    source: str | None   # the mutated text; None unless it is safe to run
    targets: int         # definitions whose qualified name is the directive symbol
    edits: int           # bodies neutralised (0 or 1) / call sites silenced (0..n)
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
