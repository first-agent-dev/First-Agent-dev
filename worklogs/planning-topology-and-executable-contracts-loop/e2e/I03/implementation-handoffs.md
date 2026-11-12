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

## I03-LIVE-28 — E508 / S3P3 staged candidate feeds `I03-LIVE-23` (merged by E515, Q143 option A)

- **Contracts / producers:** E508; S3P3 slice A; CT93, CT94, CT116, CT118, CT120; `I03-LIVE-23`
  (owning case) and `I03-LIVE-S06` (the join). Producers: `src/fa/execution/client.py::open_candidate_view`
  and `read_candidate_buffer`; `src/fa/inner_loop/tools/write_file.py::build_scoped_write_file_tool`
  (candidate branch); `src/fa/inner_loop/stage_candidate.py::capture_stage_candidate`.
- **Why the case id is not in the register.** E508 drafted this subject as `I03-LIVE-28` in the master
  sheet only. Register, index, producer-baseline and producer-coverage are frozen for this era
  (`scripts/check_execution_e2e_coverage.py:659-670`; frozen counts asserted at
  `tests/test_e2e_artifact_contract.py:340-350`, 125/89/35, and `test_register_only_reuses_s06_for_its_explicit_extension`
  admits exactly one duplicate). Q90 D4 settled the policy: new producer keys are assigned to existing
  cases, no new case ids. Q143 option A therefore makes this an **extension of `I03-LIVE-23`** rather
  than a case of its own, and this handoff is the register-side home for the keys.
- **Production path:** `_run_admission_repair` seeds a candidate for `ADMISSION_REPAIR` and `EVAL_REPLAN`
  only (`plan_promotion.seed_plan_candidate` refuses `ORDINARY_PLANNING`), so a first plan is never a
  candidate. The composition root opens the CANDIDATE view, the planner rewrites the buffer through the
  scoped writer, `capture_stage_candidate` reads it once while the view is alive, and the controller
  validates the captured bytes (label + digest) before handing them to `publish_plan`.
- **The invariant this proves.** The seed under `.fa/admission/<run>/` holds the *last admitted bytes*.
  Reading it after the stage would validate bytes nobody wrote and could promote an unchanged candidate
  as a repair. That is why the read must happen inside the view's lifetime and why a partial capture is
  a named refusal rather than "no candidate".
- **Observable effect / artifact:** local proof is `tests/test_s3p3_candidate_buffer.py` (13 passed over
  the real authority) and `tests/test_execution_composition.py::test_workflow_root_publishes_candidate_through_real_local_authority`
  (real CLI + real supervisor; the recorded trajectory must be exactly `["CANDIDATE", "CANDIDATE"]`).
  Both are local only.
- **Live observation (to fold into the `I03-LIVE-23` run sheet at STEP8):** on the host with the installed
  service and a structurally failing plan — two `WRITE_FILE` requests against a `CANDIDATE` view and none
  against `PROJECT` for the candidate address; the seeded host candidate file unchanged by the planner
  and removed after the stage; `CREATE_VIEW` carrying `candidate_scope.plan_ref` equal to the payload
  `plan_ref`; the canonical bytes becoming exactly the repaired bytes with one revision advance;
  `admission.json` recording the attempt with the candidate digest. Negative controls, canonical plan
  byte-identical each time: `candidate_scope: null` (codec refusal, no wire request), a foreign buffer
  label (`PATH_DENIED`), `write_file` on the CANDIDATE view (`denied`), a second write without the
  returned digest (`STALE_REVISION`); and a second repair round must validate the new candidate, not the
  previous round's bytes.
- **Host-only assumptions / limitations:** no fixture or run sheet is assigned (SLICE6 STEP8, after STEP7
  review). The local banks prove the substrate and the trajectory; only the host can show the installed
  supervisor, the operator's canonical checkout and a real provider-driven repair in one run.
  `I03-LIVE-23` remains `PLANNED / UNEXECUTED`.
- **Planner disposition:** pending. E515 records the merge and this handoff; it does not promote a live
  result, authorize a fixture, or amend case ownership.

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

## I03-LIVE-27 — Q85 / CT113 / E283 controller-attested workspace handoff

- **Contracts / producers:** Q85 (answered by E282); CT113; SLICE2 STEP6; `I03-LIVE-27`;
  L-HAND-1 and L-HAND-2. The local authority+route leg is implemented (E283). The distinct
  controller leg is still pending under CT108 / SLICE5 STEP2; the integrated outer-chat join is
  I03-LIVE-S08. These are linked obligations, not one claimed implementation.
