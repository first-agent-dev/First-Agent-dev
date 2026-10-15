---
Increment-ID: RM-planning-topology-I03
Roadmap-ID: RM-planning-topology
status: OUTLINED
slices: 0
shipped: —
---

# INCREMENT I03 outline: Execution/workspace foundation and integrated acceptance

**Not an executable increment yet.** This rolling-wave outline receives transferred obligations;
zero declared slices means there is no authorisation to dispatch it as an admitted plan. Write
concrete briefs/CTs/tests/producers/kill directives before implementation. OUTLINED is not READY,
IN PROGRESS, IMPLEMENTED or VERIFIED. No scope transfer is delivery.

**Depends on:** actual retained I02 local DoD, not its former host E2E prerequisite.
**Target delivery:** safe actual explicit and outer-chat→invoke_workflow paths using one trusted
host execution authority, private workspace views and sealed/fenced publication, followed by
reviewed deployed I02+I03 acceptance. Keep PTY and Linux/Docker only; unavailable backend fails closed.

## Context and transferred ownership

- [I02 migration bank](../notes/i02-to-i03-scope-migration-2026-10-15.md) is the clause/STEP/GAP/case map
  and preserves old SLICE7/DoD. CT96/CT97 and CT88/CT89 remain original obligation identities.
- [Execution decision note](../notes/execution-workspace-and-i02-i03-scope-decisions-2026-10-15.md)
  specifies selected guarantees/TCB/irreversible points and open dispositions.
- [Scope-reduction audit](../notes/execution-foundation-scope-reduction-and-reuse-audit-2026-10-15.md)
  grounds existing-code reuse and compact grouping. Six groups are a drafting candidate, not a
  reason to hide giant briefs; split increment if concrete size exceeds the seven-slice ceiling.
- No new public context field. Preserve ordinary logs/redaction, initial-only bounded parent input
  through per_role_task; distilled retry/replan packets, not repeated full parent transcripts.

## Candidate delivery groups and mandatory oracles

| Group | Work / migrated obligations | Observable negative proof |
| --- | --- | --- |
| A | Immutable controller imports/launches; private UDS host supervisor/approved profiles; existing BashExecutor/PTY/noninteractive adapters; CT97 execution seam | Wrapper/entrypoint imports image-owned runtime; cells have no daemon socket/controller secrets; backend unavailable executes zero project commands; uncertain PTY result never replays |
| B | One local workspace identity/ownership authority; protected process-shared lease; materialized immutable published revisions, private candidates and pinned readers; CT97 file/shell views | Same workspace cannot have two writers even with different run/session labels; dirty tracked/untracked inputs visible; file tools/PTY see same private edits; other actors cannot mutate canonical tree |
| C | Process-tree terminal barrier, sealing/export, fenced durable publication/intent/recovery, parent refresh; Q58 integration and distinct bootstrap irreversible points | Descendant writer prevents seal; stale generation/base rejected; crash recovery exposes no partial current manifest; no-clobber install preserves collisions; canonical post-commit bytes never auto-rolled back |
| D | Actual nested selection/admission/bootstrap/clarification; CT96 + managed clauses CT90/CT92–CT95; Q66 initial task composition | Real outer-chat→invoke→run_workflow→_cmd_run→drive_session with only provider mocked; no guessed PlanRef; existing selection/new project work; collisions/malformed requests stop before coder; context appears only in initial planner input |
| E | Whole project execution integration incl early readiness/imports/dependency hooks/verifier; PlanRef/evidence operation+revision binding; CT97 integration | Complete execution call inventory inside boundary before first project command; stale/zero/skip/error evidence never PROVEN; Q55/Q56/T0 preserved; no host subprocess fallback or controller-package import pollution |
| F | Entire former I02 SLICE7 CT88/CT89 + STEPs1–10, unique gate/admission/runtime cases, handoffs/run sheets/fixtures/skills/manual checklist + actual deployed acceptance | All unique I02+I03 producer cases mapped and reviewed on deployed main with code/image/config/run/oracle/artifact evidence; local green, NOT_RUN/skip/BLOCKED never PASS; safe update stop/observe→review→enforce ordering |

Group F is last for the actually delivered foundation. A backend-only proof is not whole-product
isolation; A/E coverage cannot leave unguarded readiness, project imports or tool fallback routes.
Supervision and publisher authority share one coherent ownership domain; no independent lease,
fencing or journal services, distributed scheduler, raw Docker API surface or second sessions DB.
Cells never write canonical state. Bootstrap no-replace, Q58 replacement and multifile publication
may reuse safe IO but keep different commit/recovery semantics.

## PTY/FastAPI disposition

Existing `src/fa/runtime/server.py` is an incomplete optional PTY HTTP transport, not a ready
host supervisor. Reuse `BashExecutor`, PtyResult, PTY machinery and result framing; choose an
optional cell-internal server only if it reduces dependencies/implementation. Standalone server
completion/deployment is **not** an I02 task and not an independent I03 shipping criterion.
Required capability is enforced lifecycle integration: launch/profile ownership, inspect/cancel,
all-descendant terminal barrier, view identity/fencing and seal. No second management authority.

## Required dispositions before concrete briefs

- Preserve Q59/Q60/Q62/Q63 exact pending choices; broad design approval does not close them.
  CT96 legacy schema recommendations must be reconciled with current stable-ID selection design.
- Preserve supported lifecycle versus target: current SessionManager rejects a second session
  using another session's owned workspace. Explicitly plan approved new-session/old-workspace reuse;
  do not silently remove guard or add a session-transfer platform.
- Define copy/input policy, protected path traversal, revision pin/retention and recovery authority
  with concrete negative tests. Materialized copies suffice; CAS/overlay/reflink/GC platform deferred.
- Plan actual single-host Linux/Docker profile/UID/UDS/cgroup deployment proof; tests over fake
  executor responses do not certify that deployment. Host/kernel/daemon/admin are explicit TCB.
- CT97 old fallback suggestion to delete arbitrary shell is superseded: PTY stays. All project-code
  execution uses the mandatory boundary independent of role permission or observe/enforce.
- Preserve Q53(c) slice attribution; detailed parser reuse, not contract→nodeid mapping or automatically
  adopted extra clean-control baseline. Local classification fix is retained I02, supervised binding I03.

## Acceptance ownership (incomplete)

Local composition/security/recovery tests and every unique migrated producer kill are required.
Final deployed-main package retains original update/health/rc stop conditions, no secrets/raw host
logs in Git, append-only attempts and operator/reviewer-owned verdicts. If update returns nonzero,
inspect printed deployed SHA/health/test rc: deployment may already have happened; no blind retry.
Exact live-result schema/checklist finalization follows Q63 disposition before fixture implementation.
I02 can be SHIPPED on its retained local DoD; that does not satisfy any I03 acceptance row.

## Explicitly not this increment

Old I03 per-slice scheduler/tracker/three-level L2 eval and related coder prompt/read-API consumers
are the named deferred **slice-loop/tracker/L2-eval successor** on the roadmap. Foundation I03
shipping does not expire operator ticking or deliver L2 VERIFIED. Do not renumber I04–I06/Q64→I06.
Parallel workflow/subagent orchestration, CAS/overlay/backend matrix, advanced privacy/logging/GC,
package/proxy framework and calibration/≥95% remain outside this foundation.
