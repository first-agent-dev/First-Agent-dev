# Q147 — retracted: the mechanism was already specified and already implemented

**Status: RETRACTED (2026-11-12). Operator was right; the escalation was wrong.**

I raised Q147 claiming that "how a validated `PlanSnapshot` reaches the admission
machine" was an unstated contract choice requiring a public-interface decision. It is
not. Both halves already exist in I01/I02, and one of them is the *existing* mechanism
in `workflow_controller.py` today, not something to be added.

## What I missed

**1. The snapshot is already self-contained; a path is not its identity.**

`PlanSnapshot(ref, utf8_bytes, text, ids)` carries the plan's own bytes. `PlanRef` is
`(workspace_relative_path, source_kind, sha256)` — a *label plus digest*, not a location
that must be readable later. `snapshot_from_bytes(relative_path, raw, *, source_kind)`
(`plan_admission.py:160`) constructs a complete snapshot from bytes with no filesystem
access at all. `read_plan_snapshot(workspace, plan_path)` is a thin wrapper that reads
bytes and then calls exactly that function (`:133–145`).

So "supply the validated `PlanSnapshot` internally" needs no new mechanism: the bytes
come from the pin (which `inventory_project_artifacts` + `resolve_existing_choice`
already produce, with `source_kind="EXISTING_SELECTION"` at `managed_acquisition.py:482`),
and `snapshot_from_bytes` turns them into the snapshot. The spec said "internally"; I
read that as "via a new parameter" when it means "from bytes the controller already has".

**2. The controller already builds admission snapshots from bytes rather than from paths.**

`_read_repair_candidate` (`workflow_controller.py:2658–2681`) is this exact pattern,
already shipped for managed repair: it takes bytes from the authority's staged buffer
through `ctx.managed_candidate_reader`, calls `snapshot_from_bytes(label, content)`, and
compares the resulting digest against the digest the authority reported. When no buffer
is bound it falls back to `read_plan_snapshot` — and the docstring states why the managed
run must not use the host path. That is the precedent, and S5P1's acquisition prelude is
the same shape with a different source.

**3. `_check_admission_source` is not a blocker, because admission is constructed *from*
the snapshot.**

My fear was that the host re-read (`:2578–2584`) would judge one tree by reading another.
But `_check_admission_source` returns early when `ctx.admission is None` (both call sites:
`_plan_integrity_errors`, `:1185`; the coder gate, `:2728`). Admission is only ever built
as `_WorkflowAdmission(snapshot, ...)` (`:2988–2990`, field declared at `:180`), and in a
managed run that snapshot comes from the bound reader. The host re-read is the *host-mode*
branch of an already-branched mechanism — the same shape as `_read_repair_candidate`'s
`captured is None` fallback. It is not a second source of truth needing a new public knob;
it is the existing split, and the acquisition path joins the managed side of it.

**4. The spec sequence already gates this correctly.**

`i02-explicit-admission-spec-2026-10-15.md:88–92` fixes the order: "pure request check →
explicit snapshot read → create durable ACQUIRING admission … → optional configured
ordinary planner → recheck source hash → shared pre-coder validation/repair → durable
ADMITTED attempt → T0 → coder." For acquisition the "explicit snapshot read" step is the
pin-backed read instead of a host read; every later step is unchanged, including
"recheck source hash". Nothing in that sequence requires a new parameter, and the spec
already anticipated the snapshot being the authority.

**5. The reserved vocabulary confirms it was designed.**

`admission_schema.py:143` admits `source_kind ∈ {EXPLICIT, EXISTING_SELECTION, BOOTSTRAP}`.
`EXISTING_SELECTION` and `BOOTSTRAP` are not reachable by the CLI path: they exist for
exactly the internal acquisition producer. The "internal" channel was designed into the
schema, and I proposed a parameter to carry what the schema already names.

## Why the escalation was wrong, not just inconvenient

I had the evidence and read past it: I saw `_read_repair_candidate` construct a snapshot
from bytes, and I saw `_WorkflowAdmission.snapshot: PlanSnapshot` — a field typed to the
snapshot, not to a path. I then reasoned from `run_workflow`'s signature alone ("only
`plan_path: Path | None`") to a conclusion about the *whole* mechanism. The signature is
the public caller's input; the controller's internal builder is a different surface, and I
checked one and inferred about the other.

## Consequence for S5P1 STEP2

No Q147 decision is needed and no public signature change is proposed. The caller is
implementable on existing seams:

- the prelude reads candidates through the pinned `READ/PROJECT` port
  (`list_project_names` + `inventory_project_artifacts`, blocks 2–4 of S5P1);
- `resolve_existing_choice` / bootstrap produce the `PlanSnapshot` with its
  `source_kind`, exactly as `managed_acquisition.py` already does;
- admission is built from that snapshot the way `_read_repair_candidate` and
  `_WorkflowAdmission` already do, and the existing `_check_admission_source` split keeps
  the host re-read on the host branch only.

The remaining work is wiring, not a new contract. If a genuine gap appears while wiring
it — for instance if the bootstrap receipt must be read back through the pin before
admission rather than after — that is a narrower question and can be raised on its own
evidence rather than on my misreading.