- **Verified source references:** `src/fa/execution/primitives.py::Operation.HANDOFF`;
  `src/fa/execution/service.py::SupervisorService._handoff`;
  `src/fa/execution/workspace.py::WorkspaceAuthority.handoff`, `_handoff_owner`, `_settled`;
  `src/fa/execution/client.py::ExecutionClient.request`;
  `src/fa/inner_loop/tools/workflow_tool.py::build_invoke_workflow_tool`'s `handler` and
  `_child_run_context`; `src/fa/session/manager.py::SessionManager.begin_run`;
  `tests/test_execution_handoff.py`.
- **Production path:** The existing `handoff` wire operation carries the caller namespace and
  `target_namespace`; `_handoff` constructs the target `NamespaceRef` and calls the authority.
  `WorkspaceAuthority.handoff` proves the owner, requires every WRITE view settled and no
  `intent.json`, requires this process's live writer fd, then checks same session, target parent
  equals caller run, and target run differs. `_handoff_owner` performs one private metadata replace
  and read-back before returning a fresh capability; generation, owner namespace, status and current
  revision do not change. Q85 deliberately makes the parent link controller-attested: the controller
  must allocate the child via `_child_run_context` / the existing `SessionManager.begin_run`; the
  authority does not look up or attest target-run existence.
- **Pending controller seam (source-verified, not implemented):** `ExecutionClient.request` is a
  generic one-shot RPC and does not resend after an uncertain send, but there is no controller call
  to `Operation.HANDOFF` and no `ExecutionClient.handoff` convenience method. The current workflow
  handler refuses acquisition-dependent nested roles before child dispatch; it has no parent
  mutator drain/suspension or server-acknowledged grant-transfer path. SLICE5 STEP2 must later drain
  and settle parent writes, allocate once, call the existing wire operation once, validate the returned
  grant, and dispatch only after acknowledgement. A refusal or uncertain reply means no child dispatch
  and no retry with a new request id. The parent/child controller proof is not supplied by this local
  authority handoff or by I03-LIVE-27 alone.
- **Observable effect / artifact:** Local CT113 tests observe the same-generation grant transfer,
  changed active actor, unchanged owner/status/revision, old-capability denial, cached same-request
  replay, and byte-identical refusal state for unsettled views/intent and invalid namespaces. The
  planner-owned I03-LIVE-27 row remains the surface oracle; L-HAND-1 covers the grant/epoch/replay
  chain and L-HAND-2 covers unsettled refusal. The separate I03-LIVE-S08 join owns the actual nested
  controller/outer-chat witness.
- **Host prerequisites:** An approved filesystem and deployed service/dispatcher under the controller
  UID; an actual same-session child allocated by `SessionManager.begin_run`; a live writer fd; and
  real view/cell settlement observations for the open/sealed cases. The approved deployed SHA, image,
  profile, configuration and commands must be supplied from the actual host, not inferred here.
- **Candidate fixture / command: [PROPOSAL]** After SLICE6 STEP7 review and planner/operator
  disposition, map the existing L-HAND-1/2 host scenarios to I03-LIVE-27 on an approved disposable
  workspace. Keep the existing expected observations and negative controls; no new fixture, host
  command, acceptance oracle or case ownership is proposed in this handoff.
- **Local proof:** `tests/test_execution_handoff.py` is the real-authority/composed-route bank
  (17 passed; 15/15 assertion-only mutants killed in the existing E283 evidence). It proves local
  component behavior only: it does not allocate the target through a real `begin_run`, run a deployed
  service as the controller UID, or supply a kernel-observed live-cell settlement.
- **Host-only assumptions / limitations:** I03-LIVE-27 is **PLANNED / UNEXECUTED** and its live result
  remains **NOT RUN**. L-HAND-1/2 are planned host evidence, not local status promotions. This entry
  does not prove the pending SLICE5 controller path, the I03-LIVE-S08 nested workflow, installed
  origins, Docker/cgroup behavior, or deployment readiness. No fixture exists and STEP7 review must
  precede any fixture/helper implementation.
- **Evidence references:** `../README.md` and `live-verification.md` (`I03-LIVE-27`);
  `../../notes/i03-live-e2e-test-plan-2026-10-22.md` (L-HAND-1/2);
  `../../notes/e2e-live-verification-register.md` (E282/E283);
  `../../increments/increment-03-execution-workspace-foundation.md` (CT113, SLICE2 STEP6,
  CT108/SLICE5 STEP2, E287); `tests/test_execution_handoff.py`.
- **Planner disposition:** pending. This coder handoff records source facts and evidence limits only;
  it does not amend the planner-owned oracle, case ownership, fixture authorization, host result, or
  live status.

