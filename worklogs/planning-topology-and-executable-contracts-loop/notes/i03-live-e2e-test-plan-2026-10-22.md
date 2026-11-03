# I03 live-host E2E test plan — how to build the suite, in dependency order

**Status:** PLAN ONLY. No case below has been executed, no row in
[e2e-live-verification-register.md](e2e-live-verification-register.md) is promoted, and nothing here
is evidence of live behaviour. This is the execution/evidence plan for the final **W4 live-only** wave;
case contracts, fixtures, driver and negative-control sensitivity must be authored, reviewed and dry-run
locally in W3 before deployment. W4 executes that frozen package only; it does not develop it on the host.
Dates this plan: 2026-10-22, after E265 (SLICE2 STEP4 part B-1), wave boundary clarified 2026-11-03.

**Current acceptance-scope ruling (2026-10-23):** final I03 acceptance requires live-host E2E for all
changes in I01–I03 of this project. The I03 inventory has 27 surfaces/8 joins; Q88 selected explicit
I01-origin IDs and the package now maps all 42 I01 CTs plus seven in-scope deferred obligations to
three planned I01 cases. All remain `NOT RUN`; this is not live evidence. The canonical package is
`worklogs/planning-topology-and-executable-contracts-loop/e2e/`.

**Purpose.** The register defines what the approved-host fixture must arrange and observe; it is not
permission to author tests during deployment. W0–W3 implement and validate the case contracts, markers,
fixtures, external driver, producer coverage and local negative controls on Arena in dependency order.
After those local W3 gates close, W3's approved `fa update` builds and starts the candidate image on the
user's host; this deployment/build is a prerequisite, not live acceptance. When W4 starts, the exact
suite and commands are frozen, reviewed, and locally dry-run. A host-side missing prerequisite is
BLOCKED, not an invitation to improvise test code against the deployed system.

**Non-negotiable framing (inherited rules).**
- Deployment is Linux/Docker/Ubuntu/Python only; no added Go runtime. Cases run against the actual
  approved image, never a `tmp_path` stand-in for `/sessions/<id>/`.
- A runner/collection/timeout/infra failure cannot be evidence either way (kill or survival). A case
  that cannot arrange its fixture is `BLOCKED`, not `PASS`.
- Unknown terminality leaves ownership quarantined and the case `UNEXECUTED`; no retry is allowed to
  manufacture a verdict.
- Every case must have a **negative control** proving the oracle can detect the producer. W3 must
  demonstrate sensitivity with a targeted local mutation/fault injection for each security/contract
  oracle. W4 must not disable code or mutate the deployed production service: if an actual host negative
  control requires a producer-disabled image, run only in an explicitly approved, labeled disposable
  test image/cell with disjoint state and cleanup assertions. "Green twice" is not a proof, and a
  negative control is never permission to damage or contaminate the user's production workspace.

---

## 1. Harness shape

Three layers, deliberately separate, because each fails differently:

| Layer | Location | Purpose | Runs in CI? |
| :--- | :--- | :--- | :--- |
| `tests/integration/conftest.py` | authored/unit-tested in W3; probes host only in W4 | fail-closed preflight + session-scoped fixtures (approved image, daemon, sessions root, evidence sink) | no |
| `tests/integration/live/test_*.py` | authored/reviewed/dry-run in W3; execute against approved host only in W4 | each case maps to exactly one register row or join | no |
| `scripts/e2e_live.py` | authored, contract-tested and dry-run in W3; invoked in W4 | external observer; captures evidence and writes immutable run manifest | no |

Rules that make the layer honest:

1. **Markers must be registered before the first case is written** (`pyproject.toml`
   `[tool.pytest.ini_options] markers`). The plan's verify fences already invoke
   `-m execution_host`; with `--strict-markers` on, an unregistered marker is a hard error, so
   registration is step 1, not a detail. Two markers: `execution_host` (needs Docker + approved
   image) and `live_e2e` (needs Docker + approved image + real provider credentials — the S08 cases).
2. **Skip is not pass, and a skip must say why.** The fixture skips at *collection* only when
   `FA_REQUIRE_EXECUTION_HOST` is unset; when it is set (`FA_REQUIRE_EXECUTION_HOST=1`), a missing
   daemon/image is a **failure**, not a skip. This is the single guard that stops a green-looking run
   on a host that never had Docker.
