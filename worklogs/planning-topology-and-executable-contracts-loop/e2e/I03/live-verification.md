# I03 live verification - master sheet

**Status: PLANNED - every case below is `NOT RUN`. Nothing here is evidence of live
behaviour.** This sheet is the integrated I03 master record described by
`notes/e2e-handoff-and-plan-review-design.md` section 3 and I03 SLICE6 STEP2. The index
that maps these cases to slices, contracts and run sheets is `../README.md`.

## Provenance of this file

| Field | Value |
| --- | --- |
| Source register | `worklogs/planning-topology-and-executable-contracts-loop/notes/e2e-live-verification-register.md` |
| Rows imported | 34 unique cases (26 surfaces + 8 joins; both S06 observations retained) |
| Oracle text | copied from the register; the historical and extended S06 observations are both retained; no new acceptance oracle is authored here |
| Live result | `NOT RUN` for every case; only an operator or an independent evidence reviewer assigns PASS/FAIL/BLOCKED |
| Generated | 2026-10-23, reconciled against the merged register through E278 (adjacent tip `899cc16`) |

## Vocabulary and rules (normative)

- **Live result is exactly `NOT RUN | PASS | FAIL | BLOCKED`** (Q63, E231;
  `notes/artifact-schema-and-grammar.md` section 6). No other value, no reason enum,
  no mandatory BLOCKED reason.
- **`commentary` is optional in every state**, <=512 UTF-8 bytes, single line,
  credential-redacted, and **never** used for control flow.
- **`NOT RUN` and `BLOCKED` never count as PASS.**
- **Local proof and live result are separate.** A green local suite says nothing about
  the deployed host; `Local proof` records what exists in-repo and is not a live
  verdict.
- **Attempts are append-only.** A new run appends a row; it never edits, reorders or
  deletes an earlier one. Each attempt carries the identity CT88 requires: deployed
  SHA, image digest, profile, config, run id, command, rc/effect, artifact, reviewer.
- **This file is checked, not trusted:** `tests/test_e2e_artifact_contract.py` validates
  the JSON Schema with all four states (commentary present and absent, including the
  UTF-8 byte limit) and checks this sheet's IDs, current NOT RUN status and attempt
  columns. It does not parse or evaluate host evidence and never assigns a live result.

## Cases

