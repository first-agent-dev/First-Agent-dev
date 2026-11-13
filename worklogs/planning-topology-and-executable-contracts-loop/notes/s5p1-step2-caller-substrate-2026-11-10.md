# S5P1 STEP2 — the production acquisition caller: what the substrate already fixes

Written 2026-11-10, Arena-local, before writing the caller. Everything below was
measured in the tree at `d8e4ba5`; nothing here is a proposal that contradicts an
existing mechanism.

## The three pieces that are already landed

| piece | where | what it proves |
| --- | --- | --- |
| acquisition registry | `profiles.build_acquisition_registry` | 5 read/search tools in a positive list; no mutator; identical host/managed |
| snapshot admission | `workflow_controller.run_workflow(admission_snapshot=…)` | a plan can be admitted from bytes the caller already validated, with `conflict` / `admission-without-coder` / `unreadable` closed |
| choice → outcome | `managed_acquisition.resolve_acquisition_choice` | `SELECT_EXISTING` → snapshot, `NEEDS_CLARIFICATION` → pass-through, `BOOTSTRAP` → needs installation, never a fabricated snapshot |

## What the spec already decided, and therefore must not be re-decided

**One `run_workflow`, not two phases.** `i03-execution-workspace-spec:1356`:
*"Private ManagedAdmissionEntry permits initial no-PlanRef planner only after
actual child/owner grant validation. Do not run an extra pre-workflow planner then
replay planner in run_workflow."* A design that runs `roles=["planner"]`, reads the
choice, then re-enters with `roles=["coder"]` is exactly the forbidden shape. The
admission must be bound **inside** the run that dispatched the planner.

**The dispatch kind already exists.** `PlannerDispatchKind.ACQUISITION`
(`planner_dispatch.py:24`) is present with its invariants: it owns no candidate
buffer (`owns_candidate` excludes it) and may not name an `active_plan`, because
acquisition runs before anyone selected a target.

**The plan-read substrate exists twice over.** `snapshot_from_bytes` builds a full
`PlanSnapshot` with no filesystem, and `_read_repair_candidate` is the same seam
already in production.

## The two facts that shape the caller

### 1. A READ/PROJECT view with no plan is legal — and `pin_reader` already says so

`AuthorityWorkspacePort.list_project_names` requires `Access.READ` +
`ViewPurpose.PROJECT`, which the CANDIDATE view a coder holds is not. The question
is what the *acquisition* stage reads through.

`workspace.pin_reader(..., plan_ref=None, formal_evidence=False)` is the answer, and
it is the existing production path — not a new purpose row in `_PURPOSE_MATRIX`
(which offers `PROJECT → (WRITE, with-plan)` and read-only pins as `VERIFICATION`,
empty scope). `ProtectedPlanContext.recheck` returns immediately on a null
`plan_ref` ("Ordinary no-active-plan context, not formal evidence"), so
`pin_reader(None)` is *designed* for a run that has no plan yet, which is precisely
an acquisition stage.

`_pinned_verify_substrate` (`workflow_controller.py:393`) is the working template:
pin → validate the grant is `PIN_READER`/`READ`/`PROJECT`/owned → build
`ClientWorkspacePort` → stop the view in `finally` even when the stage raised.

### 2. The planner's choice is readable in production, through the seam eval uses

`_run_stage` builds a local `sink: list[SessionOutcome]` and passes it as
`outcome_sink` for **every** role (`workflow_controller.py:1425`); `_cmd_run` appends
the terminal `SessionOutcome` (`cli.py:3070`), and `final_text` is set when the LLM
stopped on its own (`coder_loop.py:548`). Eval is read at `:1544`. An acquisition
stage reads its choice the same way — same channel, one line of guard.

## What is left, and its exact shape

`run_workflow` currently refuses a coder-bearing run with no plan **before any
stage** (`_require_plan_for_coder`). For an acquisition run the plan cannot exist
until the planner has spoken, so that entry check must admit one shape:

* first configured role is `planner`, and
* an acquisition substrate was supplied.

Then, after the planner stage returns and its choice resolves to a snapshot, the
controller binds `_WorkflowAdmission` for the following coder stage from that
snapshot. Everything downstream is unchanged: `_validate_plan_admission`, the
verify gate, promotion.

Refusals the caller owes the operator, each distinct: no managed execution; no
pinned view available; planner produced no parseable choice; choice is
clarification; choice is bootstrap (needs the authority-side install first); the
selected project is not in the pinned revision.

**Deliberately not done in the same slice.** Bootstrap installation through
`prepare_bundle` → `install_project` (both authority-gated and already served by the
supervisor dispatcher) has no inner-loop caller; it stays open and must not be
described as working because `render_bundle` exists.
