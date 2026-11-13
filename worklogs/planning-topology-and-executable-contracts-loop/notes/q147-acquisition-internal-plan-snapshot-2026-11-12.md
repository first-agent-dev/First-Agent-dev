# Q147 — how does a validated `PlanSnapshot` reach admission without a host plan path?

**Status: OPEN — blocked S5P1 STEP2; raised 2026-11-12.**

## Context

S5P1 STEP2 is "complete the real managed acquisition caller". Its own text is
prescriptive about the seam and explicit about the constraint that makes it hard:

> Inside existing `run_workflow`, validate a private child/owner/view-bound
> `ManagedAdmissionEntry` ... and dispatch the configured planner exactly once. Its
> registry is read/search/final-choice only; negotiate Q108 and use LIST plus reads
> through the same immutable `READ/PROJECT` pin.

and

> **Admission invariant:** current `workflow_controller.py:2731–2736` requires
> `plan_path` and reads from the host workspace. Defer that entry check only for the
> private read-only acquisition prelude, then **supply the validated `PlanSnapshot`
> internally** to the existing admission/repair machine ... Do not fabricate a host
> `Path`, accept model-supplied paths, or weaken plan-before-coder.

Blocks 1–4 of S5P1 are done: the stage kind exists (`62e49be`), the wire can name
projects (`d268d29`), the two refusals are split (`060cfaa`), and the port can carry
names to acquisition (`40c1cb1`, `34460b2`). What remains is the caller that would
use them.

## What I measured in the code

1. **`run_workflow` has no plan input other than a host `Path`.** Signature takes
   `plan_path: Path | None`; admission needs `snapshot` (`workflow_controller.py:2988`)
   and gets it only from `read_plan_snapshot(workspace, plan_path)` (`:2924–2930`).
   There is no parameter for an already-validated snapshot.

2. **Admission re-reads the host, twice.** `_check_admission_source` (`:2578–2584`)
   does `read_plan_snapshot(ctx.workspace, Path(source.ref.workspace_relative_path))`
   and compares `sha256`; it is called from both the coder gate (`:1255`) and the
   stage-integrity path (`:1188`). In a managed run, the revision the coder will edit
   lives in the authority's view, not in `ctx.workspace`, so this read is not evidence
   about the tree under admission. This is the same class of defect R24 removed for the
   verify gate: judging one tree by reading another.

3. **The controller has a pin-based port, but not where admission needs it.** A
   `ClientWorkspacePort` over a pinned `READ/PROJECT` view is constructed for the
   verify substrate (`:462–470`) and torn down after. It is not available to
   `run_workflow`'s admission, and none of `_check_admission_source`'s call sites
   has one.

4. **The pieces for the alternative exist.** `inventory_project_artifacts(port, slug)`
   and `resolve_existing_choice(...)` already produce a `PlanSnapshot` from bytes read
   through a port (`managed_inventory.py`, `managed_acquisition.py`), and the port can
   now name the candidates it should be asked about (`list_project_names`). So the
   bytes for a validated snapshot are obtainable through the pin today. What does not
   exist is a way for that snapshot to *reach admission* and for admission to *re-check
   it against the pin* instead of against `ctx.workspace`.

## The question

How should the validated `PlanSnapshot` reach the existing admission machine, and
against what should admission re-verify its content?

The plan says "supply the validated `PlanSnapshot` internally" but does not say by
which mechanism, and the re-check half is not addressed at all — yet `_check_admission_source`
is the thing that decides `source-changed`, so leaving it on the host read would let
admission accept a snapshot it can no longer substantiate, or refuse a correct one
because the host copy is stale or absent.

**This is a contract choice, not an implementation detail:** option A adds a new
public `run_workflow` parameter, which is a public API change to a function the CLI,
the tool layer, and integration tests all call.

## Options

- **A — add a keyword-only internal parameter, e.g. `admission_snapshot: PlanSnapshot | None`
  (default `None`, so every existing call site is byte-identical), and make
  `_check_admission_source` prefer a snapshot-backed substantive check over the host
  read when it is present.** Simplest mechanism that satisfies the target behavior;
  keeps one admission machine; no host `Path` is fabricated. Cost: a new public
  parameter on `run_workflow` (the SPEC says "no public ... context field" for STEP2 —
  whether a keyword-only parameter with `None` default counts is exactly what needs
  deciding), plus a second verification route inside `_check_admission_source`.
- **B — keep `run_workflow`'s signature and carry the snapshot on `WorkflowContext`**,
  built by the caller before the call. Avoids the signature change but moves the fact
  out of the function's contract, and the SPEC's phrase "no public ... context field"
  reads as excluding this.
- **C — write the validated snapshot into the host workspace first and pass a real
  `plan_path`.** Rejected on sight: it fabricates the host path the SPEC forbids and
  reintroduces exactly the stale-host-copy defect R24/S5P1 exist to remove.
- **D — stop before the caller and re-scope S5P1 STEP2 into a design round.** Honest
  but leaves four finished blocks with no consumer; the naming seam stays advisory.

## Engineering recommendation

**A**, with the re-check preference made explicit and narrow:

1. `admission_snapshot` is keyword-only and defaults to `None`; when it is `None`,
   every code path is exactly today's, so legacy `fa workflow` and integration callers
   are unaffected and the existing 44 schema tests keep their meaning.
2. When it is present, `_check_admission_source` verifies the *snapshot's own* digest
   and provenance (the bytes it was built from, `source_kind`, and the pin it came
   from) instead of re-reading `ctx.workspace`; a snapshot whose digest does not match
   its recorded bytes stays `source-changed`, refused, before any coder stage.
3. `plan_path` remains required for the public path. The prelude is deferred only for
   the internal caller, and the snapshot must be present before `T0`/coder — plan-before-coder
   is not weakened, it changes *where the authoritative copy comes from*.

This is the smallest change that makes the managed caller possible without inventing a
second admission machine, and it keeps the failure closed: a missing or mismatched
snapshot refuses, it never falls back to the host tree.

I did not implement any of it. Choosing between A and B is a decision about a public
interface, and C is a contract violation — the plan left the mechanism unstated, so this
is the stop-and-ask point rather than a place to pick the convenient option.

## Impact if deferred

S5P1's last four blocks (caller, `render_bundle` authority-side, zero-coder-on-denial
E2E, spec §7 fixtures/v1 compatibility) cannot start. `list_project_names` remains a
seam with a proven owner but no production caller, and Q141's gate cannot be revisited,
because the gate's removal depends on a coder acquisition path existing.
