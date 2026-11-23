# What entities does verification actually need? (analysis behind Q-V2-SLICE3-1)

Written 2026-11-22, after the CT-3.6 verifier half landed (E615). The question was "what artifact does a sealed
verification write" and the options were two files / a widened record / a replacement. Asking it that way was
already a mistake: an artifact is a storage choice, and storage choices should fall out of the entities the
workflow has to carry. So this starts from the purpose.

## The purpose, stated as questions

The workflow's verification step exists to answer three questions and nothing else:

1. **Was this claim executed against this candidate?** — a *claim* is a contract (`CT-x.y`) with its `TEST-ID` and
   one sealed nodeid. The answer is per claim, never per suite: "the suite was green" is the exact sentence CT-3.4
   forbids.
2. **By which bytes, at which revision, on which substrate?** — the oracle is a seal (plan digest, closure digest,
   sealed revision), the thing judged is a *different* revision (the candidate), and the place it ran is a pinned
   read-only cell. Without all of that an outcome is an anecdote.
3. **May the candidate proceed — and if not, what exactly must the coder change?** — a verdict plus a repair
   target, both derivable from (1) and (2), neither of them a stored authority.

## Entities that follow from those questions

| Entity | What it is | Why it is irreducible |
|---|---|---|
| **ClaimEvidence** | `(contract_id, test_id, nodeid, outcome, detail)` | This is the unit (1) is asked about. `outcome ∈ {passed, failed, skipped, error}`, and `error` must stay distinct from `failed`: "the oracle could not run" is not "the code is wrong", and collapsing them is how a broken cell reads as a red test. |
| **RunIdentity** | `(route, plan_sha256, seal_sha256, closure_sha256, sealed_revision, candidate_revision, profile_id, substrate, run_id, attempt, repair_round, mode)` | (2) is not a comment on the evidence, it *is* the evidence's validity. Two revisions because the oracle must not move while the code does — that difference is the whole claim of a pinned run. |
| **CommandRun** | `(command, outcome, exit_code, stdout_tail, stderr_tail, duration_s)` | Evidence has to be produced by something. Keeping the command is what makes "the cell ran it" checkable instead of asserted. |
| **Verdict** | derived: `blocking`, the first blocking reason, repair targets | (3) must be a *function* of the above, recomputed on read. Stored as authority it can go stale and claim a pass nobody can reproduce. |

Nothing else is needed. In particular `slice_id`, `test_paths` and the per-slice command list are **scaffolding for
the legacy route**, not entities: they exist because planner-authored `verify` fences are per slice, and they
disappear from the V2 route the moment the fence is retired.

## What today's record actually is

`SliceVerification` / `PlanVerification` (`slice_verification.py:2313`, `:2336`) are built around (4) with (1) only
implicitly present:

- `command_results` **is** `CommandRun` per slice — kept.
- `kill_checks: tuple[(contract_id, KillCheck)]` is a *mutation* verdict attached to a contract, not "did the sealed
  test for this contract execute and pass".
- `failed_nodeids` is slice-wide, so attribution to a contract is not structural.
- **`RunIdentity` is absent from the type entirely.** `mode`, `repair_round` and `plan_ref` are added by the writer
  (`workflow_controller.py:765–811`); the seal, the closure digest, the sealed revision and the candidate revision
  are nowhere in the record. A `verification.json` attempt cannot say which oracle it belongs to.

That absence, not the file layout, is what Q-V2-SLICE3-1 was really about: on the V2 route the artifact would
record outcomes with no way to bind them to the seal that produced them.

## The minimal surface, and why the three options were the wrong question

One attempt entity, one log:

```
VerificationAttempt := RunIdentity + [ClaimEvidence] + [CommandRun] + Verdict + errors
```

- **V2 route** (`route="sealed"`): one `CommandRun` (the sealed argv), one `ClaimEvidence` per sealed selector, plus
  the seal's `attested`/`pending` contracts so the total stays honest (D-V2-12).
- **Legacy route** (`route="planner-fence"`): today's records, unchanged, as that route's contribution.

Because a route is a *value inside the attempt*, one append-only log still describes every attempt a run made, and a
reader never guesses: `route` is mandatory and the other half of the schema is empty by construction.

Which kills the original options:

- **(A) a second file** duplicates the log machinery and the attempt counter, and forces every reader to join two
  files by attempt index. That join is the drift this project keeps paying for; it also makes "which attempts
  happened, in order" a property of two independent writers.
- **(C) replace the artifact** destroys the only record the frozen legacy route produces, and operators currently
  read `verification.json` to decide whether to move a project to enforce mode (`feature_flags.py:59`).
- **(B) widen the record** is the right shape but the wrong reason: not "an optional block readers must ignore" but
  "the attempt becomes route-tagged and gains the identity it never had". Legacy keys stay, populated only by the
  legacy route, so no existing reader has to learn a new file and no new reader has to learn a missing field.

## Consequence for CT-3.6's wiring half

The controller branch becomes mechanical: on the V2 route call `verify_sealed_acceptance`, project its result into
the same attempt shape with `route="sealed"`, and never call `verify_plan(plan_ids, …)` — which is what actually
retires the planner fence. Two properties must be tested at that point, and neither is provable today:

1. a plan carrying a hostile `verify` fence produces **zero** executions on the V2 route (the fence cannot drive a
   result even when it exists);
2. an attempt's `identity` cannot be absent or partial — a sealed attempt without its seal/revisions is refused at
   write time, not repaired by a reader.

The 7 call sites that consume `verification.blocking` are unchanged by this: `blocking` stays a derived field, now
computed over claims instead of slices on the sealed route.

---

# Adversarial pass (same day): where the first version breaks

I attacked the surface above as if a reviewer wanted it rejected. Eight findings; six change the design, one is a
naming fix, one is a hole I am deliberately leaving open with a reason. The revised surface follows.

## F1 — the design silently drops mutation evidence (accepted: biggest defect)

`ClaimEvidence` as I specified it answers only "did the sealed test execute and pass". But verification also runs
**kill checks** — a mutation per `FUNCTIONAL` contract, whose verdict is whether the mutation *died*. Today that is
`SliceVerification.kill_checks: tuple[(contract_id, KillCheck)]`, a second structure keyed by the same contract id.
Leaving it out would mean the artifact holds one row per contract for execution and a *parallel* array for mutation,
i.e. the reader joins two structures by contract id — the same class of defect the whole exercise is avoiding.

**Change:** one row per contract, with the mutation folded in as a nested field:
`ClaimEvidence(contract_id, test_id, nodeid, outcome, mutation: MutationEvidence | None, detail)`.
A contract with no kill directive carries `mutation=None` (not `False`: absent ≠ survived).
The legacy route keeps `kill_checks` verbatim — it is the frozen route, and rewriting its shape buys nothing.

## F2 — `route` conflates two axes (accepted: makes an invariant checkable)

I used one field, `route: sealed | planner-fence`, for two different questions: *which grammar* the plan is written
in, and *who authored the command* that produced the evidence. They coincide today, but they are independent: a V2
run still runs harness-issued mutation probes, and a legacy run could one day be driven by a harness command.
With one field, "the planner fence never drives a V2 result" is true only *by omission* — the artifact simply has no
planner commands on that route, and nothing can catch a consumer that reintroduces one.