3. **Assertions read persisted evidence, never in-process objects.** For anything that claims "the
   deployed controller did X", the oracle is: the on-disk run artifact
   (`/srv/first-agent/state/session-log/<run_id>/…`), the Docker API response the driver captured, the
   kernel's own view (`/sys/fs/cgroup/…`), or a sentinel file written by a shim the image executed.
   In-process objects are acceptable only for `unit`-level cases that stay in `tests/`.
4. **One evidence directory per run**, `notes/evidence/i03-e2e/<run-id>/`, containing: image digest,
   wheel SHA, daemon version, kernel/cgroup facts, the pytest JUnit XML, the driver manifest, and any
   captured frames/sentinels. Evidence is append-only; a later run adds a directory, never rewrites.
5. **Cleanup is part of the oracle.** Every case ends with the same assertion: zero containers
   carrying the run label, zero live `fa-*` cgroup entries, zero supervisor processes. A case that
   leaks is a failure even if its own assertion passed — leaked cells are how ownership bugs hide.

---

## 2. Phase order (what becomes writable when)

Cases cannot be written before their subject exists; writing them early produces the near-miss
proxies the project already paid for once (E259: duplicated producers masking each other). Order:

| Phase | W3 preparation (local gates first; image deploy prerequisite last) | W4 live execution | Dependency / rows |
| :--- | :--- | :--- | :--- |
| **P0 harness** | implement markers, preflight, fixture contracts, external driver, evidence sink and cleanup checks; unit-test simulated host-present and `FA_REQUIRE_EXECUTION_HOST=1` missing-host refusal paths | verify the actual running host/image preflight before any case | none |
| **P1 images/entry** | build/test the installed wheel and entrypoint contract locally; freeze image build inputs and expected identity | verify the already-running approved image digest, isolated entry, profile rendering and PTY deadlines; do not rebuild | LIVE-01, 02, 05, 15, 16 |
| **P2 backend/cell** | test create/start/attach/RUN, one-shot+interactive semantics, cancel/force-stop and no-replay using local deterministic backends and mutation/fault controls | prove behavior against the approved Docker daemon, cgroups and real cells | LIVE-10, 11, 12, 13, 18 |
| **P3 authority/views** | test registration, R0, pinned readers, rooted IO and same-view read-your-writes against the real local authority/UDS | verify actual deployed filesystem, mount and kernel behavior | LIVE-03, 14, 17 |
| **P4 tools through the real port** | complete caller tests for E264/E265 on admitted views; local composition only, not stub-only | verify the same tool behavior in approved deployed cells | joins S02, S05, S07 |
| **P5 journal/recovery/seal** | run deterministic kill/fault-injection at each durable boundary, seal/drain and forward-recovery matrix locally | verify actual crash/restart, filesystem durability and containment under approved host conditions | LIVE-06, 07, 08, 09; joins S01, S03, S04, S06 |
| **P6 composed service** | implement and pass local SessionManager/provisioner/CLI and controller-attested HANDOFF composition; mock only provider I/O; validate controlled-provider case definitions | execute approved real-provider cases and deployed handoff/ledger observations | LIVE-04, LIVE-27; joins S07, S08 |

**W3→W4 boundary.** P0–P6 case code, fixtures, mutation-sensitivity checks, command vectors, and
evidence schemas are reviewed and dry-run locally before deployment. The cases remain blocked on their
product dependencies in W0–W2 until those callers exist; do not write success assertions against
recording fakes. After all Arena-local W0–W3 implementation, test, coverage and review gates pass,
W3 performs the separate approved `fa update` build/deploy prerequisite and verifies its SHA/digest/
config/health. W3 remains OPEN until that prerequisite succeeds; it does not run or close live cases.
W4 runs only the approved frozen package against that already-running image and does not update/rebuild. A missing Docker
host is simulated only in W3 dry-run tests; with `FA_REQUIRE_EXECUTION_HOST=1`, an actually missing
W4 host/image must fail before any row can be reported PASS.

---

## 3. Case template (write this, not prose)

Every case file carries, above the test:

```
Register row:   I03-LIVE-14 (+ join S05 if the case spans)
Contract:       CT101/CT103a (as cited by the row)
Arrange:        what the fixture must exist (image, view purpose, plan_ref, session id)
Act:            the one externally-triggered action
Observe:        the persisted artifact / kernel fact / sentinel that decides it
Negative control: the mutation of the product this oracle must catch
Cleanup:        the leak assertion
```

The negative control is what makes a case worth its cost. Its sensitivity proof belongs in W3 and
must disable the actual producer/caller through a targeted source mutation or fault injection; a test
that only calls a helper or toggles an unrelated mock is invalid. In W4, test the unchanged approved
artifact positively. If a host-side negative variant is itself required by a case, build/use an
operator-approved disposable test image and isolated labelled state; never patch or mutate the live
production service or user workspace.

---

## 4. Cases this session's work adds (E264/E265), and how to verify them live

These are new obligations created by SLICE2 STEP4 part A/B. Unit proof exists; live proof needs the
admitted view, so all belong to P4.

| Case | Arrange | Observe | Negative control |
| :--- | :--- | :--- | :--- |
| **L-TOOL-1** write/read/edit through the port | admitted PROJECT view, real authority, controller process | bytes land in the view (`authority.read_file` agrees, host canonical untouched), denial for an unadmitted path leaves no file | remove the port injection → the tool writes the host path, which the case must catch by watching the canonical tree |
| **L-TOOL-2** stale-base edit | two controller principals on one view | second write returns the conflict result, concurrent bytes preserved | disable the digest check → lost update, case fails on content |
| **L-TOOL-3** PDF/binary/oversize are named refusals | view with a PDF, a NUL-containing blob, and a >1 MiB text file | three distinct, deterministic tool results; the canonical/host file is *never opened* (see trace below) | restore the host-path read → the trace shows an `open` outside the view |
| **L-TOOL-4** artifacts keep the controller path | an artifact minted by a real run, then an `artifact_id` read inside the view | content matches the stored artifact; no view IO for it | route artifacts through the port → refusal, case fails |
| **L-TOOL-5** memory-per-call search/reach (Q105; E374), PLANNED | admitted view, both tools twice; distinct pinned reader over earlier revision; monitor cell file opens and writes | each result reflects its own view; indexes are per-call in memory; no index DB or sidecars in view **or writable scratch**, no host fallback; view digest unchanged by searches | redirect index to view or scratch disk / host, or bind reader to writer view → independent trace, digest or revision oracle fails |
| **L-TOOL-6** zero host-Git reads | controller process with `git` replaced by a shim that appends to a sentinel and exits 127 | sentinel is empty after a full tool sweep; the JSON tool inventory contains no `fs_checkpoint`/`fs_undo`/`fs_diff` | re-enable the pair tools → sentinel non-empty |
| **L-TOOL-7** tools and PTY see each other | one view, a PTY inside the cell, a tool write | PTY output shows the tool's write and vice versa, with blackboard on and off; a *reader* view is unaffected | drop the shared view → the PTY sees stale bytes |
| **L-TOOL-8** large search/reach result, PLANNED | real admitted views, 195 248-byte reach fixture from E374, outline fixtures, authorised WRITE and READ; separate legacy reference | complete exact ToolResult and attribution without hidden truncation; wrong view/principal denied; collect actual worker/supervisor/controller RSS, CPU and elapsed time under defined concurrency and deadline | truncate/drop/reorder/duplicate output or read wrong view → exact bytes/hash, count and provenance oracle fails |
| **L-TOOL-9** interrupted result and Q75, PLANNED | actual cell and UDS; same request ID/input/proof, slow or disconnected reader; durable old v1 DONE plus new helper execution | observe bounded buffers, deadline and terminality; exact protected-memory replay only for same binding; cache loss/restart fails closed without re-execution or result reconstruction; Bash v1 and old DONE unchanged | replay with mismatched principal/input/proof, rebuild result after cache loss, issue second helper or forge terminality → binding, execution-count and journal oracle fails |
| **L-TOOL-10** memory-index lifetime, PLANNED | repeated real search/reach EXECs on one admitted view; instrument actual helper/cell lifecycle and cgroup memory | results correct on every call; no index DB/sidecars, no live helper descendants after terminal barrier; approved persistent cell is accounted separately; record peak and post-call resources, distinguish process-exit cleanup from same-process cleanup | retain helper descendant after terminal barrier or place DB on disk → lifecycle or filesystem oracle fails; missing host or unproven terminality is BLOCKED |