## I03-LIVE-S07 — Q109-B rooted managed discovery (candidate ledger-append exercise)

- **Contracts / producers:** Q109-B; I03 spec §4; S4P2/STEP2b/Q97; existing
  `I03-LIVE-S07` cell-local tool-route oracle. This proposal does not create a new live ID or change
  the current `NOT RUN` result.
- **Verified local seam:** `project_tools._dispatch("fs_reach", ...)` builds the real registry; the
  managed reach builder opts into strict rooted reads; `StructuralIndex._build` enumerates candidates
  and the rooted reader opens the relative file under one pinned root descriptor. The implemented
  `tests/test_execution_project_tools.py::test_cell_reach_refuses_symlink_replacement_after_enumeration`
  replaces an enumerated source with an outside-view symlink and checks for a non-retryable refusal.
- **Local verification (2026-11-01):** The rooted-read target bank completed with 87 passed and two
  existing Q106 xfails. Positive controls resolve in-root file/directory symlinks to one canonical
  target; reader-level escape, link-replacement, identity-drift and over-limit tests refuse. The
  integrated C3 race returns non-retryable `reach_failed` with no partial result. Ruff, mypy
  (`--python-version 3.13`), compileall and `git diff --check` passed.
  Targeted mutation checks both killed (a) bypassing `RootedFileReader` in the producer and (b)
  removing the managed strict-read binding. Pytest ran under Python 3.11 with a temporary
  `typing.override` compatibility shim; Python 3.13 was unavailable, so this is not supported-runtime
  evidence or live-host acceptance.
- **Candidate live exercise: [PROPOSAL]** After STEP7 review, Q108 transport and STEP2b production
  wiring, arrange one approved mutable PROJECT view with a safe Python file and a controlled outside
  sentinel. Invoke the installed fixed project-helper EXEC through the real controller/supervisor.
  Inject replacement only after enumeration and before content open. Positive control: an ordinary
  in-view symbol resolves. Adversarial outcome: the race returns an explicit non-retryable refusal,
  never the sentinel name/content, and performs no host-path read. Re-submit the exact completed
  request identity to exercise Q75 replay: assert the same stored refusal and exactly one original
  journal operation/RUN, with no helper re-execution. Append the dated attempt/evidence directory to
  the existing `I03-LIVE-S07` attempt table only after observing the deployed SHA, image, profile,
  config, run ID, command, return code/effect and independent reviewer.
- **Negative controls / host limits:** Removing the rooted-reader producer or its binding in a test
  build must make the adversarial case observe the sentinel and fail. This is a host-owned test mutant,
  not permission to edit an approved deployment. Local fault injection proves neither Docker/cgroup
  containment nor deployed journal behavior; actual fixture and command remain unassigned until the
  live-plan owner approves them.
- **Planner disposition:** pending. This proposal does not amend the I03-LIVE-S07 oracle, authorize a
  fixture/host command, or assign a live result.

## Q112/R02 — entrypoint readiness refusal and session-ledger handoff (PROPOSAL ONLY)

- **Source and contract:** `scripts/fa-entrypoint.sh::_prepare_entrypoint_workspace` and its managed-session caller refuse auto-run after failed `workspace_bootstrap ensure`, before session provisioning, `.active` publication, and `fa run`; an explicit command override remains available and skips auto-run provisioning. Only a fresh unpublished clone may be removed; a resumed workspace is retained.
- **Local evidence:** `tests/test_fa_entrypoint.py` passed 20 tests on CPython 3.13.16. Ruff, `bash -n`, `compileall`, and `git diff --check` passed. Producer mutation bypassing the refusal and edge mutation provisioning an explicit override were both killed and restored. This is shell/test-double evidence only; successful bootstrap is not proof of a managed EXEC backend.
- **Deferred live exercise:** `../../notes/i03-live-e2e-test-plan-2026-10-22.md`, §4.2 proposes fresh/resumed readiness refusal, explicit override, and successful managed auto-run cases. The host oracle reads the authoritative SQLite `session.db`: `session_meta` run bindings plus `event_log` rows, with before/after snapshots reopened from disk. It verifies no provision/run append on refusal or override and one run binding plus durable run events on the successful control.
- **Host-only assumptions / limitations:** proposal only; no fixture, deployed command, live ID assignment, or host evidence is authorized or present. Execute after merge to `main` and the planned user-host `fa update`, with an approved image/state root and controlled readiness cause. Record actual evidence only in the planner-approved register; Docker/cgroup and backend acceptance are not inferred from local tests.