**Change:** `identity.route ∈ {v2, legacy}` (grammar), and every `CommandRun` carries
`authored_by ∈ {planner, harness}`. The CT-3.6 property then becomes a checkable invariant rather than a shape:
**on `route == "v2"` no `CommandRun` may have `authored_by == "planner"`**, refused at write time. That is a test
that fails the day someone wires the fence back in.

## F3 — absence reads as a pass (accepted: totality must be carried)

`claims[]` holding only executed selectors means a contract whose selector silently vanished is indistinguishable
from one that passed: the reader must fetch the seal and diff. D-V2-12 already established the fix on the seal side
(sealed selectors + `attested` + `pending` = `contracts_total`); the attempt must carry the same totality, or the
artifact is weaker than the thing it describes.

**Change:** `claims[]` covers the seal's whole total. `outcome` extends to
`{passed(failed, skipped, error, attested, pending)}` — the last two are the seal's own vocabulary, so a claim that
is carried by a named party (`attested`) or owed to a host (`pending`) can never be read as proven by the oracle.
A `claims[]` shorter than `contracts_total` is refused at write time.

## F4 — "refused" and "empty" are the same shape (accepted)

A run refused before executing (no substrate, drifted seal, malformed candidate) produces zero claims and an
`errors` entry. A reader cannot tell that from a truncated artifact, and the eval renderer would print an empty
evidence block as if nothing was wrong.

**Change:** attempt-level `outcome ∈ {executed, refused}`, alongside `errors`. `refused` implies `blocking = true`;
`executed` with zero claims is refused at write time as inconsistent.

## F5 — `candidate_revision_id` was an assertion, not evidence (accepted: the sharpest finding)