**Tracing "never opened the host file" / "never ran git".** Two cheap, external mechanisms; use both,
because each misses a case:
1. **Shim on `PATH`** for `git` (and any host helper) writing `argv`+`cwd` to a sentinel file. Catches
   every `execve` the controller spawns through `PATH`; deterministic, no privileges.
2. **`strace -f -e trace=execve,openat -o trace.txt --` around the controller** in the driver, filtered
   to paths outside the view and the approved roots. Catches absolute-path execution the shim cannot,
   and file opens. Requires `CAP_SYS_PTRACE` on the host — record its absence as `BLOCKED`, never as
   `PASS`.

---

## 4.1. Cases E277–E279 add: the composed service, the barrier and the receipt ledger

E277 gave the service its nineteen routes and one socket owner, E278 the `CellTermination` join, E279 the
receipt issuer. None of it has met a daemon. These cases are P3/P4 work and may not be attempted before the
image, the socket and the `cgroup` mount are arranged (§1), and like every case above each one needs its
negative control in the same file.

The journal is the durable ledger of this system: one append-only record per operation id, `complete` is the
only writer of a result, and the record — not the reply — is what survives a kill. So the receipt cases assert
on the **on-host journal files** as well as on the wire reply, and every case names the record it expects.

| Case | Arrange | Observe (wire **and** ledger) | Negative control |
| :--- | :--- | :--- | :--- |
| **L-RCPT-1** `exec` receipt is true of the host | admitted PROJECT view, real image, real `docker` socket, real `/sys/fs/cgroup` mount; one `printf` and one `false` | `EXITED` with the container's own exit code for both; `terminal_barrier: true` only alongside `cgroup.events` reading `populated 0` for that CID; `duration_ms > 0`; tails ≤ 64 KiB; identity fields equal the view record's tree/plan and the approved profile's digest | point `cgroup_root` at a directory whose `cgroup.events` says `populated 1` → the case must see a refusal (`EXECUTION_UNKNOWN`), never `EXITED` |
| **L-RCPT-2** `inspect` replays, the ledger does not rewrite | a completed `exec` (L-RCPT-1), then `inspect` twice | both replies are byte-identical to the stored receipt; the **EXEC** record file's hash is unchanged; the two INSPECT operations each appended exactly one record ending `DONE`; the daemon log shows no `GET /containers/<cid>/json` between the two inspects | delete the container between the two inspects → the replay still answers, which is what proves no daemon contact |
| **L-RCPT-3** `cancel` before create / during create / during RUN | the three S04 timings, real SIGKILL, daemon access log on | receipt is `CANCELLED` under `op-<cancel request_id>`, never `EXITED`; `exit_code` only when an `exited` was observed; the target record shows `cancel_requested: true` **in the snapshot the driver takes when the kill request arrives**; `populated 0` read after the stop returns | move the intent write after the kill (test build) → the snapshot at kill time shows `cancel_requested: false`, which the case must catch |
| **L-RCPT-4** a spent budget is final | a command that outlives its `timeout_ms` | `TIMED_OUT`, `exit_code: null`, `terminal_barrier: false`; **zero** post-reply `GET /containers/<cid>/json` in the daemon log; the ledger record ends `DONE` with exactly that receipt | re-enable the post-command observation (test build) → one extra GET appears, which fails the case |
| **L-RCPT-5** one-shot vs interactive | the same command under a one-shot profile and an interactive one | one-shot requires `populated 0`; interactive returns `EXITED` with `terminal_barrier: false` while the shell lives, and `stop_view` then reports `terminal: true` with the same CID's cgroup empty | create the interactive view *after* the command → the case must fail to arrange (BLOCKED), never PASS on a later cgroup read |
| **L-RCPT-6** ledger append survives a kill | `kill -9` the supervisor after the command reply but before `complete`; restart | exactly one record per operation id after restart (no duplicates, no second RUN in the daemon log); `inspect` answers `UNKNOWN` or the stored receipt, never a fresh `EXITED` with a new exit code | kill *after* `complete` → `inspect` must replay the stored receipt; if both timings look the same, the case is not observing the boundary and must be rewritten |

