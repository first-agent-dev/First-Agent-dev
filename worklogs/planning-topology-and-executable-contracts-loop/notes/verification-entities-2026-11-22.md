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

**Correction:** `claims[]` covers the seal's total; `outcome` includes `attested` and `pending` from the seal's own
vocabulary; write-time rule `claims-total-mismatch` when `len(claims) != contracts_total`.

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
                        outcome: passed|failed|skipped|error|attested|pending,
                        mutation: MutationEvidence | None,            # None only when no KILL-TARGET (F1)
                        detail: bounded 2000 chars, single line (F6)

MutationEvidence     := operator, path_or_symbol, verdict (closed KILL_CHECK_VERDICTS), detail (bounded)
CommandRun           := command, authored_by: planner|harness, outcome, exit_code, tails, duration
```

Write-time refusals: `claims-total-mismatch`, `claim-mutation-missing`, `fence-on-v2-route`,
`empty-attempt-unexplained`, `verifier-revision-mismatch`, `identity-missing-on-v2`.