The caller passes the revision string. Nothing proved the pinned view was actually at it, so the artifact could
faithfully record a revision that never ran the oracle — the exact failure mode ("a record that names an identity it
did not use") this project keeps paying for.

Two facts make this fixable rather than merely notable: `ReadOnlyManagedBashExecutor` holds the authority's view
(which names its revision), and the controller already has both ends in `ctx.managed_revision_pair`
(`base_revision_id`, `target_revision_id`).

**Change:** the substrate must *name* the revision it is pinned at, and `verify_sealed_acceptance` refuses a
disagreement (`verifier-revision-mismatch`) instead of recording the caller's claim. A substrate that cannot name
its revision is refused too — "I ran somewhere" is not an identity. `RunIdentity.sealed_revision_id` comes from the
seal, `candidate_revision_id` from the substrate, and equality with the caller's expectation is checked, never
assumed.

## F6 — free text in an artifact the model reads (accepted: bound it, and label it)

`detail` will carry assertion text and command tails — coder-influenced bytes — into the eval context. The rest of
the pipeline already treats that as untrusted (`_tail`, `EVIDENCE_TAIL_LIMIT`); a new field must not be the one
place that forgets.

**Change:** `detail` is bounded (single-line normalised, ≤ 2000 chars), and the renderer prefixes it as untrusted
text. A schema rule, testable without a model in the loop.

## F7 — naming (accepted, cosmetic)

`RunIdentity` collides conceptually with `RunContext`, and `sealed_revision`/`candidate_revision` are inconsistent
with the codebase's `*_revision_id`. **Change:** `VerificationIdentity`, `sealed_revision_id`, `candidate_revision_id`.

## F8 — the legacy route stays identity-blind, and that is a deliberate exception (kept, stated)

Making `identity` mandatory on both routes would be the cleaner rule, but the legacy route is frozen and being
retired (D-V2-1/D-V2-2), and forcing identity into it means touching every attempt it writes for no consumer that
survives. **Decision:** `identity` is mandatory on `route == "v2"` and optional on `route == "legacy"`, which is
written down here rather than left to be discovered. When the legacy route is deleted, the field becomes mandatory
for the one route that remains and the rule tightens by deletion, not by edit.

## Revised surface

```
VerificationAttempt := outcome("executed"|"refused")
                    + identity: VerificationIdentity      # mandatory on v2
                    + claims: [ClaimEvidence]             # covers the seal's total
                    + commands: [CommandRun(authored_by)] # v2: harness only, enforced
                    + verdict: derived (blocking, first reason)
                    + errors

ClaimEvidence      := (contract_id, test_id, nodeid, outcome, mutation: MutationEvidence | None, detail)
MutationEvidence   := (operator, path_or_symbol, verdict, detail)
VerificationIdentity := (route, plan_sha256, seal_sha256, closure_sha256,
                         sealed_revision_id, candidate_revision_id, profile_id, substrate,
                         run_id, attempt, repair_round, mode)
```

Three of these findings (F2, F3, F5) are the ones that would have cost real debugging later: F2 because the fence
could come back unnoticed, F3 because a vanished selector would read as green, F5 because the artifact could vouch
for a revision it never ran. F1 is the one that would have produced a permanently awkward artifact. F4, F6, F7 are
cheap correctness. F8 is the honest exception.

**Nothing in this section is implemented yet.** The code that exists (`verify_sealed_acceptance`, E615) returns the
narrower `SealedVerification` and takes `candidate_revision_id` on trust — F5 and F3 change its signature and its
refusals, so implementing the schema first and the wiring second keeps each step green.

---

# Do the findings hold? (checked against the code, not against my summary)

Each finding below is re-derived from a quoted location. Verdicts: **real**, **shrinks** (the defect is smaller and
the fix different), **grows** (worse than stated), or **not a defect**.

## F1 — mutation evidence dropped: **REAL, and worse than stated**

`SliceVerification.kill_checks: tuple[tuple[str, KillCheck], ...]` is populated per contract by `verify_slice` and
consumed at four places (`workflow_controller.py:746` payload, `:871` block detail, `:1125` evidence renderer, plus
the slice verdict). `plan_v2.py:563` parses `KILL-TARGETS`, and SLICE3's own intent says the mutation runner is
STEP9A's and "MUST NOT" be reimplemented. So kill evidence is part of V2 verification, and an artifact that carries
only `(claim → passed)` would need a second array keyed by the same contract id.

**It is worse than that.** The verifier I landed in E615 never runs a mutation: `verify_sealed_acceptance` proves
"the sealed nodeid executed and passed" and nothing else. A `FUNCTIONAL` contract with a `KILL-TARGETS` directive
would therefore be recorded as proven by an attempt whose mutation never ran. That is not a schema gap, it is a
defect in the landed code — recorded as **F9** below.

**Correction:** one row per contract, `mutation: MutationEvidence | None`, plus a write-time rule —
`claim-mutation-missing`: a claim for a contract that declares a kill directive may not have `mutation=None`, and a
`MutationEvidence.verdict` from the closed `KILL_CHECK_VERDICTS` set. `None` therefore means exactly "this contract
declares no kill target", never "did not get to it".

## F2 — route conflates two axes: **REAL (structural, provable by construction)**

`verify_slice` runs `record.commands` — planner-authored text — through `run_commands` (`slice_verification.py:2394`
and `:624`), while `capture_test_nodeids` (`:882`) and the kill runner (`:1969`) issue harness-built commands through
the *same* `run_commands` and the *same* `executor`. The artifact's `commands` array (`workflow_controller.py:745`)
therefore mixes both provenances with no marker, and the only way to tell them apart downstream is to remember which
slice of history produced them.

**Correction:** `CommandRun.authored_by ∈ {planner, harness}`, and `identity.route ∈ {v2, legacy}` for the grammar.
Invariant at write time: `route == "v2"` ⇒ no command is `planner`-authored (`fence-on-v2-route`). That is what makes
CT-3.6's retirement statement checkable rather than true-by-omission.

## F3 — absence reads as a pass: **REAL (artifact-level)**

`_slice_verification_payload` (`workflow_controller.py:739–763`) emits `verdict`, `test_paths`, executed `commands`,
`kill_checks`, `regression_nodeids`, `failed_nodeids`, `detail` — and **no expected set and no total**, while the seal
carries `contracts_total` (`acceptance_bundle.py:149`) and its attested/pending split. So "the seal promised 12
contracts, this attempt covered 11" is not answerable from the artifact at all. At *runtime* the gap is refused
(`run_sealed_acceptance` → `sealed-test-missing`), which is why this is an artifact defect and not a correctness hole.

**Correction:** `claims[]` covers the seal's total; write-time rule `claims-total-mismatch` when
`len(claims) + len(attested) + len(pending) != contracts_total`. **Implemented differently from this first draft,
and better:** `attested`/`pending` do *not* become claim outcomes. The seal already keeps them as two lists beside
`selectors`, and re-encoding "proven by the oracle" vs "carried by a named party" vs "owed to a host" as three
values of one enum would be a second vocabulary for one idea — the attempt now carries the same two lists the
seal does.

## F4 — "refused" vs "empty": **SHRINKS to an invariant, no new field**

Checked the refusal path: the controller catches any exception and builds `PlanVerification(errors=(...))`
(`workflow_controller.py:1792–1796`), `blocking` is true whenever `errors` is non-empty (`:2346`), and
`_verification_is_indeterminate` (`:839`) is consulted before the gate is applied (`:902`). So refusal *is* handled;
what does not exist is anything that stops a writer from emitting an empty claim set with no errors, which would read
as "nothing to check".

**Correction:** no `outcome: executed|refused` field — it would be redundant state that can disagree with `errors`.
Two invariants instead: `claims` non-empty ⇒ no `errors` describing a refusal is required to agree, and the converse,
`claims` empty ⇒ `errors` non-empty (`empty-attempt-unexplained`). Fewer fields, same guarantee. This is the
simplification the adversarial pass was looking for.

## F5 — candidate revision asserted: **REAL (and the fix has an exact anchor)**

`ViewRef` (`execution/types.py:63–70`) carries `base_revision` — the authority-named revision a view is pinned at —
and `ReadOnlyManagedBashExecutor` holds it privately (`client.py:1578`: `self._view = view`) with **no public
accessor**, while `ManagedVerifyCommandExecutor` (`slice_verification.py:476–501`) exposes nothing about the view it
wraps. The controller does hold both ends (`ctx.managed_revision_pair.base_revision_id/target_revision_id`,
`workflow_controller.py:322`, `:1201`), so the expected value exists — it is simply never compared with the substrate.

**Correction:** the substrate must name its revision (`view_revision_id`, a public read-only property forwarded by the
wrapper), and `verify_sealed_acceptance` refuses `verifier-revision-mismatch` on disagreement *or* absence. Identity
then comes from the thing that ran, and the caller's value is an expectation that can fail.

## F6 — free text into the eval context: **REAL, and sharper than "unbounded"**

The block *is* bounded, but at the wrong end: `_verification_evidence_lines` renders per-field text unbounded
(`:1117` slice detail, `:1126` kill-check detail) and then cuts with `rendered[:EVAL_VERIFICATION_MAX_CHARS]`
(`:1136–1140`) — a **head** truncation. One long `detail` on the first slice therefore *evicts the rest of the
evidence*: later slices, failing nodeids and errors never reach the model, while the footer still says "full artifact:
<path>". Command output is already bounded (`TAIL_LIMIT`, `:582`), so `detail` is the one field that can starve the
block.

**Correction:** bound each field where it is produced (single-line normalised, ≤ 2000 chars, with an explicit
`…[truncated]` marker), and render it as untrusted text. Bounding the payload keeps the truncation honest; bounding
the renderer alone does not.

## F7 — naming: **REAL but cosmetic**

`RunIdentity` next to `RunContext`/`ExecutionBinding`, and `sealed_revision` inconsistent with the codebase's
`*_revision_id` (`ViewRef.base_revision`, `GrantReply.revision_id`). **Correction:** `VerificationIdentity`,
`sealed_revision_id`, `candidate_revision_id`.

## F8 — legacy stays identity-blind: **REAL, deliberate exception, unchanged**

Making `identity` mandatory on the frozen route would mean rewriting attempts for a route being deleted (D-V2-1,
D-V2-2). Kept as stated: mandatory on `v2`, optional on `legacy`, and the rule tightens by deletion.

## F9 — NEW: the landed verifier records a pass without the mutation (**REAL, code defect in E615**)

`verify_sealed_acceptance` (`acceptance_collection.py`) collects the sealed closure and asserts every selector's
nodeid executed; it never runs `_run_kill_check`. Combined with F1's rule, an attempt it produces for a plan with
`KILL-TARGETS` is *incomplete*, and today it is not even labelled as such — it simply has no mutation records.

**Correction:** the verifier composes with STEP9A's existing mutation runner instead of reimplementing it (SLICE3's
intent forbids a second runner): a public `run_kill_checks(...)` seam over `_run_kill_check`, called per contract with
a directive, with results folded into `ClaimEvidence.mutation`. Until that exists, `verify_sealed_acceptance` must
**refuse** to project an attempt for a contract that declares a kill directive (`claim-mutation-missing`) rather than
return an artifact that reads as proven.

## Verdict

Six are real as stated, one shrinks to an invariant (F4), one is cosmetic (F7), one is a stated exception (F8), and
the check found a ninth — a defect in the code I already landed, not just in the proposed schema. F9 and F1 together
mean the sealed verifier is *not yet able to produce a truthful attempt for a functional contract*; that is the first
code step, ahead of the controller wiring.

## Final schema (what the plan now carries)

```
VerificationAttempt                  # one per attempt, append-only log entry
  route:      v2 | legacy            # grammar; decides which half is populated
  identity:   VerificationIdentity   # mandatory on v2, optional on legacy (F8)
  claims:     [ClaimEvidence]        # covers the seal's total (F3)
  commands:   [CommandRun]           # authored_by marks provenance (F2)
  blocking:   derived                # never read as authority
  errors:     [text]                 # empty claims ⇒ non-empty errors (F4)

VerificationIdentity := route, plan_sha256, seal_sha256, closure_sha256,
                        sealed_revision_id, candidate_revision_id,   # candidate from the substrate (F5)
                        profile_id, substrate, run_id, attempt, repair_round, mode

ClaimEvidence        := contract_id, test_id, nodeid,
                        outcome: passed|failed|skipped|error,          # never attested|pending (F4)
                        mutation: MutationEvidence | None,            # None only when no KILL-TARGET (F1)
                        detail: bounded 2000 chars, single line (F6)

MutationEvidence     := operator, path_or_symbol,
                        verdict ∈ {v.value for v in KILL_CHECK_VERDICTS}, detail (bounded)
CommandRun           := command, authored_by: planner|harness, outcome, exit_code, tails, duration
```