`pty_control` (E280) adds the control plane. Its cases are small but each one has a failure mode that only a
live shell shows, and two of them are ledger-append cases: INTERRUPT/CLOSE are mutating operations and must
append exactly one record, while LIST is read-only and must append none.

| Case | Arrange | Observe (wire **and** ledger) | Negative control |
| :--- | :--- | :--- | :--- |
| **L-PTY-1** LIST sees only this view's sessions | two live views with different session names, one real command each | each view's `LIST` returns exactly its own session names; the session named `main` in one view is not visible from the other; the ledger gains **no** record for either LIST | reuse one view's session name from the other view's episode (test build) → the case must fail to arrange, never PASS on a shared answer |
| **L-PTY-2** INTERRUPT is an ACK, not terminality | a live interactive session with exported state | a real Ctrl-C reaches the pane; the reply carries `{sessions, message}`; a following command still runs in the **same** container id with its environment intact; `cgroup.events` for that CID is still `populated > 0`; the ledger has one DONE record for the interrupt | close the session first (test build) → the interrupt must be refused (`EXECUTION_UNKNOWN`), and the shell must still answer `LIST` |
| **L-PTY-3** an unknown session never costs the shell | one live shell, an INTERRUPT for a name that was never created | the supervisor refuses `EXECUTION_UNKNOWN`; the daemon log shows **no** attach write for that request; the very next command still succeeds in the same cell; the ledger record for that interrupt ends `UNKNOWN`, never `DONE` | let the raw frame reach the worker (test build) → the cell's attach dies and the following command must fail, which is exactly what the case forbids in production |

Two of these cases (`L-RCPT-2`, `L-RCPT-6`) are the ledger-append cases the session's instruction asked for:
they assert that the journal gains exactly one record per operation, that a completed command's record is never
rewritten, and that the replay is served from the record rather than from the daemon.

`handoff` (Q85 ruling, E282/CT113) adds one case, and it is the only case in this suite whose arrange step
needs two real runs. It is P6 work: it cannot be written before SLICE2 STEP6 exists and the controller cutover
(SLICE4 STEP2) gives the handler a client, because the "child run" it names must come from an actual
`SessionManager.begin_run`, not from a hand-made namespace.