### I03-LIVE-01

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-01` |
| Kind | surface |
| Producer | I03-LIVE-01 `src/fa/controller_entry.py` |
| Subject | Installed isolated entry and dependency/origin closure |
| Increment | I03 |
| CTs (provisional mapping) | CT98 (provisional mapping) |
| Phase | P1 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_controller_entry.py |
| Expected live observation | Boot actual image entrypoint/wrapper/help/auto-run/session with hostile CWD/PYTHONPATH/editable-pth/project venv. Assert installed module origins and unchanged controller/control sentinels; no project import before cell admission. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-01` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-01

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-02

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-02` |
| Kind | surface |
| Producer | I03-LIVE-02 `src/fa/execution/__init__.py` |
| Subject | Execution package installation |
| Increment | I03 |
| CTs (provisional mapping) | CT98 (package-origin closure; no independent producer) (provisional mapping) |
| Phase | P1 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | none recorded |
| Expected live observation | Build/install frozen wheel in actual controller and cell images using supported CPython 3.13 with `zlib` and the frozen build dependencies; assert execution package origins/dependency closure and no source/editable shadow. Missing `zlib`, setup errors or unavailable build deps are BLOCKED, never a pass/skip. Package marker has no independent runtime producer. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-02` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-02

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-03

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-03` |
| Kind | surface |
| Producer | I03-LIVE-03 `src/fa/execution/types.py` |
| Subject | Namespace/view/operation/receipt/grant projections |
| Increment | I03 |
| CTs (provisional mapping) | CT99, CT100, CT101, CT102, CT103 (provisional mapping) |
| Phase | P3 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | no dedicated suite; exercised by test_execution_admission.py, test_execution_attach.py, test_execution_backend.py |
| Expected live observation | Actual UDS wrong namespace/view/generation, forged receipt and malformed grant cases deny before effects. Read persisted receipt identities; durable journals contain no capability; IDs alone authorize nothing. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-03` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-03

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-04

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-04` |
| Kind | surface |
| Producer | I03-LIVE-04 `src/fa/execution/protocol.py` |
| Subject | Closed codec, bounded frames, DeadlineConnection |
| Increment | I03 |
| CTs (provisional mapping) | CT99, CT100 (provisional mapping) |
| Phase | P6 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_protocol.py |
| Expected live observation | Actual socket partial/oversize/duplicate-key/nonfinite/unknown-field frames, expired input and command-over-control-budget. Assert zero denied create/RUN, bounded replies, no reset or automatic replay. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-04` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-04

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-05

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-05` |
| Kind | surface |
| Producer | I03-LIVE-05 `src/fa/execution/profiles.py` |
| Subject | Approved profile rendering |
| Increment | I03 |
| CTs (provisional mapping) | CT100a (provisional mapping) |
| Phase | P1 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | no dedicated suite; exercised by test_execution_client.py, test_execution_dispatch.py, test_execution_views.py |
| Expected live observation | Actual image/inspect/host facts: pinned image, nonroot, private namespaces, capdrop/NNP/seccomp/resource limits, network none and only approved source/scratch/cache mounts. Deny raw image/mount/env/daemon overrides; inspect is not host attestation. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-05` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-05

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-06

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-06` |
| Kind | surface |
| Producer | I03-LIVE-06 `src/fa/execution/supervisor.py` |
| Subject | PeerIdentity, dispatcher, completed-reply cache and input hash |
| Increment | I03 |
| CTs (provisional mapping) | CT99, CT100 (provisional mapping) |
| Phase | P5 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_supervisor.py |
| Expected live observation | Real private UDS kernel peer authentication, exact input reservation, durable begin/DONE and original reply replay. Exercise revoked-proof Q75, cache loss/saturation/restart and denied peer; no callback/reexecution/grant reconstruction. Verify the original absolute deadline reaches actual admission/backend and all request-path journal lock waits; no fresh phase budget or late follow-up. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-06` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-06

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-07

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-07` |
| Kind | surface |
| Producer | I03-LIVE-07 `src/fa/execution/journal.py` |
| Subject | Single supervisor, reservation/begin/create/start/CID/cancel/completion/recovery |
| Increment | I03 |
| CTs (provisional mapping) | CT100, CT104, CT107 (provisional mapping) |
| Phase | P5 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_journal.py |
| Expected live observation | Kill supervisor at each durable boundary, including lost create/start and completed-creation/DONE-with-live-cell cases. Enumerate every EXEC record with durable CID, including DONE; observe/stop only the original labelled CID, preserve its completed result, and verify no renewed begin/create/start/attach/RUN. Observe unknown fencing, durable cancel before signal and secret-free files. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-07` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-07

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-08

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-08` |
| Kind | surface |
| Producer | I03-LIVE-08 `src/fa/execution/plans.py` |
| Subject | ProtectedPlanContext and actual plan recheck |
| Increment | I03 |
| CTs (provisional mapping) | CT97, CT100, CT110, CT111 (provisional mapping) |
| Phase | P5 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_plans.py |
| Expected live observation | Actual protected view/context and controller-admitted PlanRef; change source/hash before admission/exec and forge worker plan hash. Deny effects or completion. Ordinary no-active-workflow null allowed; formal evidence null denied. Never infer ordinary mode from null or PROJECT alone. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-08` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-08

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-09

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-09` |
| Kind | surface |
| Producer | I03-LIVE-09 `src/fa/execution/client.py` |
| Subject | ExecutionClient and all ManagedBashExecutor methods |
| Increment | I03 |
| CTs (provisional mapping) | CT100 (provisional mapping) |
| Phase | P5 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_client.py |
| Expected live observation | Actual tool/PTY run/INTERRUPT/CLOSE/LIST with 15 closed errors, supplied/missing references, timeout and disconnect. Persist truthful typed outcomes; no host shell/reconnect/resend. Control uncertainty replays original control input, never exec-inspects its request ID. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-09` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-09

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-10

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-10` |
| Kind | surface |
| Producer | I03-LIVE-10 `src/fa/execution/cell_protocol.py` |
| Subject | Private worker codec |
| Increment | I03 |
| CTs (provisional mapping) | CT100 (provisional mapping) |
| Phase | P2 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | no dedicated suite; exercised by test_execution_attach.py, test_execution_backend.py |
| Expected live observation | Actual non-TTY cell stream with split/oversize/malformed frames, wrong request/session binding and command/control concurrency. Reject invalid frames without privilege/grant/path leakage or invented success. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-10` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-10

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-11

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-11` |
| Kind | surface |
| Producer | I03-LIVE-11 `src/fa/execution/cell_worker.py` |
| Subject | Persistent worker, one-shot worker and module main |
| Increment | I03 |
| CTs (provisional mapping) | CT100 (provisional mapping) |
| Phase | P2 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_cell_worker.py |
| Expected live observation | Keep interactive two-command shell-state reuse as its own case. For the approved noninteractive one-shot profile, `session_id=null` is accepted only there; two sequential distinct operations get fresh cells/attaches and one RUN apiece, with real nonzero/timeout outcomes and no worker reuse/replay. Force reply visibility before sender return/gate retirement, then issue interactive RUN2 and prove it waits at publication rather than false-busy/reexecution. Exercise concurrent interrupt/close/list/STOP and EOF. STOP/worker exit is not cgroup emptiness. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-11` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-11

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-12

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-12` |
| Kind | surface |
| Producer | I03-LIVE-12 `src/fa/execution/worker_client.py` |
| Subject | Sole attach, RUN/control multiplexing and stream-loss handling |
| Increment | I03 |
| CTs (provisional mapping) | CT100 (provisional mapping) |
| Phase | P2 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | no dedicated suite; exercised by test_execution_attach.py |
| Expected live observation | Real Docker attach one RUN plus concurrent controls, correlation mismatch and forced stream loss. All affected requests become uncertain without resend/reconnect; verify no duplicate command sentinel. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-12` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-12

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-13

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-13` |
| Kind | surface |
| Producer | I03-LIVE-13 `src/fa/execution/docker.py` |
| Subject | Authenticated native HTTP, create/start/inspect/attach/force-stop |
| Increment | I03 |
| CTs (provisional mapping) | CT100a (provisional mapping) |
| Phase | P2 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_docker.py |
| Expected live observation | Real approved daemon: owned labels/image/CID, original-name recovery, attach Upgrade/mux/stderr limits, fixed full-CID SIGKILL after durable cancel and independent same-CID inspect. Foreign/rebound identity, 409/404/loss/malformed replies remain truthful; no ACK-as-terminal barrier. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-13` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-13

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-14

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-14` |
| Kind | surface |
| Producer | I03-LIVE-14 `src/fa/execution/view_io.py` |
| Subject | RootedViewIO and actual admitted text IO |
| Increment | I03 |
| CTs (provisional mapping) | CT103 (provisional mapping) |
| Phase | P3 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_view_io.py |
| Expected live observation | Actual tool and PTY same-view read-your-writes; immutable readers stay pinned. Exercise no-follow/link/FIFO/owner/protected-PlanRef/size/UTF8/window/hash/expected-absence, parent-swap and fsync faults. Assert canonical/control sentinels, modes/UIDs, retained descriptors through drain and explicit conflict/uncertainty. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-14` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-14

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-15

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-15` |
| Kind | surface |
| Producer | I03-LIVE-15 `src/fa/runtime/pty_pool.py` |
| Subject | Fractional PTY deadlines consumed by worker |
| Increment | I03 |
| CTs (provisional mapping) | CT100 (provisional mapping) |
| Phase | P1 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_pty_pool_narrowing.py |
| Expected live observation | Actual installed PTY backend receives subsecond remaining budget; normal/nonzero/timeout preserve result fields and responsiveness, no timeout truncation to zero or new process scope. Actual cgroup cleanup remains independently required. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-15` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-15

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-16

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-16` |
| Kind | surface |
| Producer | I03-LIVE-16 `Dockerfile.fa` |
| Subject | Noneditable install and isolated build checks |
| Increment | I03 |
| CTs (provisional mapping) | CT98, CT100a (provisional mapping) |
| Phase | P1 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_container_build_invariants.py |
| Expected live observation | Build actual approved immutable image; record wheel/image/dependency SHA, isolated help/origin checks and deployed entrypoint/mount facts. Build checks alone do not prove runtime cutover or kernel isolation. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-16` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-16

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-17

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-17` |
| Kind | surface |
| Producer | I03-LIVE-17 `src/fa/execution/workspace.py` (E253–E256 local ownership foundation) |
| Subject | Actual workspace registration/R0/writer owner |
| Increment | I03 |
| CTs (provisional mapping) | CT101, CT102, CT103, CT104, CT105, CT106, CT107, CT107a (provisional mapping) |
| Phase | P3 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_workspace.py, test_workspace_publication.py |
| Expected live observation | On approved Linux filesystem, quiesce legacy writers; register dirty roots, reject bind/inode/nested aliases/rebind and protected overlap; race two OS actors for one durably advanced writer; kill/restart with old owned views and verify quarantine/no renewed grant. Preserve canonical index/sentinels, enforce input/copy/fsync faults and retain revisions/pins. E253 registration/writer, E255 readers, E256 PROJECT views, E257 admission/close/drain/trusted inputs, E258 approved-profile/execution-trusted accessors and E259's closed purpose matrix (CANDIDATE/VERIFICATION/MUTATION/PROVISIONING views, purpose write gate, scoped candidate buffer) are local component proofs in this module; none is deployed admission/backend integration. Live witnesses must cover: all five purpose combinations construct real views; every forbidden purpose/access/scope/plan tuple denies INPUT_POLICY before any effect; MUTATION writes outside src//scripts deny PATH_DENIED; VERIFICATION has no write path; candidate buffer bytes land only in supervisor staging and never at canonical .fa/admission. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-17` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-17

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-18

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-18` |
| Kind | surface |
| Producer | I03-LIVE-18 `src/fa/execution/backend.py` (E258 local CellBackend episode owner; E260 R1–R5 refinements; E261 one-shot CANCEL gap) |
| Subject | Profile-specific episode lifetime, guarded launch, exact-view cancel, complete owned-cell recovery and one absolute deadline |
| Increment | I03 |
| CTs (provisional mapping) | CT100 (provisional mapping) |
| Phase | P2 |
| Register origin | E250 — I03 complete source/seam inventory, 2026-10-18 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_backend.py |
| Expected live observation | Actual installed service + approved daemon + real worker: interactive commands share one episode; each distinct noninteractive EXEC accepts null session only on the fixed one-shot profile and gets a fresh cell/attach/one RUN; same-op replay never creates/re-sends. Cancel a running one-shot using its exact journal-bound CID without relying on the interactive episode map; wrong-view cancel is `UNAUTHORIZED` with unchanged journal and no daemon request. Force close-before-effect (zero create/start/attach/RUN) and effect-before-close (close/drain waits); a close after attach blocks RUN. Restart after a creator record is DONE but its interactive cell is live inspects/stops only the durable original CID/labels, keeps DONE unchanged, and never creates/starts/attaches/RUN. Hold real journal flock and episode-lock contention under one request deadline; expiry before transaction/effect yields `BACKEND_UNAVAILABLE` and zero Docker effects, while possible post-write/effect uncertainty is preserved. Foreign name/labels deny; no `CommandOutcome` terminality claim. Local component proof is not deployed cell/cgroup evidence. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-18` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-18

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-19

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-19` |
| Kind | surface |
| Producer | I03-LIVE-19 `src/fa/execution/publication.py` (E267 local seal component) |
| Subject | Post-barrier recompute, sealed manifest v1, tombstones, protected-plan boundary, `STOPPING → SEALED` with read-back, content-derived revision id |
| Increment | I03 |
| CTs (provisional mapping) | CT105 (provisional mapping) |
| Phase | P5 (provisional: row postdates notes/i03-live-e2e-test-plan-2026-10-22.md section 2) |
| Register origin | E267 — nineteenth production surface: `execution/publication.py` (seal), PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_workspace_publication.py |
| Expected live observation | On the approved filesystem, with a real worker/attach cell: stop a view with real descendants, mutate the view's source *after* the barrier through a still-open descriptor and through a fork/double-fork/setsid writer, then seal. Observe: the sealed manifest's `tree_sha256` matches a recompute over the frozen bytes and not the pre-barrier input hash; a tombstone appears only for a genuinely removed base path; a changed plan path or a new/changed link is refused with the view left `STOPPING` and **no** `sealed.json`; a killed supervisor between manifest write and `SEALED` leaves either a re-sealable `STOPPING` view or a `SEALED` view whose stored manifest still matches its recompute. Negative controls: disable `_validate_sealed_tree`, and separately let the manifest write happen before the terminality precondition. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-19` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-19

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-20

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-20` |
| Kind | surface |
| Producer | I03-LIVE-20 `src/fa/execution/publication.py::publish_view` (E269 local publish component) |
| Subject | Fenced publication: intent-before-pointer ordering, `current.json` as the only commit discriminator, materialization from the sealed manifest under the derived id, canonical projection that preserves `.git/index` and excluded trees, projection proof, `PUBLISHED` settlement |
| Increment | I03 |
| CTs (provisional mapping) | CT106 (provisional mapping) |
| Phase | P5 (provisional: row postdates notes/i03-live-e2e-test-plan-2026-10-22.md section 2) |
| Register origin | E267 — nineteenth production surface: `execution/publication.py` (seal), PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_workspace_publication.py |
| Expected live observation | On the approved filesystem, with a real worker/attach cell and a real reader pin: seal a view whose source adds a file, deletes one and changes a mode; publish it. Observe: `current.json` gains exactly the five §5.1 keys with the derived `revision_id`; the new revision verifies; canonical bytes equal the sealed bytes with logical modes restored; the pinned reader still reads the old bytes while a fresh pin reads the new revision; `.git/index`, `.fa/artifacts` and `.venv` are byte-identical; `intent.json` is absent afterwards and `view.json` says `PUBLISHED`; a second publish returns the same revision with the caller's own `operation_id` and writes no second intent; `release` then succeeds and the workspace survives a restart as `AVAILABLE`. Then the fault rows: SIGKILL after the pointer replace but mid-projection must leave `current.json` at the committed revision with intent `PROJECTING`, a canonical tree that is a complete Rold or Rnext-projection (never a mixture that verifies), and a workspace that refuses further work until recovery; SIGKILL before the pointer must leave no reachable revision. Negative controls: remove `publish_view -> _commit_current`, and separately remove the canonical projection proof. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-20` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-20

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-21

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-21` |
| Kind | surface |
| Producer | I03-LIVE-21 `src/fa/execution/publication.py::render_bundle` / `prepare_bundle` (E271 local bundle component) |
| Subject | Trusted bounded renderer + private bundle store: controller-owned frontmatter, three files only, disguised-metadata/heading/slice refusals, durable `bundles/<id>/{bundle.json,files}` bound to workspace, generation and base revision |
| Increment | I03 |
| CTs (provisional mapping) | CT107a, CT109a (provisional mapping) |
| Phase | P5 (provisional: row postdates notes/i03-live-e2e-test-plan-2026-10-22.md section 2) |
| Register origin | E267 — nineteenth production surface: `execution/publication.py` (seal), PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_workspace_publication.py |
| Expected live observation | On the approved filesystem with a real owner grant: prepare a bundle for a project slug from plain prose. Observe: exactly three files appear under `worklogs/<slug>/` in the bundle directory (never in the canonical tree), each manifest digest matches its bytes, the bundle records the prepare-time `base_revision`/`generation`/`workspace_id`, a second prepare yields the same `bundle_sha256` with a different id, a stale `expected_base_revision` is refused, and a bundle prepared while a view is unsettled is refused `WORKSPACE_BUSY`. Negative controls: drop the disguised-metadata scan, drop the fixed frontmatter, drop the base CAS. Install is its own row (`I03-LIVE-22`) now that Q82 is settled as (B). |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-21` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-21

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-22

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-22` |
| Kind | surface |
| Producer | I03-LIVE-22 `src/fa/execution/publication.py::install_project` (E271 unit B local install component) |
| Subject | BOOTSTRAP install of one rendered bundle as `worklogs/<project_slug>` inside the preparing workspace (Q82 (B)): durable `intent.json` (`kind=BOOTSTRAP`, `target_relative`, `new_sha256` = bundle digest) before the irreversible point, `renameat2(RENAME_NOREPLACE)` of a staged copy, then revision + `current.json`, then the projection proof |
| Increment | I03 |
| CTs (provisional mapping) | CT107a, CT109a (provisional mapping) |
| Phase | P5 (provisional: row postdates notes/i03-live-e2e-test-plan-2026-10-22.md section 2) |
| Register origin | E267 — nineteenth production surface: `execution/publication.py` (seal), PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_workspace_publication.py |
| Expected live observation | On the approved filesystem with a real owner grant: install a bundle prepared for the current base revision. Observe: the three project files appear at `worklogs/<slug>/…` with modes 0644/0755 and are **never** byte-different from the bundle; `current.json` advances to the derived revision, the revision verifies, the canonical tree equals it, the intent is gone, and the bundle directory is retained. Then the refusals, each leaving the canonical tree and pointer untouched: an existing project (`COLLISION`, its bytes byte-identical), a stale `base_revision` (`STALE_REVISION`), another workspace's bundle, a retargeted slug, an unsettled view (`WORKSPACE_BUSY`), a tampered bundle (same-size byte flip). Then the fault rows: SIGKILL after the rename must leave the installed directory and the intent with the pointer still old, and must never delete the installed files on restart; SIGKILL between the rename and the revision must recover forward. Negative controls: remove the pre-rename intent, replace `RENAME_NOREPLACE` with an ordinary rename, remove the pointer commit, remove the bundle digest check. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-22` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-22

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-23

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-23` |
| Kind | surface |
| Producer | I03-LIVE-23 `src/fa/execution/publication.py::publish_plan` (E273 local replacement component) |
| Subject | Q58 canonical plan replacement **through the authority**: the same-path `os.replace` is the irreversible point, and the revision + `current.json` complete forward afterwards — the inverse order of publish and install. Rules imported from `plan_admission` (≤ 1 MiB, strict UTF-8, non-empty), shape fixed to `worklogs/<slug>/increments/<name>.md`, durable `intent.json` (`kind=PLAN`, `old_sha256`, `new_sha256`, `next_revision`, `phase=PREPARED`) before the replace, no rollback after it |
| Increment | I03 |
| CTs (provisional mapping) | CT107a (provisional mapping) |
| Phase | P5 (provisional: row postdates notes/i03-live-e2e-test-plan-2026-10-22.md section 2) |
| Register origin | E267 — nineteenth production surface: `execution/publication.py` (seal), PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | none recorded |
| Expected live observation | On the approved filesystem with a real owner grant: replace a canonical plan whose ref names the committed bytes. Observe: the file at the **same path** becomes exactly the new bytes with its mode preserved, `current.json` advances to the derived revision, the revision tree names the new digest and size, the superseded revision still serves the old bytes to a pinned reader, the intent is gone, and no temporary survives in `worklogs/…` or `.fa/publish-tmp`. Then the refusals, each leaving the plan byte-identical and the pointer old: a stale ref hash (`STALE_REVISION`), a path that is not the canonical plan, bytes that are not a plan, a capability that is not this workspace's grant (`UNAUTHORIZED`), an unsettled view (`WORKSPACE_BUSY`), a link swapped in after staging (`PATH_DENIED`). Then the fault rows: kill *after* the replace and before the revision must keep the new bytes and the `PREPARED` intent and must never restore the old ones; kill between the revision and the pointer must complete forward on restart. Negative controls: remove the pre-replace re-proof, remove the durable intent, remove the revision commit, restore the old bytes after a failure. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-23` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-23

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-24

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-24` |
| Kind | surface |
| Producer | `src/fa/execution/workspace.py::authorize` (E274 pre-reservation authority check) |
| Subject | Pre-reservation grant proof and stored plan-context recheck in `WorkspaceAuthority.authorize` |
| Increment | I03 |
| CTs (provisional mapping) | CT99 (provisional mapping) |
| Phase | P5* |
| Register origin | E274 — SLICE1 STEP3 part 1, CT99 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | `test_workspace_authorize.py` (local only) |
| Expected live observation | The dispatcher's `authorize` seam over the real authority and a real peer credential: closed envelope shape is enforced by the wire decoder; the authority proves `_owner_only` for view-less requests and `_proof_only` for view-scoped requests (`RELEASE` in both shapes); stored `ProtectedPlanContext` for `pin_reader`/`create_view`/`exec` is rechecked against pinned revision bytes. On the approved filesystem with the installed service and controller UID, authorized requests proceed; wrong/absent capability, foreign namespace, swapped `view_id`, and wrong shape are refused with the exact closed code before any reservation (`operations/` unchanged, no `docker ps` delta, no canonical byte or grant changed). Damage the pinned plan in revision data and verify `pin_reader`/`create_view`/`exec` refuse `INPUT_POLICY` while the owner grant still works. Negative controls: remove owner proof, replace view proof with “any live view,” and remove plan recheck. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-24` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-24

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-25

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-25` |
| Kind | surface |
| Producer | `src/fa/execution/workspace.py::_load -> _recover_intent (E276 forward recovery, CT107)` |
| Subject | CT107 forward recovery at durable boundaries: complete forward, discard only provably uncommitted work, or quarantine with intent intact |
| Increment | I03 |
| Slice (provisional mapping) | SLICE3 |
| CTs (provisional mapping) | CT107 (provisional mapping) |
| Phase | P5* |
| Register origin | E276 — CT107 forward recovery, SLICE3 STEP4 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_workspace_recovery.py (local only) |
| Expected live observation | On the approved filesystem with the installed service: SIGKILL the supervisor (a) before the intent, (b) after the intent before the irreversible syscall, (c) after the syscall before its fsync, (d) after the pointer replace before the first projection byte, (e) midway through a multi-file projection, (f) after `DONE` before the reply; observe after restart that every committed revision is complete, that no canonical byte of an uncommitted attempt survives, that `pending/` holds no entry the authority ignores, and that a workspace the authority cannot settle is `QUARANTINED` with its `intent.json` still present while other workspaces keep loading. Separately label process-crash from power-loss evidence and include an fsync-unsupported/EIO case. Negative controls: trust `phase` instead of `current.json`, delete a successfully installed bootstrap directory, overwrite a third plan version, settle a view the intent does not name. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-25` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-25

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |


### I03-LIVE-26

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-26` |
| Kind | surface |
| Producer | `src/fa/execution/service.py (E277 composed supervisor: route table, socket owner, main)` |
| Subject | Composed supervisor over the real authority, journal, dispatcher and private UDS |
| Increment | I03 |
| Slice (provisional mapping) | SLICE1 |
| CTs (provisional mapping) | CT99 (provisional mapping) |
| Phase | P5* |
| Register origin | E277 — composed supervisor, SLICE1 STEP3 — PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | test_execution_service.py (local only) |
| Expected live observation | On the approved host with the operator config and the controller's UID: start `fa-execution-supervisor` (via `build_supervisor`/`main`) and observe that the socket appears only after recovery and is `srw-------` owned by the service user; send one request per operation and observe the exact closed reply per owner (register/acquire/pin/create_view/read/write/edit/release/seal/publish/bundle/install) while `exec`, `inspect`, `cancel`, `pty_control`, `handoff` and `register{create:true}` each refuse `BACKEND_UNAVAILABLE` with a durable `UNKNOWN` reservation where the operation reserves; verify a wrong UID is rejected before any frame is read, an unknown config key refuses startup, and SIGTERM stops acceptance and unlinks the socket without stranding an admitted handler. Negative controls: bind before recovery, `chmod 0600` removed, a dormant route returning `{}`, and `create_view` dropping the wire `base_revision`. Note that `seal` refuses `TERMINALITY_UNKNOWN` until the cgroup observer exists, so a full stage cannot be completed through this surface yet. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-26` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-26

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |


### I03-LIVE-S01

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-S01` |
| Kind | join |
| Producer | I03-LIVE-S01 |
| Subject | Installed launch → actual supervisor/controller → private authenticated UDS |
| Increment | I03 |
| CTs (provisional mapping) | CT98, CT99, CT100a (provisional mapping) |
| Phase | P5 |
| Register origin | Cross-module joins — all planned, not shipped composition |
| Register status | PLANNED / UNEXECUTED |
| Local proof | composed join - see the component rows named in Subject |
| Expected live observation | Boot the actual `build_supervisor/main`, installed entrypoint and private UDS service with hostile CWD/PYTHONPATH/editable-pth/project venv; prove installed origins, no workspace-source shadow, no unrestricted Docker socket/control secret in the model-facing controller, and zero project host/controller commands on unavailable backend. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-s01` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-S01

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-S02

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-S02` |
| Kind | join |
| Producer | I03-LIVE-S02 |
| Subject | Dispatcher → actual WorkspaceAuthority.admit/effect → CellBackend |
| Increment | I03 |
| CTs (provisional mapping) | CT99, CT100, CT101, CT103 (provisional mapping) |
| Phase | P4 |
| Register origin | Cross-module joins — all planned, not shipped composition |
| Register status | PLANNED / UNEXECUTED |
| Local proof | composed join - see the component rows named in Subject |
| Expected live observation | Real actor/generation/pin/profile/PlanRef and one original deadline from request receipt through authority/registry/episode locks, journal flock/transactions, Docker, attach and RUN. `admit()` alone is not an effect guard: force close-wins before `WorkAdmission.effect()` (zero create/start/attach/RUN/write) and effect-wins (close/drain waits); close between attach and RUN denies RUN. Force journal/episode lock expiry before a write and assert `BACKEND_UNAVAILABLE` with no late effect; retain uncertainty if a mutation may have begun. E251/E257/E258 and E260 are LOCAL component owners only; this composed live join remains PLANNED/UNEXECUTED. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-s02` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-S02

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-S03

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-S03` |
| Kind | join |
| Producer | I03-LIVE-S03 |
| Subject | Journal → original creation/CID → attach → profile-specific per-command RUN |
| Increment | I03 |
| CTs (provisional mapping) | CT100 (provisional mapping) |
| Phase | P5 |
| Register origin | Cross-module joins — all planned, not shipped composition |
| Register status | PLANNED / UNEXECUTED |
| Local proof | composed join - see the component rows named in Subject |
| Expected live observation | Interactive mode: two commands, two durable operations, one cell/attach, preserved shell state. Noninteractive mode: two distinct null-session operations, two fresh one-shot cells/attaches, one RUN each; same-op duplicate/lost reply never allocates a replacement. Force the reply-publication/RUN-gate handoff schedule. Restart after creator-DONE/live-cell observes/stops the exact original CID without altering DONE or creating/starting/attaching/sending RUN again. No second history; E258/E260 local proofs are not deployed evidence. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-s03` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-S03

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-S04

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-S04` |
| Kind | join |
| Producer | I03-LIVE-S04 |
| Subject | Cancel/close-admission → drain → force-stop → kernel barrier |
| Increment | I03 |
| CTs (provisional mapping) | CT100, CT104 (provisional mapping) |
| Phase | P5 |
| Register origin | Cross-module joins — all planned, not shipped composition |
| Register status | PLANNED / UNEXECUTED |
| Local proof | composed join - see the component rows named in Subject |
| Expected live observation | Hold active file handler and queued RUN while stopping; prove scoped-effect close ordering, exact-view CANCEL and active one-shot CANCEL by journal-bound CID (same-namespace wrong-view op is denied before journal/Docker mutation); fork/double-fork/setsid writers stay fenced until owned cgroup populated=0. 204/409/404/STOP/worker exit are not release proof; unknown quarantines. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-s04` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-S04

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-S05

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-S05` |
| Kind | join |
| Producer | I03-LIVE-S05 |
| Subject | Registered root/writer → dirty R0 → view/rooted IO → pinned reader |
| Increment | I03 |
| CTs (provisional mapping) | CT101, CT102, CT103, CT103a (provisional mapping) |
| Phase | P4 |
| Register origin | Cross-module joins — all planned, not shipped composition |
| Register status | PLANNED / UNEXECUTED |
| Local proof | composed join - see the component rows named in Subject |
| Expected live observation | Two OS actors race alias/bind/nested registrations and writer generation; exactly one writer. Copy actual staged/unstaged/untracked/deleted bytes without canonical index changes; tools/PTY share writer view, independent pins survive newer generation. Purpose-correct views (E259) join this witness: verification/candidate pins stay immutable while mutation/provisioning project views keep rooted writes. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-s05` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-S05

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-S06

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-S06` |
| Kind | join |
| Producer | I03-LIVE-S06 (original join + explicit extension) |
| Subject | Actual view → seal/current/intent → projection/recovery; extended to cover the sealed-manifest/publish identity and kill-at-boundary recovery |
| Increment | I03 |
| CTs (provisional mapping) | CT104, CT105, CT106, CT107, CT107a (provisional mapping) |
| Phase | P5 |
| Register origin | E267 — nineteenth production surface: `execution/publication.py` (seal), PLANNED / UNEXECUTED |
| Register status | PLANNED / UNEXECUTED |
| Local proof | composed join - see the component rows named in Subject |
| Expected live observation | Original register oracle: Freeze after terminal barrier; inject death/fsync failure at every irreversible boundary. Complete old/new immutable revisions or quarantine, no committed rollback; protect Git index and user sentinels, safe no-replace new-project install. Extended register oracle: E267 covered only the seal half locally; E269 now also covers the publish half (CT106) locally, so the join has both components in-process. The live case must additionally prove that seal **cannot** run while any handler or cell is unsettled (E266's barrier plus this module's preconditions), that a `SEALED` manifest is the exact byte identity the fenced publication commits, and that a supervisor kill at each durable boundary recovers forward. None of that is observable without an approved Docker/cgroup host, so the row stays `PLANNED / UNEXECUTED`. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-s06` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-S06

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-S07

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-S07` |
| Kind | join |
| Producer | I03-LIVE-S07 |
| Subject | SessionManager/provisioner/tool builders/verifier → actual composed service |
| Increment | I03 |
| CTs (provisional mapping) | CT96, CT97, CT98, CT99, CT100, CT100a, CT101, CT102, CT103, CT103a, CT104, CT105, CT106, CT107, CT110, CT111, CT111a (provisional mapping) |
| Phase | P4, P6 |
| Register origin | Cross-module joins — all planned, not shipped composition |
| Register status | PLANNED / UNEXECUTED |
| Local proof | composed join - see the component rows named in Subject |
| Expected live observation | New/resume/new-session explicit reuse and real provisioning namespace before RPC; all execution/import/Git/readiness/search/PDF/mutation routes stay cell-local. Validate actual Compose/service wiring, remove controller workspace-source PYTHONPATH shadow, cut callers and mounts over atomically, keep daemon authority outside the model-facing controller, and prove unavailable dependencies have no host fallback. These callers/owners remain unimplemented. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-s07` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-S07

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### I03-LIVE-S08