Write-time refusals: `claims-total-mismatch`, `claim-mutation-missing`, `fence-on-v2-route`,
`empty-attempt-unexplained`, `verifier-revision-mismatch`, `identity-missing-on-v2`.

---

# F10 — measured while ordering the work: on the V2 route, verification is green by emptiness

Asking "what runs today on a `PLAN-V2` run" produced the finding that matters more than F9 this turn.

`PlanSnapshot.ids` is **empty by design** for a V2 snapshot — `plan_admission.py:74–76` says so, and `:401` constructs
`ids=PlanIds()` with the parsed `graph` beside it, deliberately, so the V1 extractor never judges V2 bytes. The
verification call site does not know that: `workflow_controller.py:1757` passes exactly those `ids` to
`verify_plan(plan_ids, …)`, and `_stage_plan` (`:1335–1337`) returns `ctx.admission.snapshot.ids`.

Measured, not inferred (2026-11-22, on this tree):

    verify_plan(PlanIds(), root=<tmp>)  ->  plan commands: ()   slices: ()   errors: ()   blocking: False

So on the V2 route the whole verification stage runs nothing, reports nothing, and satisfies `blocking is False`
in enforce mode. The gate is not merely missing a fence — **there is nothing for it to say, and it says "ok"**.
That is a strictly worse condition than F9: F9 was "the verifier could record a pass it did not measure"; F10 is
"the verifier measures nothing and the gate reads that as a pass", today, on the only forward grammar.

Two consequences for the order of work:

1. **The projection and the controller branch are the urgent half, not the mutation runner.** The sealed verifier
   already measures the right thing; nothing hands its result to the gate. F9's guard stays as the rail that keeps
   the projection honest, but its trigger cannot fire on today's grammar — see 2.
2. **F9's premise narrows, and the earlier report over-claimed.** The V2 grammar's `KILL-TARGETS` entries are
   `KillTarget(target_id, ct, test_id)` (`plan_v2.py:509–518`): *attribution*, not an executable mutation — no
   operator, path or symbol. `_run_kill_check` needs `KillDirective(operator, path, symbol, …)`, so no mutation can
   be constructed from a V2 plan at all, and CT-3.4's "target pass remains VACUOUS on the V2 route" is consistent
   with that. The `kill_required` refusal therefore protects a future route that carries executable directives; it
   did not make today's V2 results false, and this note and the ledger say so rather than leaving the stronger claim
   standing. `kill_required` is empty for a V2 attempt, and the attempt's `mutation=None` means "no executable
   mutation declared", which is the truth on this grammar.

F10 also sharpens what CT-3.6's wiring must prove, and it is not only "the fence does not run":

* a V2 attempt for a plan whose sealed nodeid fails must be **blocking** (today nothing runs, so nothing blocks);
* a V2 attempt must never be produced with an empty claim set (the entity refuses it: `empty-attempt-unexplained`);
* `verify_plan(PlanIds(), …)` must stop being reachable on the V2 route, i.e. the branch is on the *snapshot grammar*,
  not on "are there commands".

## Ordered remaining work (recorded so it is not re-derived)

1. **Projection** — `sealed_attempt(bundle, verification, identity)` → `VerificationAttempt`: claims from
   `bundle.selectors` × `verification.run.outcomes`, `attested`/`pending`/`contracts_total` from the seal, one
   `harness`-authored `AttemptCommand`, and identity fields proved against the bundle (seal, closure, plan, sealed
   revision) plus `candidate_revision_id == verification.candidate_revision_id` (`verifier-revision-mismatch`).
2. **Substrate-named revision (F5)** — `ReadOnlyManagedBashExecutor.view_revision_id` (from `ViewRef.base_revision`),
   forwarded by `ManagedVerifyCommandExecutor`, required by `verify_sealed_acceptance`; a view that disagrees with
   the caller is refused.
3. **Controller branch** — on `snapshot.format == PLAN_V2` call the sealed verifier and write the attempt; never call
   `verify_plan(ids)` there (F10). Proven by: a plan with a hostile `verify` fence produces zero executions on the V2
   route, and a failing sealed nodeid makes the attempt blocking.
4. **Artifact writer** — emit `route` + `identity` + `claims[]` in the attempt log, keep the legacy keys for the
   legacy route, and render claims (bounded detail, `UNAVAILABLE`/untrusted label) in the eval block.
5. **`run_kill_checks` seam** — only if a route can declare executable mutation directives; today none can, so this
   is *not* on the critical path and must not be built speculatively (SLICE3's intent forbids a second runner, and
   there is nothing to run).

## F10 — landed: the projection, and the total rule it corrected

Item 1 of the ordered list is implemented: `sealed_attempt(bundle, verification, *, identity)` in
`acceptance_collection.py`, with `_claim_outcome`, `_require_command`, `_require_identity_matches` and
`_require_run_matches` beside it. Claims are `bundle.selectors × verification.run.outcomes` — a selector with no
outcome becomes `outcome="error"` with the detail *"the sealed selector produced no nodeid in this run"*, never
`skipped`, because "did not execute" and "failed" are different facts and only one of them is a coder's bug. One
`AttemptCommand.from_result(verification.command, authored_by="harness")`; `attested`, `pending` and
`contracts_total` come from the seal; `kill_required == ()` for the reason recorded above.

**Two things had to be fixed to make the join honest, and both were measured rather than assumed:**

1. **The receipt had no command.** `SealedCollection`/`SealedVerification` recorded argv, nodeids and outcomes but
   not the `CommandResult` that produced them, so the projection had no provenance to carry. Both now hold
   `command`, and a collection that cannot name its own command is refused (`collection-no-command`) instead of
   being projected as if it were evidence.