| Case | Arrange | Observe (wire **and** ledger) | Negative control |
| :--- | :--- | :--- | :--- |
| **L-HAND-1** the grant moves, the epoch does not | one registered workspace with a live owner grant, one child run allocated by a real `begin_run` in the same session (`parent_run_id` = the owner's run), a pinned READ view at R0 | the reply is `{view_ref:null, capability, generation, revision_id}` with **the same `generation`** and the same `revision_id` as before the call; the child immediately opens a WRITE view whose `view_ref.generation` is that same generation and writes successfully; the pinned reader still answers R0; `workspace.json` differs from the pre-call copy **only** in `active_actor` and the grant (byte compare, not a field list); exactly one `operations/op-<request_id>.json` ends `DONE` and contains no capability; the daemon log shows no new attach and `docker ps` no new container | call `handoff` again with the same `request_id` and the *old* capability → the identical cached reply (the new capability) must come back, while a **new** `request_id` with the old capability must be `UNAUTHORIZED`; then a second `handoff` from the child to its own `begin_run` child must succeed, proving the chain rather than a one-shot move |
| **L-HAND-2** nothing unsettled may move | the same arrangement, three times: a view `SEALED` but not published; a view still `OPEN` with a live cell; a workspace with a surviving `intent.json` from an interrupted publication | each call refuses `WORKSPACE_BUSY` and leaves `workspace.json` byte-identical; after publishing the sealed view (or stopping the open one) the same call succeeds, which is what proves the refusal was the settlement predicate and not an unrelated error | swap `_settle_owner`'s predicate for `_forward_gates` (test build) → the sealed-view case changes code path *and* the open-view case starts probing the canonical tree; the case asserts the refused codes and the untouched metadata, so either substitution shows up |


---

## 4.2. Q112/R02 entrypoint readiness and session-ledger append (PROPOSAL; not an I03-LIVE result)

This proposal covers the selected `auto_run_only` contract and Q118's narrow provisional-run allowance for
`scripts/fa-entrypoint.sh`. It does not create or renumber a frozen `I03-LIVE-*` row and must not run until the
approved implementation is merged to `main` and deployed through the user's `fa update` workflow. Readiness
failure must be injected inside the managed EXEC cell; host bootstrap/readiness is not a substitute. The tests
require an approved host, image, state root, and a controlled failure; Docker and live-host evidence remain absent.

**Ledger authority.** Observe the on-host `<FA_STATE_ROOT>/sessions/<session_id>/session.db` directly, read-only.
`SessionManager.begin_run` claims `run_binding:<run_id>` in `session_meta`; `SessionDatabase.event_log` is the
authoritative event ledger. `events.jsonl` is a compatibility mirror and is not the append-count oracle. Record
pre-run DB row/key snapshots, post-run snapshots, returned process status, `run_id`, and hashes in the evidence
directory; reopen the DB before comparing so the test proves durable state rather than a process-local view.

| Case | Arrange / act | Observe (host status, files, and ledger) | Negative control |
| :--- | :--- | :--- | :--- |
| **L-ENTRY-1** managed cell-readiness failure refuses auto-run | Fresh session ID, `FA_AUTO_RUN=1`, no command override; admit the managed new-root provisioning run, then force cell-local readiness to fail; invoke the installed entrypoint | Structured status is `FAILED`; independent host trace shows no host project clone/checkout/configure/readiness command and no `fa run`; no new `.active` publication; a provisional manifest/DB and exactly one run reservation may exist, with the failed run ID durably non-reusable; no workflow `event_log` append. Cleanup may remove only unregistered session-owned state and must not delete supervisor-registered bytes | Rebuilt test image with the refusal branch disabled must expose `fa run` or a forbidden host-side project command; independently verify the tombstone cannot be reserved again. If either observer cannot see its mutant, the oracle is invalid |
| **L-ENTRY-2** resumed workspace survives cell-readiness refusal | Pre-existing active session/workspace with a user sentinel, DB and one prior run binding; managed cell-local readiness fails during auto-run | Refusal is recorded; workspace/sentinel and existing active pointer remain unchanged; no `fa run` or workflow event append. At most one new provisioning reservation may be added and must remain a non-reusable tombstone; all prior bindings/events remain unchanged | A test build that removes the refusal gate must expose `fa run`; independently attempt reservation reuse and require rejection. A resumed DB delta is valid only for the reserved tombstone |
| **L-ENTRY-3** explicit override remains diagnostic-only | Fresh managed clone, readiness failure, `FA_AUTO_RUN=1`, explicit harmless command override | Override `execve`, exit, and output are observed; trace has no `SessionManager provision` or `fa run`; no new manifest/session DB, run binding, or event append. The existing shell behavior may publish `.active`; do not use its presence as proof of a logical run | Rebuilt test image that removes the no-override provision guard must expose `SessionManager provision` in the process trace or leave a durable provision side effect; the test must fail even if the explicit command itself exits zero |
| **L-ENTRY-4** successful managed auto-run appends once | Valid readiness; one fresh ID; a deterministic approved provider/profile that completes a minimal task; invoke managed auto-run once | Trace shows exactly one `SessionManager provision` and one `fa run`; exactly one session manifest/DB and one new `run_binding:<run_id>`; `event_log` has a nonempty set of rows for that run, unique `event_id`s, all bound to the expected session/run; rows survive process exit/reopen; a second read/replay observation adds no rows and does not start another run | Disable/replace the production append/binding edge in a test build; the independent SQL snapshot must miss the expected binding/event rows and fail. Do not mutate the approved deployment |
| **L-ENTRY-5** unavailable managed backend prevents host project effects | Fresh and resumed managed auto-run cases, `FA_AUTO_RUN=1`, no command override; test absent execution config and, separately, valid config with an unavailable supervisor before entrypoint start | Structured failure; independent process trace shows no host project clone/checkout/configure/readiness command and no `fa run` or new `.active` publication. With absent config, fail before lifecycle state. If the configured-but-unavailable case has already reserved a run, allow only a provisional non-active manifest/DB plus one durable non-reusable tombstone; no workflow `event_log` append. Resumed workspace/manifest/prior DB rows remain unchanged apart from that reservation. Never delete supervisor-registered bytes | Rebuilt test image with the backend gate/injection removed must expose the first forbidden host project command or `fa run`; independently verify tombstone non-reuse. If the observer cannot distinguish host commands from managed EXEC or cannot see the mutant, mark BLOCKED, not PASS |
| **L-ENTRY-6** prewarmed immutable environment is immediately usable | Fresh self-repo session and resumed prepared session with a functioning managed EXEC backend. Self-repo uses an exact lock/runtime/profile/image artifact; empty clean seed uses the separate operator-prewarmed First-Agent baseline artifact; if the created root has its own `pyproject.toml`/`uv.lock`, require an exact-match artifact instead. | In the same admitted provisioning run, managed readiness reports `status=ready`, `reason_code=ready_managed_artifact`, `repaired=false`; `pytest --version && mutmut --version` succeeds inside its PROVISIONING view; artifact manifest/fingerprint and cache bytes remain unchanged. There is no per-session environment build, `uv sync`, host `.venv` fallback, or provider/LLM call before readiness. Preserve the accepted one-second immediate-tool target as a separately timed command observation. | Remove/mismatch the selected artifact in a rebuilt test image: readiness must fail closed as `managed_artifact_probe_failed` (with only Q118-bounded provisional state after admission), without a session build or host fallback; the mutation must miss the ready/tool oracle. If traces cannot distinguish artifact reuse from a build or identify provider calls, mark BLOCKED, not PASS |

**Execution/evidence rules.** Run the refusal and override cases with both fresh and resumed state as applicable; preserve the existing state root for forensic inspection until after snapshots are captured. Record image digest, deployed SHA, Python version, `FA_STATE_ROOT`, environment with secrets redacted, selected artifact fingerprint and source class (exact root lock or approved clean baseline), readiness cause/reason (`ready_managed_artifact` or `managed_artifact_probe_failed`), readiness and `pytest`/`mutmut` command wall times, command/exit, `session_id`, `run_id` (when allocated), pre/post SQL snapshots, workspace/artifact hashes, and cleanup observations. Capture independent `execve` evidence with `strace -f -e trace=execve` or an equivalent approved host observer; shell log text alone is not proof that a command was or was not launched. If the host denies the required observation privilege, mark the affected case `BLOCKED`, never `PASS`. The runner must fail if it cannot query the authoritative DB; on refusal, either absent session state (config-missing preflight) or the Q118-bounded provisional manifest/DB and tombstone is valid, but never a new active publication or workflow event. A missing DB on L-ENTRY-4 is a failed arrange, not a pass. Do not retry a case to manufacture a verdict. Append only actual attempts to the appropriate live register after planner approval of row ownership; this proposal alone assigns no row and proves nothing about host behavior.

## 5. Sequences worth spelling out (the ones a naive case gets wrong)

1. **Pinned reader vs active writer (S05/L-TOOL-5).** Order matters: create the reader view *while*
   the writer's second revision is in flight, then assert the reader answers revision R0 bytes even
   after the writer commits R1. Creating the reader afterwards proves nothing.
2. **Cancel before create / during create / during RUN (S04).** Three separate cases with distinct
   expected journal states (`not_created`, `create_uncertain`, `stopped`). The kernel barrier assertion
   is `/sys/fs/cgroup/<path>/cgroup.events` showing `populated 0`, read *after* the stop returns —
   never the API's 204.
3. **Supervisor death at a durable boundary (S06).** Kill `-9` between `fsync` and pointer replace;
   restart; the only acceptable outcomes are the complete old revision, the complete new revision, or
   quarantine. Any partial projection is a failure of the case, not a flake.
4. **Readiness gating (S07, after cutover).** With a provisioner injected, a workspace whose readiness
   can be forced degraded must produce `workspace_not_ready` and **no** active manifest, no run
   binding, no workspace bytes. Force degradation through the real environment (a broken prewarm
   input), not by stubbing the classifier.

---

## 6. Cost, flakiness and evidence policy

- Budget: P1 ≈ 10 min for W4 verification of the running image (image construction/start is the W3
  `fa update` deployment prerequisite, not W4 work), P2 ≈ 15 min, P3 ≈ 10 min, P4 ≈ 10 min,
  P5 ≈ 20 min (kill/restart cycles), P6 ≈ 20 min with a real provider. Per-case timeout 120 s except the kill matrix (300 s) and provider cases (600 s).
- **No retries for evidence.** A flaky case is a defect in the case or the product; re-running until
  green converts an unknown into a false PASS.
- A case that fails to *arrange* is reported `BLOCKED` with the arranging command and its actual
  output; the run continues so one blocked case cannot hide the rest.
- Results are appended to the register row (`Actual live evidence` column or a dated subsection) with
  the evidence directory and the image digest — never edited in place.

---

## 7. What this plan deliberately does not do

- It does not promote any row, invent a verdict, or claim that unit proof transfers to the host.
- It does not authorize the W3 host build/deploy prerequisite until all Arena-local W0–W3 gates,
  tests, sensitivity checks, independent review and runbook preparation close. That approved build/deploy
  is not live I03 acceptance; W4 is the only live-test/evidence wave.
- It does not add a second harness: use `pytest`, the registered markers and this in-repo external
  driver. The complete harness/fixture/test package must be reviewable and dry-run locally before W3's
  image build/deploy step.

## 8. W3 image-build/deploy prerequisite (frozen runbook requirement)

After all Arena-local W0–W3 gates and independent review pass, W3's deployment run sheet invokes this
approved build/deploy command on the user's Linux/Docker host:

```sh
AUTO_STASH=0 SKIP_TESTS=1 SKIP_UV_SYNC=1 PRUNE=0 fa update
```

Before invocation, record the approved candidate SHA, freshly fetch and confirm `origin/main` equals it,
keep `main` frozen through the update (the updater has no pinned-SHA input), verify a clean host checkout,
and obtain maintenance approval. This is grounded in `scripts/fa-update.sh`: `git_update()` refuses dirty
state unless auto-stash is enabled (466–480), then fetches and fast-forwards `origin/main` (483–495).
On a changed candidate, `evaluate_changes()` marks the build required and `build_and_deploy()` runs
`docker compose build` then `docker compose up` (557–561, 672–694); it waits for health and runs container
smoke checks. This host-side image build/start is intentionally the W3 deployment prerequisite, not an
accidental W4 test/build. `PRUNE=0` retains the previous image/config for reviewed rollback (986–990).

`SKIP_TESTS=1` returns from updater step 7 before its fixed `/sessions/deploy-smoke-test` deletion
(875–877), host `uv sync` (879–897), and repository-wide host pytest (909–920). It skips only that
updater-owned test block; it does **not** skip the separate W4 suite. Record step 7 as `SKIPPED`: the
script initializes `TEST_RC=0` before returning (861–865), so its printed `Tests: rc=0` is not test-PASS
evidence. The environment assignments apply to this `fa update` process only. Updater health/import
smoke checks are deployment readiness evidence, not live I03 PASS evidence.

W3 closes this deployment prerequisite only if the update/build exits 0 and independent checks show the
approved source SHA, running image digest and config/profile match the candidate, and the agent
container reports Docker health `healthy` (not `no-healthcheck`). Require the in-container `fa --version` and core-import smoke checks to visibly pass; `fa-update.sh` reports these as
warnings rather than failing its own exit, so exit 0 alone is insufficient. Record proxy/selfcheck
warnings, but do not infer a working REAL-provider path from them; W4 must prove that path. If build,
health, required smoke or identity fails, stop: W3 remains OPEN and W4 must not start. A nonzero update
does not prove that deployment did not occur; capture printed HEAD/health/test status and use the reviewed
recovery procedure—no blind retry. W3 runs no live producer cases and records no live PASS.

W4 begins only after the candidate image is already running and identified. Do not invoke `fa update`
or rebuild in W4. Run the frozen W3-reviewed suite against the running image/managed cells: product
operations and workloads execute there; the approved external driver is a bounded TCB observer that
collects host Docker/kernel/cgroup/process/DB/event-ledger evidence. Do not run repository-wide/default
project pytest or unreviewed project conftest on the controller. The only approved host test code is the
explicitly approved, frozen `tests/integration` package and external driver, excluded from default
collection; no fixture authoring or production mutation is permitted on host. Docker/host live testing
is W4-only.
