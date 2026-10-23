# I03 implementation handoffs

**Status: local coder observations only.** This file is not an acceptance oracle, a host run sheet,
or evidence of deployed behavior. The planner-owned case and live oracle remain in
[`live-verification.md`](live-verification.md) and the source register. No fixtures or live commands
are authored here; candidate exercise details are proposals for planner/reviewer disposition.

## I03-LIVE-23 — Q58 / CT107a / E273 canonical plan replacement

- **Contracts / producers:** Q58; CT107a; `I03-LIVE-23`; `publication.publish_plan` and
  `WorkspaceAuthority.publish_plan`. The case's expected live observation and ownership are unchanged.
- **Verified source references:** `src/fa/execution/publication.py::publish_plan`;
  `src/fa/execution/workspace.py::WorkspaceAuthority.publish_plan`, `_plan_prepare`,
  `_plan_source_identity`, `_plan_finish`, and `_recover_intent`;
  `tests/test_workspace_publication.py`.
- **Production path:** The publication facade delegates to the workspace authority; it is not a
  second writer. The authority validates the plan buffer and its source `PlanRef`, limits the target
  to `worklogs/<slug>/increments/<name>.md`, and proves owner authority and workspace state. It stages
  bytes, rechecks source identity immediately before the same-path `os.replace`, and writes the durable
  `PLAN` intent before that irreversible replacement. After replacement, revision/pointer/projection
  work completes forward; prior bytes are never restored.
- **Observable effect / artifact:** Local tests verify the new bytes at the same canonical path,
  preserved mode, derived revision and pointer, updated digest/size, retained old pinned revision,
  and cleared intent after success. Pre-replacement refusals leave the source and pointer unchanged.
  A post-replacement failure retains the new bytes and `PREPARED` intent and refuses further work.
  These are local component observations; the host-side acceptance oracle remains the planner's
  I03-LIVE-23 row.
- **Host prerequisites:** The planner oracle requires the approved filesystem, installed service and
  real owner grant. Host execution additionally needs the actual deployed SHA, image digest, profile,
  config and approved command; this handoff supplies none of those values.
- **Candidate fixture / command: [PROPOSAL]** After STEP7 review and STEP5 planner/operator
  disposition, exercise Q58 through the installed dispatcher/authority on an approved disposable
  workspace. Cover successful same-path replacement and pinned-reader preservation; stale hash,
  invalid/noncanonical plan, wrong grant, unsettled view, source/link race; and kill/restart around
  the replace and revision/pointer boundaries. Assert only the existing register oracle. No fixture
  or copy/paste host command is created by this proposal.
- **Local proof:** `tests/test_workspace_publication.py` exercises the real authority and filesystem.
  Relevant cases include `test_publish_plan_replaces_the_canonical_file_and_commits_a_revision`,
  stale-source/path/buffer/grant/view refusals, link and concurrent-write races, mode verification,
  and `test_a_failure_after_the_plan_replace_keeps_the_new_bytes_and_the_intent`. These prove local
  component behavior, not an installed-service restart or host crash matrix.
- **Host-only assumptions / limitations:** The local test bank does not establish installed routing,
  actual host filesystem behavior, process-kill/restart recovery, or power-loss durability. The
  dispatcher/controller cutover is separately unfinished in the plan; the authority primitive is
  not evidence that the candidate workflow reaches it. `I03-LIVE-23` remains `PLANNED / UNEXECUTED`.
- **Evidence references:** `worklogs/planning-topology-and-executable-contracts-loop/notes/e2e-live-verification-register.md`
  (Q58 / `I03-LIVE-23`); `worklogs/planning-topology-and-executable-contracts-loop/increments/increment-03-execution-workspace-foundation.md`
  (CT107a and E273); `tests/test_workspace_publication.py`.
- **Planner disposition:** pending. This coder handoff does not amend the oracle, case ownership,
  fixture authorization, or live result.

## I03-LIVE-24 — CT99 / E274 pre-reservation authority check

- **Contracts / producers:** CT99; `I03-LIVE-24`; `WorkspaceAuthority.authorize` and its
  `_authorize_operation` dispatch. The case's expected live observation and ownership are unchanged.
- **Verified source references:** `src/fa/execution/supervisor.py::SupervisorDispatcher._authorize_request`;
  `src/fa/execution/workspace.py::WorkspaceAuthority.authorize`, `_authorize_operation`,
  `_owner_only`, `_proof_only`, and `_pinned_plan_context`;
  `tests/test_workspace_authorize.py`.
- **Production path:** The dispatcher checks the peer UID and EXEC profile/budget constraints, calls
  its configured authority callback, and requires/rechecks a `ProtectedPlanContext` for
  `pin_reader`, `create_view`, and `exec`. `WorkspaceAuthority.authorize` round-trips the request
  through the closed decoder, enters its authority transaction, then delegates proof to
  `_authorize_operation`. That method proves the owner grant for applicable view-less operations or
  the exact peer/namespace/view/capability binding for view-scoped operations. EXEC uses the stored
  view context; `pin_reader` and `create_view` return a context rooted in the named pinned revision.
- **Observable effect / artifact:** This is a pre-reservation proof, not work admission or execution.
  The local tests observe returned plan context for authorized plan-bound requests and closed errors
  for denied requests. The planner's live oracle remains the source for host-side effects: denied
  requests must not create a reservation or alter `operations/`, Docker state, canonical bytes, or
  grants; a damaged pinned plan must be rejected with `INPUT_POLICY` for the protected operations.
- **Host prerequisites:** The existing planner oracle requires the approved filesystem, installed
  service, controller UID and real peer credentials. The deployed SHA, image digest, profile,
  configuration, and safe operator command must come from the actual approved deployment; none is
  supplied or inferred by this handoff.
- **Candidate fixture / command: [PROPOSAL]** After STEP7 review and STEP5 planner/operator
  disposition, exercise the existing closed request shapes through the deployed dispatcher and real
  authority on an approved disposable workspace. Include owner/view grant negatives, foreign
  namespace and swapped-view negatives, malformed shape, and damaged pinned-plan cases. Assert the
  planner-owned oracle's closed errors and unchanged pre-reservation state. No fixture or copy/paste
  host command is created by this proposal.
- **Local proof:** `tests/test_workspace_authorize.py` directly exercises a real
  `WorkspaceAuthority` against isolated workspace state. Its tests cover health/request shape,
  pre-grant shape, pinned-plan context and stale revisions, owner grants, exact actor/view proof,
  stored-plan authorization, release shapes, no-effect refusals, and the closed read-only operation
  classification. This component proof does not exercise the installed service or deployed host.
- **Host-only assumptions / limitations:** The local authority tests do not establish installed
  package origins, live UDS peer credentials, deployed controller wiring, Docker behavior, or the
  end-to-end absence of host effects. `authorize` itself does not reserve or execute work; the
  operation handler remains responsible for its state checks and re-proofs. The candidate exercise
  is unreviewed, no fixture exists, and this handoff assigns no live result.
- **Evidence references:** `worklogs/planning-topology-and-executable-contracts-loop/notes/e2e-live-verification-register.md`
  (E274 / `I03-LIVE-24`); `../README.md` (`I03-LIVE-24`); `tests/test_workspace_authorize.py`.
- **Planner disposition:** pending. This coder handoff does not amend the oracle, case ownership,
  fixture authorization, or live result.