2. **`claims-total-mismatch` was wrong for every real seal.** The attempt counted
   `len(claims) + len(attested) + len(pending) == contracts_total`. Measured on the fixture seal:
   `contracts_total=2`, `selectors=(CT-1.1,)`, `attested=("CT-1.2",)`, `pending=("CT-1.2",)` — because
   `acceptance_bundle` requires `pending ⊆ attested` (`:601`). The seal's `pending` is a *deploy qualifier on an
   attestation*, not a third disjoint bucket, so the sum is 3 against a total of 2 and the projection of a correct
   verification was refused. The rule is now a **coverage** rule: one contract id per claim (`claims-total-mismatch`
   if a contract is claimed twice), no contract both claimed and excused, and
   `len(claims) + len(attested ∪ pending) == contracts_total`. The sum rule's mutant dies against
   `test_a_pending_contract_that_is_also_attested_is_counted_once`; the intersection-removal mutant dies against
   `test_a_contract_cannot_be_claimed_and_also_excused`; the dropped-contract case (F3's original purpose) is still
   refused because coverage falls short.

**What the projection refuses, each with a test that dies when the rule is removed:** `verifier-revision-mismatch`
(the caller's candidate is not the verification's candidate), `verifier-identity-mismatch` (any of plan/seal/closure/
sealed-revision disagrees with the bundle, **or** the `SealedRun` itself carries another seal's digests — a frozen
run can be swapped in after the fact, which the identity fields alone cannot see), `collection-no-command`, and the
attempt's own `attempt-<rule>` translations.

**Measured:** `tests/test_v2_sealed_attempt.py` 10 oracles, `tests/test_v2_verification_attempt.py` 23; bundle
targeted bucket 314 passed; `ruff` clean, `ruff format` clean, mypy 62 raw (unchanged against the `head-c41df3e-f9`
recording), `fa authoring-check` diagnostics 0. Seven hand-built mutants, all killed: drop `_require_run_matches`,
drop the revision refusal, drop the identity refusal, make a missing outcome `passed`, drop the harness authorship,
restore the three-list sum, drop the claim/excused intersection.

**Still not done, and next in order:** the controller branch (item 3) is the *only* thing that makes F10's green-by-
emptiness stop, because the projection has no caller on the V2 route yet — `_stage_plan` still passes
`PlanSnapshot.ids` to `verify_plan` (`workflow_controller.py:1757`). Item 2 (F5, substrate-named revision) is what
gives `identity.substrate`/`candidate_revision_id` a value the verifier can prove rather than receive.

## F5 — landed: the substrate names the revision, the verifier refuses the disagreement

`candidate_revision_id` was an assertion: the caller typed a revision and the artifact recorded it as though
something had checked. Three small pieces make it evidence, and none of them creates a new trust boundary:

* `ReadOnlyManagedBashExecutor.view_revision_id` — the authority's own `ViewRef.base_revision`, or `None` before a
  view is pinned and after `suspend()` (`client.py`). `None` is the honest answer for "no view"; returning `""`
  would let a blank caller revision compare equal by accident.
* `ManagedVerifyCommandExecutor.view_revision_id` — forwards only. It is where verification is *judged*, so it must
  not become a place where the identity is invented: a wrapped executor with no answer, or a blank one, yields
  `None`.
* `acceptance_collection._require_named_revision(executor, candidate_revision_id)` — called after the plan and seal
  checks and **before** any cell command: a substrate that cannot name its revision, or names another one, is refused
  with `verifier-revision-mismatch`. `prepared == {}` in both oracles, so the refusal provably precedes execution.

The ordering is deliberate and was checked against the existing oracles: the drift (`seal-byte-drift`) and nodeid
checks happen while collecting, i.e. *after* this refusal, so every existing refusal keeps the rule it was recorded
under rather than being re-labelled by the new check.

**Measured:** 6 hand-built mutants, all killed — drop the refusal, disable the comparison, make the wrapper return
`None` always, make it forward blank strings, make the client return `None` always, make it return `""` when
suspended. `tests/test_slice_verification_runner.py` now constructs a real `ReadOnlyManagedBashExecutor` (a real
`ViewRef`/`GrantReply`/non-interactive `ExecutionProfile`, an unconnected client) rather than a stand-in, plus four
forwarding oracles; `tests/test_ai_native_acceptance_collection.py` gains "cannot name", "names another" and "names
the candidate and therefore runs" (the last one through the real in-band substrate). The S0 probe asserts
`substrate.view_revision_id == managed.current_revision_id` inside the xfail, i.e. it becomes a proof of this seam on
the W4 host rather than a parallel claim.

**What this does not do:** `verify_sealed_acceptance` still has no production caller — `_stage_plan` reaches
`verify_plan(PlanIds())` (F10). Item 3, the controller branch, is next.

## F10 — closed: the V2 stage branches on the snapshot's grammar

Item 3 is implemented in `workflow_controller`. `_run_stage`'s coder gate now reads
`_sealed_snapshot(ctx)` — the admitted snapshot when its `format` is `PLAN-V2`, else `None` — and on that
route calls `_sealed_stage_verification(...)` inside the same pinned substrate. **`verify_plan` is not reached
on the V2 route at all**: not with a guard, and not with the empty `ids` a V2 snapshot carries by design. The
`verify` fence therefore has no way to become the oracle, which is the property the earlier "green by
emptiness" measurement showed was missing.

What the sealed path does, in order, and each step is a recorded `PlanVerification` error rather than a raised
exception, so the existing enforce/observe gate keeps judging it:

1. `_stage_acceptance_bundle` — `load_seal(workspace / acceptance.seal.json)`; missing (`acceptance-seal/missing`),
   malformed (`acceptance-seal/<rule>`) or unreadable (`acceptance-seal/unreadable`) is blocking. There is no
   fallback to the fence: that fallback *is* the defect.
2. no substrate → `verifier-substrate-required`, because the unmanaged substrate is the host tree the coder just
   edited (CT61).
3. the substrate must name the candidate revision (F5) → `verifier-revision-mismatch`.
4. `verify_sealed_acceptance(..., kill_required=())` → failures surface as `sealed-verification/<rule>`.
5. `sealed_attempt(...)` → `sealed-attempt/<rule>`; a blocking attempt contributes
   `sealed-attempt/<first_reason>` so the legacy gate blocks *and says why*.
6. the receipt (`verification.command`) becomes `plan_command_results`, so a passing V2 stage has one command that
   actually ran and a blocking one has an error — never an empty command list reading as green.

The attempt is kept on `_WorkflowAdmission.last_attempt` (and cleared to `None` when the legacy route runs) for the
artifact writer, which is item 4 and is **not** done: `verification.json` today carries the receipt and the
reason, not the claims, identity or route.

**Measured:** `tests/test_verify_gate_live.py` 576 passed in 181 s, including four new oracles: the V2 stage never
reaches `verify_plan` (it is replaced by a recorder and asserted empty); the seal is read from the workspace and
the only remaining refusal is the cell; a V2 stage with a cell produces a sealed attempt whose claim is the sealed
nodeid and whose `blocking` is `False`; and a failing sealed nodeid blocks the stage. Five mutants, all killed:
force the legacy branch, make `_sealed_snapshot` always `None`, drop the substrate refusal, stop propagating a
blocking attempt, and pass a non-empty `kill_required`. The neighbouring controller files
(`test_s8_workflow_controller`, `test_injection_threading`, `test_kill_directives`, `test_plan_*`,
`test_s5p1_acquisition_seam`, `test_slice_id_validation`, `test_workflow_*`) were re-run: 149 passed.

**One structural constraint that shaped the change:** the live oracle's plan declares
`kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_plan` and
`...::_run_stage -> write_verification`, and it reports every one of those contracts `PROVEN` by mutating them. The
first attempt to satisfy `ruff`'s complexity limit extracted `verify_plan` into a helper, and the live test failed
— correctly: the mutation no longer applied, so the plan's own claim about its kill surface had become false.
`_run_stage` therefore keeps both call sites verbatim; the complexity was paid down by extracting the eval-report
build (`_stage_eval_report`) instead, which no kill directive names.

## F10 item 4 — landed: the artifact and the eval block carry the attempt

`write_verification` takes `attempt: VerificationAttempt | None`. When it is supplied the entry gains
`route`, `identity`, `claims`, `commands_authored_by`, `attested`, `pending`, `contracts_total`,
`kill_required`, `attempt_blocking` and `first_reason`, and its `blocking` is
`verification.blocking or attempt.blocking` — either face of the same evidence may block, so a disagreement
between the gate and the record cannot be smoothed into a pass. Every legacy key (`mode`, `repair_round`,
`plan_commands`, `slices`, `errors`) is untouched, and the legacy route passes `attempt=None`, so its entry
carries none of the new keys. This is additive by construction, not a schema swap, which is what lets the legacy
route keep reading the artifact it already reads.

The eval evidence block renders the attempt (`_claim_evidence_lines`): route, the authorship set, a shortened
identity line (`plan=… seal=… closure=… candidate=… sealed=…`), one line per claim with the harness's own
`proven`/`NOT proven` word, the mutation when one exists, and the claim's `detail` **labelled `untrusted` and cut to
`EVAL_CLAIM_DETAIL_MAX_CHARS = 300`** (F6: the artifact's 2000-character budget is per field, but the block has one
budget and ten fields, so re-using the wider bound would let coder-influenced text evict the diff). `attested` and
`pending` are rendered as different facts -- "not run here" and "deploy debt that does not block this attempt" --
because folding them was F3/F8's failure mode.

The block reads the attempt from `_WorkflowAdmission.last_attempt` rather than being threaded through every caller:
the gate and the evaluator then judge the *same* record, and a repair round that clears the field cannot leave a
stale attempt attached to a new candidate.

**Measured:** `tests/test_verify_gate_live.py` 581 passed in 180 s (five new oracles: the artifact carries
route/identity/claims beside the legacy keys; an attempt-less entry carries none of them; a blocking claim blocks
the record; the eval block labels and bounds the detail; and a coder stage writes the attempt it measured).
Six mutants, all killed: drop `attempt=` at the write site, never merge the attempt into the payload, stop OR-ing
the two `blocking` faces, drop the `untrusted` label, drop the detail cut, and drop the merge guard. Neighbouring
suites re-run: 134 passed (`test_workflow_artifacts`, `test_workflow_hygiene`, `test_s8_workflow_controller`,
`test_workflow_no_eval_terminal`, `test_injection_threading`, `test_kill_directives`).

**Where the ordered list now stands:** items 1–4 are landed. Item 5 (`run_kill_checks`) remains deliberately
unbuilt: on the V2 grammar a `KILL-TARGETS` row is `KillTarget(target_id, ct, test_id)` — attribution with no
operator, path or symbol — so there is nothing to mutate, and building the seam speculatively is what SLICE3's
intent forbids. The next real work on this arc is not in the list: the V2 route still has no production caller of
`_pinned_verify_substrate` that *reaches* a managed cell on this host, so the W4 host probe (S0) remains the proof
that the substrate half is live, and `run_workflow` on V2 with no cell is a *recorded block*, not a pass.

## F1 — the last schema gap, and it was an inversion (landed 2026-11-22)

F1 carried one rule that the entity did not implement: `MutationEvidence.verdict` must come from the runner's
closed set. Measured on the landed code, before any edit:

    closed vocabulary (production): ['error', 'producer_absent', 'proven', 'vacuous']
    MutationEvidence(verdict='proven')-> accepted, claim.proven = False   # the only value production can emit
    MutationEvidence(verdict='PROVEN')-> accepted, claim.proven = True    # a value production never emits
    MutationEvidence(verdict='SURVIVED' | 'bogus')-> accepted

So it was not merely unvalidated free text: the two readers (`ClaimEvidence.proven`, `VerificationAttempt.first_reason`)
compared against a literal `"PROVEN"` that no `KillCheck` can produce, while the real member read as *not proven*.
A vacuously-passing test under a survived mutation would have looked completed; a genuinely killed one, blocked. That
is F1's exact failure mode ("mutation evidence is part of the claim") reached from the other side.

**Change:** `MUTATION_VERDICTS = frozenset(member.value for member in KILL_CHECK_VERDICTS)` — **derived**, not a copy,
because `KillCheck` validates against the same set and two literals are how this drifted in the first place.
`MutationEvidence` refuses anything outside it (`mutation-invalid`, the closed rule it already used), and both readers
compare to `SliceVerdict.PROVEN.value`. No field, no new rule name, no migration: nothing in production constructs a
`MutationEvidence` yet (F9/CT-3.4: no route can declare an executable mutation), so the alphabet is free to correct
now and expensive after the first writer.

**Measured:** `tests/test_v2_verification_attempt.py` 29 passed, five new oracles (the set equality against
`KILL_CHECK_VERDICTS`; five refused spellings including the legacy uppercase ones; a truth table over *every* member
where only `proven` completes the claim; the reason/verdict agreement; the empty-reason case for a proven mutation).
Six mutants, all killed: drop the membership check, restore the `"PROVEN"` literal in `proven`, make `proven`
unconditionally true, add `"PROVEN"` to the vocabulary, restore the literal in `first_reason`, and disable
`first_reason`'s mutation branch.

**Recorded, not changed:** `kill_attribution.ATTRIBUTION_VERDICTS` is a *second*, uppercase vocabulary
(`{'PROVEN','VACUOUS','ERROR'}`) for the adjacent idea, used by CT-3.5's closure attribution. Unifying the two is a
schema decision with a blast radius across two banks and the attribution artifact, so it is filed as
**Q-V2-SLICE3-3** rather than decided here; the two sets are now visibly different instead of accidentally so.

## F1–F9 closure audit (2026-11-22) — re-verified against the code, not the plan

The F-list was written against a code base that has since changed. Each item below was re-measured by
*constructing the defect's own shape* through the real constructors (`/tmp/audit_f1_f9.py`, kept as the
reproduction recipe in this section) rather than by grepping for a rule name.

