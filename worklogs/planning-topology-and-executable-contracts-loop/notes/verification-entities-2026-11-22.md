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
