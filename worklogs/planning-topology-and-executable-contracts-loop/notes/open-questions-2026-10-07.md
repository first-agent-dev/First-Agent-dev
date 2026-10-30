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

**Status: OPEN. CT97 remains recommended, not operator-ratified.** This decision gates coder
write-boundary implementation and any claim that the active plan is protected.

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

**Context.** E288 gives `WorkflowContext`/`run_workflow` an explicit `CandidatePlanPublisher` port and provides `ExecutionClientPlanPublisher`. The ordinary CLI/session composition currently has no `ExecutionClient` owner and does not expose the trusted `NamespaceRef`, workspace ID, OWNER capability, or latest `base_revision` at the workflow boundary. Inventing those values in the CLI, borrowing a caller/model value, or reconstructing an OWNER grant would violate the existing authority model. The controller therefore fails closed when the port is absent; the host-path writer is deleted and must not be restored.

**Impact.** Managed candidate repair/replan cannot yet publish through the new route from the ordinary CLI. The component, protocol and service paths are locally tested, but Q89 is not production-enabled and SLICE3 STEP3/SLICE4 remain open. Live host evidence remains deferred; I03-LIVE-23's frozen OWNER-grant oracle is not evidence for this route.

**Options for the planner/managed-session owner.**

1. **Preferred: inject from the managed SessionManager/RunContext composition.** Pass the real client and bindings acquired by the existing managed workspace lifecycle; refresh the publisher's base only from confirmed PUBLISH results. This keeps authority and lifecycle ownership at the existing manager boundary.
2. **Compose at the CLI boundary only if the manager provides a typed binding.** The CLI may assemble the adapter, but it must receive trusted client + namespace/workspace/capability/base as one validated managed binding; it must not discover, mint, or infer them itself.
3. **Keep promotion disabled until that composition lands.** The current fail-closed port remains; no host writer or alternate protocol is reintroduced. This is the safe current state, not production completion.

**Requested resolution.** Planner assigns the implementation owner/step and chooses 1 or 2 for the eventual composition; option 3 remains active meanwhile. Do not change E2E baselines or run a host test as a substitute for this ownership decision.