| Item | Status | Measured now | Anchor |
|---|---|---|---|
| F1 mutation dropped | **closed** | `MutationEvidence(verdict="PROVEN")` → `mutation-invalid`; only `KILL_CHECK_VERDICTS` members accepted; legacy `kill_checks` written per contract and read by the gate | `verification_attempt.py:174–184`, `:342`; `workflow_controller.py:883`, `:1081`, `:1380`; `plan_v2.py:563` |
| F2 route conflates axes | **closed on v2** | planner command on a `v2` attempt → `fence-on-v2-route`; harness-only → accepted; the artifact records `commands_authored_by` | `verification_attempt.py:225`, `:235`, `:307`; `workflow_controller.py:953`, `:1319` |
| F3 absence reads as a pass | **closed** | 1 claim of a 2-contract seal → `claims-total-mismatch`; the same attempt with `attested=("CT-1.2",)` → accepted; `contracts_total` is in the artifact | `verification_attempt.py:312–321`; `workflow_controller.py:956` |
| F4 refused vs empty | **closed as an invariant** | `legacy` with no claims and no errors → `empty-attempt-unexplained`; on `v2` the same shape is refused *earlier* (`identity-missing-on-v2`, then `claims-total-mismatch`) — the invariant holds by a stricter rule, and no new field was added | `verification_attempt.py:285`, `:303–321` |
| F5 revision asserted | **closed** | substrate naming another revision → `verifier-revision-mismatch`; substrate naming none → `verifier-revision-mismatch`; a *different but agreed* candidate is accepted, which is correct (the closure may not move, the code may) | `slice_verification.py:505`; `client.py:1587`; `acceptance_collection.py:478`; `workflow_controller.py:633` |
| F6 free text | **closed on v2**, residual on legacy | 10 000-char multi-line detail → 2 000 chars, newlines collapsed, `…[truncated]`; per-field cap at render (`300`), so one field cannot evict the rest | `verification_attempt.py:80–105`, `:200`; `workflow_controller.py:1297`, `:1338` |
| F7 naming | **closed** | `RunIdentity` no longer exists; `VerificationIdentity`, `sealed_revision_id`, `candidate_revision_id` | `verification_attempt.py:117–137` |
| F8 legacy identity | **kept exception, as stated** | `legacy` with no identity → accepted; `v2` with no identity → `identity-missing-on-v2` | `verification_attempt.py:303–306` |
| F9 verifier proves without the mutation | **closed as a refusal** | `verify_sealed_acceptance(kill_required=("CT-1.1",))` → `claim-mutation-missing` *before the cell runs*; the control (no kill target) runs | `acceptance_collection.py:423–444`; `verification_attempt.py:325` |