| Field | Value |
| --- | --- |
| Case ID | `I03-LIVE-S08` |
| Kind | join |
| Producer | I03-LIVE-S08 |
| Subject | Outer chat/nested workflow → source handoff/eval → final release proof |
| Increment | I03 |
| CTs (provisional mapping) | CT96, CT108, CT109, CT109a (provisional mapping) |
| Phase | P6 |
| Register origin | Cross-module joins — all planned, not shipped composition |
| Register status | PLANNED / UNEXECUTED |
| Local proof | composed join - see the component rows named in Subject |
| Expected live observation | Real-provider CONTINUE_EXISTING and actual outer-chat delegated witness plus controlled bootstrap/failure/concurrency/isolation cases. For Q66, a bounded/redacted parent-only sentinel reaches the first actual planner provider request, is absent from retries/replans as specified, and credential/system-prompt sentinels are absent; no public `context` field. Preserve Q59 suggestion/manual behavior, Q56/Q73 negative/indeterminate outcomes and Q74 checkpoints. Freeze/review final fixtures before approval/deploy; final SLICE6 only. |
| Fixture / run sheet | fixture not assigned (SLICE6 STEP8, after STEP7 review); run sheet `#i03-live-s08` |
| Live result | NOT RUN |
| Commentary | |

#### Attempts - I03-LIVE-S08

| # | Date | Result | Run ID | Deployed SHA | Image digest | Profile | Config | Command | rc / effect | Evidence | Reviewer | Commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