**Nothing in F1–F9 is open as a rule.** What the audit did find is four *route-level* gaps — the places where
the entity is correct and the pipeline cannot reach it, or reaches it with a fact missing:

**N1 — the seal is never minted on the create-new route (highest impact).** `mint_seal` is called only from
`acceptance_defect.correct` and tests, so `_stage_acceptance_bundle` refuses `acceptance-seal/missing` on every
V2 stage: the whole CT-3.6 path is unreachable in production, and every rule above is a guard nobody trips.
Two halves were missing, and the first is now landed (see the section below): `mint_seal` needs a `collected`
report, and every collector needed a minted bundle — a cycle. `collect_sealed_tree` breaks it. The remaining half
is the controller wiring plus D-V2-5's pointer/recovery rules (E1–E9). Plan-settled (CT-2.4, CT-3.2, D-V2-5) — no
question to raise.

**N2 — a declared kill target leaves no trace in a V2 attempt.** The controller passes `kill_required=()`
unconditionally, and the reason is right for *execution* (V2 `KillTarget` carries attribution only — and, corrected
2026-11-22, *no operator*, while its `target_id` has no agreed shape either: the prompt teaches `path::symbol`, the
fixtures use dotted ids — Q-V2-SLICE3-5; so nothing is runnable, F10 item 5). But the artifact then records `kill_required: []` even when the plan declares
`KILL-TARGETS  KT-1 -> CT-1.1, TEST-1.1`. A reader cannot tell "no mutation was required" from "a mutation was
declared and never ran" — F3's shape, one field over, and the exact reason F1 was called the worst defect. The
record-only fix (carry the declared attribution: target id, contract, test, and say `executed: false`) is small;
the fail-closed fix (pass the declared CTs as `kill_required`) blocks every plan that declares a target until the
runner exists. **Which one is right is a product choice the plan does not settle → Q-V2-SLICE3-4.**

**N3 — the run report carries the attested ids but not the evidence behind them.** D-V2-10's stated mitigation is
"attested ids, reason and owner written into the seal *and the run report*". The seal carries `attestations`
(contract, invariant, reason, route, artifact, owner, `reviewed_at`, scope digest); the artifact and the eval block
carry only `attested`/`pending` id lists (`grep -c attestations` in `workflow_controller.py` → 0). So on the report a
reviewer reads "CT-1.2 was attested" with no way to see who, on what, and whether the artifact named was a host
probe or a review. Plan-settled by D-V2-10 — implement, no question.

**Minor residual (recorded, not urgent):** on the frozen legacy route `_verification_evidence_lines` still renders
`slice_result.detail` and `check.detail` unbounded before the 20 000-char head cut (`workflow_controller.py:1371`,
`:1382`, `:1391`), and legacy `plan_commands` carry no authorship. Both die with the route (D-V2-1/D-V2-2); the
per-field production bound is `TAIL_LIMIT` (4 000), so one field cannot grow without limit — it can still evict a
later slice, which is F6's cosmetic half.

**Order this implies:** N1 first (otherwise nothing else is observable in production), then N2/N3 in one change set
(the artifact schema bump is shared), then the remaining S5/S6 work. F10 item 5 (`run_kill_checks`) stays unbuilt
until a grammar can express an executable mutation.

## The pre-mint collection seam, and the cycle it removes (landed 2026-11-22)

`collect_sealed_tree(acceptance_root, *, sealed_root, workspace, deadline, executor) -> SealedCollection` runs the
sealed closure's harness argv through the managed substrate **before any seal exists** and returns nodeids keyed
exactly as `mint_seal(collected=…)` expects. `sealed_test_paths`, `sealed_collection_argv`, the in-band renderer and
the nodeid re-keying were factored over an `AcceptanceClosure` (they only ever needed one), so the pre-mint path and
the post-mint path share one implementation instead of growing a second. `acceptance_bundle.require_sealed_root` is
now public for the same reason: a root the seal would refuse must not be accepted on the way in.

Measured: `tests/test_ai_native_acceptance_collection.py` 37 passed (8 new oracles, including the one that closes
the loop — collect a tree, mint from `collection.nodeids`, and prove the mint sealed the same closure digest that
was collected); affected bucket 388 passed; five mutants of the new seam each killed by a named oracle. The
long bank `tests/test_verify_gate_live.py` was **interrupted by the operator before it finished** and has not been
re-run; it is owed before N1's controller wiring lands, and nothing in this change is claimed as E2E-verified.

## N1–N3 landed, and the four defects the new bank found (2026-11-22)

**N1 — custody.** `acceptance_seal_store.SealStore` replaces the loose `SEAL_FILENAME` in the tracked tree. The
record is `.fa/seals/<seal_sha256>.json` and the authority over "which seal is in force" is a single pointer,
`.fa/seal-current.json`, replaced by `os.replace` after an fsync (never a partial file). `.fa/` is the one location
both canonical walks already exclude (`workspace.py:_PROTECTED_COMPONENTS`) and no file tool may address
(`view_io.py:_BLOCKED_COMPONENTS`), so "the project at revision R" and "the bytes on disk" cannot stop meaning the
same thing at the artifact that is supposed to prove custody. `store` is idempotent (a restart mints the same bytes
from the same inputs), a second different seal must declare `supersedes_sha256`, and the pointer never swings
without that declaration — a second mint on the create route is `seal-conflict`, not a supersede (D-V2-9 allows one
revision). Absence and corruption are different answers: a missing pointer is `seal-pointer-missing` ("nothing
sealed yet", which the stage reports in its existing `acceptance-seal/missing` vocabulary), a pointer naming a
record that is not on disk is `seal-record-missing`, and a torn record is `seal-record-mismatch` — never a re-mint,
because re-minting over corruption launders it into evidence.

**N1 — mint and wiring.** `_seal_published_project` runs on the create route *after* every admission refusal has
returned and *before* any coder is dispatched (D-V2-5 §3): `collect_sealed_tree` → `mint_seal` → `SealStore.store`.
`candidate_revision_id = managed.current_revision_id` (C2: the pin is consulted once, at admission; custody is
content-based afterwards). The stage reads the seal back through `SealStore.current()`. The refusal is one rule,
`bootstrap-acceptance-unsealed`, whose `detail` is the closed rule of whichever producer refused (bundle rules, and
plan rules such as `selector-uncollected` — `mint_seal` resolves selectors against the collection, so a selector
nothing collects is the parser's own rule, not the bundle's). It maps to `bootstrap_content_invalid` and is
non-retryable; repairability is split by half: an acceptance tree that does not collect is content the planner can
fix inside `acceptance/`, while the consistency half (`_UNREPAIRABLE_SEAL_RULES`: admission accepted a graph the
seal refused) is this build's defect and must not spend the repair budget. The scaffold now writes
`acceptance/pytest.ini` with the project, because a closure without a runner config is not a closure and the
planner has no instruction to author one — harness shape, like the front matter.

**N2 (Q-V2-SLICE3-4 = option A, implemented on the recorded recommendation, operator sign-off still open).**
`PlanGraph.kill_targets()` exposes the grammar's `KILL-TARGETS` rows in document order; `VerificationAttempt` gains
`kill_declared`, and the artifact records `{target_id, ct_id, test_id, executed: false}` with the eval line saying
"declared, not executed on this route". `kill_required` stays empty — nothing on this grammar is executable, which
is a fact about the plan, not about the attempt. Rules: `kill-target-invalid`, `kill-target-unknown` (must name a
covered contract), `kill-target-conflict` (declared and required are mutually exclusive), `kill-target-duplicate`.
Revert surface if the operator chooses B: `kill_declared` and its three rules; B would instead pass the declared CTs
as `kill_required` and block every plan that declares a target until `run_kill_checks` exists.

**N3 (plan-settled by D-V2-10).** The seal's `Attestation` records travel through `sealed_attempt(attestations=…)`
into the artifact (contract, invariant, reason, route, artifact, owner, `reviewed_at`, scope digest) and into the eval
block (`owner`/`artifact` cut at `EVAL_CLAIM_DETAIL_MAX_CHARS` and labelled untrusted). Rules: `attestation-invalid`,
`attestation-unowned` (the report may not carry a grant the seal does not list), `attestation-duplicate`. Both new
rule families are checked for every route, not just `v2` — the record's coherence is a fact about the record, and a
route that starts declaring targets inherits the same rules instead of a second copy.

**Four defects the bank found — each caught by a test, none by inspection.** (1) `SealStore.store` wrote the record
*before* validating the pointer move, so a refused supersede left an orphan seal nobody's pointer named; validation
now precedes `_write_once`. (2) `_admit_published_project` returned the *bound* context on a seal refusal, so the
caller still held an admission for a project with no oracle; it now returns the input `ctx`. (3) `mint_seal`'s
`PlanV2Error` escaped uncaught — catching only `AcceptanceBundleError` turned a content refusal into a crash; the
rule now travels as `detail`. (4) `bootstrap-acceptance-unsealed` had no mapping in `_V2_CREATE_FAILURES` and would
have surfaced as an unclassified failure; it maps to `bootstrap_content_invalid`, non-retryable.

**Fixture contract for route tests (all three discovered the hard way).** The shared V2 fixture front matter
(`Increment-ID: I01`, no slug/active-increment/status/created) cannot pass `check_project_metadata`, so a route test
builds its documents from `scaffold_files(slug, created=…)` and appends the authored body after the `Plan-Format`
line; a seeded acceptance test must be created the way the tool creates it; and the verify substrate must be patched
at the admission site (`workflow_controller._pinned_verify_substrate`), not at `verify_sealed_acceptance`.

**Verification.** `tests/test_v2_seal_store_and_mint.py` — new bank, **19 passed** (custody, round-trip, idempotent
re-store, supersede chain, pointer-missing vs record-missing, torn record, pointer not closed, route mint + next
stage reads it, uncollectable tree, repairability split, no pinned cell, stage-level `kill_declared`, attestations in
payload and render, plus three refusals). Affected bucket **675 passed**; the narrower re-run after the lint repairs
**260 passed**. The owed long bank `tests/test_verify_gate_live.py` **581 passed in 183 s** (it had been interrupted,
then its three `SealStore` sites were unverified). Full suite **8411 passed, 1 failed** — the pre-existing pyrefly
topology red, unchanged. Gate recording `notes/gates/2026-11-22-head-n1n3` compared to `head-2f9924b`:
**NEW TOTAL 0** (mypy 62 = base count, ruff 0, ruff-format 7 with one gone, authoring-check 0); the pytest finding
list is also 0 new against the `base-1acb56b` recording. The three mypy findings this change initially added (an
unbound lambda in a test, two imports from the wrong module) were fixed rather than recorded, because `no new red`
counts findings, not their severity. Mutation testing: **14 of 14 mutants killed**, including pointer-before-record, missing-record-read-
as-absence, record-write-into-the-tree, admission-skipping-the-mint, unsealed-context-returned, seal-family-always-
repairable, declared-targets-dropped-at-the-stage, attestations-dropped-by-`sealed_attempt`, and each of the three
new refusal rules. `ruff check`/`format --check` clean; `fa authoring-check` diagnostics 0.

**Still open.** `Q-V2-SLICE3-4` needs the operator's confirmation of option A (the implementation follows the
recorded recommendation). `Q-V2-SLICE3-3` (the duplicated uppercase verdict vocabulary in `kill_attribution`) stays
open and untouched.

## Q-V2-SLICE3-3 resolved = A: two spellings of one axis became one (2026-11-22)

`kill_attribution.py` no longer keeps a second, uppercase verdict vocabulary. `NodeOutcome` (an `enum.StrEnum`:
`PASSED/FAILED/SKIPPED/MISSING/ERROR`) types a *run*, `NODE_OUTCOMES` is derived from it, and
`ATTRIBUTION_VERDICTS` is derived from `SliceVerdict` (`{PROVEN, VACUOUS, ERROR}`) instead of a literal set. The
record validates what it names — `KillAttribution.verdict` must be a `SliceVerdict` inside that set
(`kill-attribution-invalid`) and every non-`PROVEN` verdict must carry a detail — and `NodeRun` refuses an outcome
outside the five (`kill-run-invalid`). Before this, `ATTRIBUTION_VERDICTS` was exported and read by nothing: the
constant was a promise with no reader, which is F1's shape one entity over.

The two axes stay separate on purpose: a run can be `MISSING` (no verdict counterpart) and a verdict can be `VACUOUS`
(no single-run counterpart). What was removed is two spellings of the *same* axis — `"PROVEN"` beside
`SliceVerdict.PROVEN` — which is what made a correct proof read as `mutation-invalid` (or, worse, compare `False`)
the day CT-3.4/3.5 wires attribution into the attempt.

**Measured:** bank 35 passed (was 32); nine mutants killed (constant back to uppercase literals, membership rule
removed, unexplained-non-`PROVEN` rule removed, `NodeRun` accepting any outcome, a failed mutation reading as
`VACUOUS`, a failed report row reading as `SKIPPED`, `attribute` accepting a non-run, outcome values lowercased,
baseline-pass precondition removed). The bind that keeps a third spelling from appearing is a test:
`{verdict.value for verdict in ATTRIBUTION_VERDICTS} <= MUTATION_VERDICTS`.

**Environment caveat:** the sandbox lost its python 3.13 virtualenv, so this bank was executed on CPython 3.11 with a
`typing.override` stand-in installed outside the repository. The committed code is what ran; the interpreter is not
the project's. The full suite and the gate recordings are owed (ledger E625).
