> **Status:** archived 2026-08-25 — moved per b_full, verification reports exist (S1-S4) / code-proven IMPLEMENTED (S14b)

# PLAN: S1 — Session Lifecycle, Session Authority, and Run Binding

Plan-ID: `PLAN-cli-trace-S1-session-lifecycle`

Status: **READY FOR DESIGN/VERIFICATION EXECUTION** — design/verification
execution completed with a PASS report; runtime implementation remains a later
approved slice.

Execution report: `worklogs/implementation-plans/cli-trace-S1-verification-report.md`

Parent plan:

- `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`

Revision: v2 — S1 design/verification executed. Option A, Q10-A, clean
cutover, and the artifact-only boundary are recorded in the verification
report. Runtime implementation is still deferred to the next approved subplan.

## 0. Scope and execution boundary

### In scope

This subplan freezes the contract needed to implement:

```text
session_id
  persistent user session, workspace, Blackboard, and session authority DB

run_id
  one `fa run` or `fa workflow` invocation inside a session

event_id
  one event produced by one run

--session-id
  explicit attachment to an existing persistent session
```

It also defines the clean-format read policy:

```text
new format:
  DB-backed `fa stats`

old JSONL/old per-run DB artifacts:
  untouched and reported as unsupported/legacy

automatic migration:
  none in the first implementation
```

### Explicit non-goals

- No edits to `src/fa/`.
- No edits to `tests/`.
- No implementation of `--session-id` in this subplan.
- No implementation of `SessionManager` in this subplan.
- No SQLite schema migration in this subplan.
- No automatic migration of existing per-run DBs or JSONL.
- No `fa inspect` command.
- No host-wrapper change.
- No subagent implementation; Q11-B is a later subagent slice.
- No production deployment.

### Stop rule

If the source/entrypoint trace reveals a policy choice not covered by this
subplan, stop. Add a new blocking `Q#` to this subplan and the parent plan.
Do not silently choose a lifecycle, migration, path, or ownership policy.

## 1. Before editing: source-verified current behavior

### 1.1 Baseline authority

The baseline for this subplan is commit:

```text
3668e758c1522645a1bfb70787ebf53f7ef170a7
```

The uncommitted candidate runtime patch is not the implementation baseline. It
is preserved outside the repository and must not be applied by S1.

### 1.2 Container workspace behavior

Source: `scripts/fa-entrypoint.sh:146-182`.

Current behavior:

```text
if /repo/.git exists and FA_WORKSPACE is unset:
  SESSION_ID = FA_RUN_ID or generated session-<timestamp>-<pid>
  SESSION_DIR = /sessions/<SESSION_ID>
  clone /repo into SESSION_DIR if needed
  checkout branch agent/<SESSION_ID>
  publish /sessions/.active
  set local WORKSPACE=SESSION_DIR
```

The current entrypoint therefore conflates two identities:

```text
SESSION_ID ← FA_RUN_ID
FA_RUN_ID   ← SESSION_ID
```

This is incompatible with the accepted target where one persistent session can
contain multiple independent runs, each with a new `run_id`.

After workspace setup, command-override mode executes the supplied command at
`scripts/fa-entrypoint.sh:203-206`. The subplan must verify whether direct
`docker compose exec first-agent ...` receives the workspace/session context
created by the original entrypoint process. Do not assume that a shell-local
`WORKSPACE` variable survives a later `docker compose exec` process.

### 1.3 Current `fa run` parser behavior

Source: `src/fa/cli.py:344-429` in the baseline.

`fa run` currently accepts:

- positional task / `--task`;
- `--role`;
- `--config`;
- `--workspace`;
- `--max-turns`;
- `--run-id`;
- `--resume`;
- `--output-mode`;
- `--detail`;
- `--no-color`.

There is no `--session-id` argument in the baseline parser.

### 1.4 Current `fa workflow` parser behavior

Source: `src/fa/cli.py:431-508` in the baseline.

`fa workflow` currently accepts:

- role list;
- task;
- `--workspace`;
- `--run-id`;
- `--config`;
- `--max-turns`;
- `--mode`;
- `--max-repairs`;
- `--max-replans`;
- per-role task overrides.

There is no `--session-id` argument in the baseline parser.

### 1.5 Current run trace behavior

Source: `src/fa/cli.py` `_cmd_run()` and `src/fa/inner_loop/state.py`.

Current baseline behavior:

```text
run_id = args.run_id or run-<process-pid>

trace root:
  Path.home() / ".fa" / "session-log" / run_id

events mirror:
  <trace root>/events.jsonl

EventLog authority attempt:
  <trace root>/session.db
```

The baseline `EventLog.__init__` calls `_initial_next_id(path)` before
constructing `SessionDatabase`. This is the F-01 ordering defect already
reproduced in the parent plan. The candidate patch changes this behavior but is
not approved by S1.

### 1.6 Current SessionState/Blackboard behavior

Source: `src/fa/inner_loop/state.py:305-378` in the current working tree and
corresponding baseline symbols.

The intended production path is:

```text
SessionState(log=EventLog(...))
  → session_db = log.session_db when session_db was not supplied
  → Blackboard(workspace/.fa/blackboard, session_db=session_db, run_id=run_id)
```

Blackboard's JSONL mirror is rooted under the workspace, while its injected
SQLite authority is taken from the EventLog DB in the current production path.
Blackboard also exposes a standalone constructor that creates its own DB when
no `session_db` is supplied.

The current state object does not carry a first-class `session_id` field and
does not reject an explicitly supplied `session_db` that differs from
`log.session_db`.

### 1.7 Current stats/read behavior

Source: `src/fa/stats.py:250-265`.

Current `parse_session(events_path)` constructs `EventLog(events_path)` and
calls `read_all()`. This can create a DB while reading a legacy JSONL directory
and can reach the hidden JSONL fallback in `EventLog.read_all()`.

Target direction accepted by the operator:

```text
current format:
  DB-only reader

legacy format:
  no automatic migration or hidden fallback in the first implementation
```

The exact unsupported/legacy diagnostic is part of this subplan.

## 2. Contracts and gap IDs addressed

### Parent-plan contracts

- `CT1` — CLI dispatch and command-root contract.
- `CT2` — session authority and run-scoped trace contract.
- `CT4` — Blackboard conflict and session ownership contract.
- `CT6` — workflow controller/artifact contract.
- `CT8` — deployment topology contract.
- `CT9` — event identity and run-binding contract.
- `CT10` — authority failure-policy contract.

### Parent-plan gaps

S1 addresses the lifecycle/design parts of:

- `V3` / `V4` / `V5` — hidden JSONL fallback and DB creation during reads;
- `V7` — missing run/session binding;
- `V16` — mismatched `SessionState.session_db` and `log.session_db`;
- `V26` — entrypoint conflates `FA_RUN_ID` with persistent session identity.

S1 records, but does not implement, the dependencies for:

- `V1` — database-serialized event identity;
- `V6` — Blackboard duplicate-ID semantics;
- `V8` — initialization failure policy;
- `V9` — workflow projection accuracy;
- `V13` — failed clone state;
- `V24`/`V25` — artifact-only subagent boundary.

### Accepted decisions used by S1

- Direct-container `fa run` is the first production acceptance root.
- `session_id` is the persistent workspace/session identity.
- Default `fa run` and `fa workflow` create a new session.
- Explicit `--session-id` attaches to an existing session.
- Every invocation receives a new `run_id`.
- Option A is the selected physical direction:
  one DB per persistent session, session-scoped Blackboard/meta, run-scoped
  event rows filtered by `run_id`.
- Clean cutover is selected: no first-slice legacy reader and no automatic
  migration.
- Artifact-only subagent is the first subagent mode; its detailed enforcement
  is out of S1.

## 3. Exact files and artifacts allowed to change

### Files allowed in S1

S1 is a design/verification slice. The executor may create or update only:

1. `worklogs/implementation-plans/PLAN-cli-trace-S1-session-lifecycle.md`
2. `worklogs/implementation-plans/cli-trace-S1-verification-report.md`
3. `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`
   — only after the subplan's evidence and decisions are complete.
4. `worklogs/HANDOFF.md` — only at S1 close, to record evidence and the next
   approved subplan.

### Files explicitly forbidden in S1

- Any file under `src/fa/`.
- Any file under `tests/`.
- `docker-compose.fa.yml`.
- `Dockerfile.fa`.
- `scripts/fa-entrypoint.sh`.
- `scripts/fa`.
- Any runtime configuration or database file.

If an executor believes one of the forbidden files must change, it must stop,
add a blocking question, and wait for a revised approved subplan.

## 4. S1 design decisions to freeze

### S1-D1 — Session identity

Freeze:

- accepted identifier syntax and maximum length;
- generation method for a new `session_id`;
- whether an explicit ID must already exist;
- whether session IDs are case-sensitive;
- how invalid/path-like IDs fail.

Default proposal:

```text
session_id:
  [A-Za-z0-9_.-]{1,128}

new session:
  generated cryptographically-random or collision-resistant ID

explicit --session-id:
  must resolve to an existing validated session
```

Do not silently treat an unknown explicit session ID as a new session.

### S1-D2 — Run identity

**Decision:** every `fa run` and `fa workflow` invocation gets a new `run_id`.

```text
new invocation:
  generate a new run_id

session continuation:
  --session-id <existing>
  + generate a new run_id

explicit --run-id:
  allowed only for a new, unclaimed run identity
  existing run_id → exit 2

--resume:
  deprecated session-continuation compatibility behavior
  requires --session-id in the new format
  creates a new run_id
  never appends a new invocation into an old run trace
```

Workflow stages attach through `session_id` and receive their own run identity.
They must not reuse a prior stage's run ID.

### S1-D3 — Session authority path

**Decision:** select Candidate A — a separate session namespace.

```text
/home/fa/.fa/sessions/<session-id>/manifest.json
/home/fa/.fa/sessions/<session-id>/session.db

/home/fa/.fa/session-log/<run-id>/events.jsonl
/home/fa/.fa/session-log/<run-id>/llm_bodies.jsonl
/home/fa/.fa/session-log/<run-id>/flow_state.json
/home/fa/.fa/session-log/<run-id>/eval_report.json
```

Reason for rejecting Candidate B for the first format:

```text
/home/fa/.fa/session-log/<session-id>/...
/home/fa/.fa/session-log/<run-id>/...
```

would put two identity namespaces under one directory and make accidental
session/run path collisions harder to detect. Candidate A keeps the persistent
session authority and per-run trace artifacts visibly separate.

The manifest is not the authority for event/Blackboard data. It is an
identity/path registry pointing to the session authority DB and workspace.

### S1-D4 — Manifest schema

Freeze the minimum manifest fields:

```json
{
  "schema_version": "v1",
  "session_id": "session-A",
  "workspace_path": "/sessions/session-A",
  "session_db_path": "/home/fa/.fa/sessions/session-A/session.db",
  "created_at": "2026-01-01T00:00:00Z",
  "last_used_at": "2026-01-01T00:00:00Z",
  "status": "active"
}
```

Required checks:

- manifest `session_id` equals the requested ID;
- `workspace_path` is under the allowed `/sessions` root or the explicitly
  approved workspace root;
- `session_db_path` is under the approved FA state root;
- paths are resolved before use;
- missing/corrupt/foreign manifest fails closed;
- updates use atomic temp-file plus rename;
- manifest does not contain provider keys, proxy tokens, or raw prompts.

### S1-D5 — Workspace ownership

Freeze how CLI-owned `SessionManager` interacts with the existing entrypoint:

```text
new session:
  who creates /sessions/<session-id> from /repo?

existing session:
  who validates and selects /sessions/<session-id>?

explicit --workspace:
  allowed only for controlled deployment/testing,
  or allowed as a session creation input?
```

**Decision:** `SessionManager` is the canonical logical owner of session
identity, manifest, session DB resolution, workspace validation, and run binding.

The existing entrypoint must become an adapter/bootstrap boundary, not a second
logical session owner. Its clone behavior may be reused through a shared helper,
but the resulting workspace must be registered and validated by
`SessionManager`. There must not be two independent session-creation algorithms.

Rules:

- `--session-id` resolves the manifest-selected workspace;
- a conflicting explicit `--workspace` exits 2;
- without `--session-id`, `SessionManager` creates a new session and provisions
  `/sessions/<session-id>` from `/repo` through the approved workspace helper;
- direct `docker compose exec` must use the same SessionManager path;
- the entrypoint must not rely on a shell-local workspace variable to provide
  session context to a later process.

If the existing shell clone code cannot be safely reused by the canonical
SessionManager, stop and create a workspace-ownership implementation subplan;
do not silently keep duplicate owners.

### S1-D6 — Run-to-session binding

Every run must persist an explicit binding:

```text
run_id → session_id
```

The binding must be stored in the approved session authority and/or a validated
run manifest. Event queries must be scoped to `run_id`; session queries must be
scoped to `session_id`.

Required negative cases:

- run ID exists but belongs to another session;
- session ID exists but workspace path differs;
- run artifact directory exists without a valid binding;
- two sessions attempt to claim one run ID;
- one EventLog instance reads another run's rows.

### S1-D7 — Clean-cutover read behavior

Freeze the DB-only current-format reader:

```text
new session/run with valid session.db:
  fa stats reads DB rows scoped by session_id/run_id

old JSONL-only directory:
  fa stats does not create session.db
  fa stats returns explicit unsupported/legacy diagnostic
  fa stats exits with the documented non-zero code
```

No automatic import and no hidden JSONL fallback are allowed in the first
implementation.

### S1-D8 — Existing artifact disposition

Freeze:

- existing per-run DBs are not modified by S1;
- existing JSONL files are not deleted by S1;
- no automatic migration runs during `fa run`, `fa workflow`, or `fa stats`;
- later migration, if needed, is a separate explicit plan with backup,
  validation, count/hash comparison, and rollback.

## 5. Step-by-step S1 execution

### Step S1.1 — Validate the baseline map

Traces-to: CT1, CT2, CT4, CT8, CT9.

Target liveness: source map L1→L2; no runtime behavior claim.

Allowed files: the subplan and verification report only.

Do:

1. Re-run the source checks against baseline commit `3668e758c...`.
2. Record exact parser arguments for `fa run` and `fa workflow`.
3. Record exact entrypoint session/workspace behavior.
4. Record exact `_cmd_run` trace path behavior.
5. Record exact `SessionState`/Blackboard construction behavior.
6. Record the difference between baseline and unapproved candidate patch.

Do not:

- do not call the candidate patch “implemented”;
- do not infer that an entrypoint shell-local variable is available to later
  `docker compose exec` processes;
- do not edit runtime files to make the map easier to describe.

Exit criteria:

- [x] every baseline claim has file:symbol evidence;
- [x] every candidate-only behavior is labelled candidate;
- [x] no source/test files changed.

### Step S1.2 — Compare lifecycle ownership options

Traces-to: CT1, CT2, CT8, G4.

Target liveness: lifecycle decision L0→L2.

Do:

1. Compare CLI-owned `SessionManager`, entrypoint-owned lifecycle, and a
   separate session registry against the accepted requirements.
2. Use explicit criteria:
   - direct `docker compose exec` support;
   - WebUI command support;
   - workspace isolation;
   - persistent session reuse;
   - testability;
   - no duplicate clone authority;
   - operator-visible failures.
3. Record Q10-A as selected: CLI-owned SessionManager, one logical workspace/session
   owner, with the entrypoint acting as an integration adapter.
4. If a new policy question appears, stop and add Q12+.

Exit criteria:

- [x] one ownership design selected;
- [x] entrypoint boundary is explicit;
- [x] direct exec behavior is listed as a blocking deployment verification;
- [x] no duplicate logical workspace owner is introduced.

### Step S1.3 — Freeze the session/run/path contract

Traces-to: CT1, CT2, CT4, CT8, CT9, CT10.

Target liveness: contract L0→L3-ready.

Do:

1. Freeze S1-D1 through S1-D8.
2. Add exact manifest schema and validation rules to the verification report.
3. Add exact path layout and path-containment rules.
4. Add exact exit/error behavior for unknown session, corrupt manifest,
   workspace mismatch, unsupported legacy artifact, and run/session mismatch.
5. Define how `--resume` behaves under the new run identity policy.
6. Define the `session_id`/`run_id` binding needed by workflow stages.

Exit criteria:

- [x] no lifecycle noun has two meanings;
- [x] one session can contain at least two distinct runs on paper;
- [x] one run cannot belong to two sessions;
- [x] current/legacy read behavior is explicit;
- [x] paths and manifests are machine-checkable.

### Step S1.4 — Define the implementation subplan boundary

Traces-to: G1, G2, G5, G6, CT1, CT2, CT4, CT8, CT9, CT10.

Target liveness: next-slice readiness L0→L3-ready.

Do:

1. Identify the exact future source files/symbols for the SessionManager,
   parser `--session-id`, session DB factory, EventLog injection, and stats DB reader.
2. Identify the exact future tests:
   - parser C0/C2;
   - session manifest C0/C1;
   - session attach/create C1/C2;
   - run/session binding C1;
   - old-format unsupported/clean-cutover C2;
   - DB-backed `fa stats` C2;
   - direct-container acceptance C2.
3. Keep old-format migration/compatibility outside the new-format implementation;
   no legacy reader is part of the first slice.
4. Create the next implementation subplan only after S1 DoD is complete.

Exit criteria:

- [x] future runtime artifact inventory is exact;
- [x] no forbidden source/test edit was smuggled into S1;
- [x] next implementation slice has no unresolved lifecycle policy choice.

## 6. Verification plan

### S1 verification classes

S1 is a design/verification slice and therefore does not claim runtime behavior.

| Claim | Test/verification class | Primary oracle |
|---|---|---|
| Baseline parser has no `--session-id` | C0/source verification | exact parser inventory |
| Entrypoint conflates `SESSION_ID` and `FA_RUN_ID` | C0/source verification | exact shell lines |
| Current trace path is run-based | C0/source verification | `_cmd_run` path construction |
| Current Blackboard injection path | C0/source verification | `SessionState` constructor call |
| Session/run target contract is internally consistent | design review + report | identity/path/state table |
| Legacy clean cutover has no hidden migration | contract specification | explicit error/no-write rule |
| Option A has no unowned authority scope | design review | session/run/DB scope matrix |

### Producer kill-check

No product producer is changed in S1. Therefore a runtime producer kill-check is
**N/A by design**, and the report must not claim L3 product behavior. Producer
kill-checks begin in the first runtime implementation subplan after S1.

### Static/document checks after each S1 edit

```bash
git diff --check
python scripts/check_doc_links.py
```

The executor must also inspect:

```bash
git diff -- worklogs/implementation-plans/PLAN-cli-trace-S1-session-lifecycle.md
git status --short
```

No pytest run is required for a docs-only S1 edit unless the executor changes a
runtime/test file, which is forbidden by this subplan.

## 7. Risks, rollback, and stop conditions

| ID | Risk | Mitigation | Detection |
|---|---|---|---|
| S1-R1 | CLI and entrypoint both create workspaces | freeze one owner before coding | duplicate clone/path trace |
| S1-R2 | `--resume` silently reuses old run_id | define session continuation separately | two-run identity test |
| S1-R3 | old JSONL behavior is reintroduced as hidden fallback | clean-cutover contract + no-write test | legacy stats probe |
| S1-R4 | session DB path leaks host topology | keep paths container-internal | path/source grep |
| S1-R5 | manifest becomes a second authority | manifest stores identity/path metadata only | authority table review |
| S1-R6 | artifact-only subagent policy leaks into S1 runtime edits | forbid `src/fa`/`tests` changes | post-edit status check |

### Rollback

S1 produces documentation/design artifacts only. Rollback is:

```text
revert the S1 subplan/report and main-plan update;
no runtime DB or session artifact is changed.
```

### Mandatory stop conditions

Stop and create Q12+ if any of the following remains undecided:

- who owns workspace creation for direct `docker compose exec`;
- whether `--workspace` can override a manifest-selected workspace;
- whether `--resume` means session continuation or trace continuation;
- exact unsupported legacy exit code/message;
- exact session manifest path/schema;
- exact run-to-session binding storage;
- whether an existing session may be attached from a different container/workspace.

## 8. Definition of Done

### State

Before S1:

```text
session_id and run_id are conflated in the entrypoint;
fa run/workflow have no --session-id;
EventLog authority is currently per-run-shaped;
legacy stats can create/read through JSONL fallback;
```

After S1:

```text
session_id, run_id, and event_id have one meaning each;
Option A is translated into an exact path/scope contract;
--session-id lifecycle is specified;
clean cutover read behavior is specified;
old artifacts are explicitly outside automatic migration;
future runtime edits have exact file/symbol/test boundaries.
```

### Artifacts

- this subplan;
- `cli-trace-S1-verification-report.md`;
- approved update to the parent workplan;
- updated `HANDOFF.md` with evidence and next subplan.

### Contracts

- `CT1`, `CT2`, `CT4`, `CT6`, `CT8`, `CT9`, and `CT10` have S1 design status;
- Q10 is either resolved or promoted to a new explicit blocking Q#;
- Q2 clean-cutover behavior is explicit;
- no runtime claim is marked IMPLEMENTED or VERIFIED by S1.

### Negative proof

S1 is invalid if:

- a later executor still needs to guess whether DB scope is session or run;
- a later executor still needs to guess what `--session-id` attaches to;
- a legacy stats read can silently create a DB;
- the plan says “workspace is read-only” without naming the enforcement root;
- the subplan claims a producer kill-check despite changing no producer.

## 9. Approval and handoff

This subplan is ready for design/verification execution, not runtime code changes.

At S1 close, the executor must report:

```text
S1 STATUS: PASS | BLOCKED
Q12+: none | <exact question>
Files changed: <exact list>
Runtime files changed: NONE (required)
Verification commands: <commands + actual outputs>
Parent plan update: <exact section/IDs>
Next subplan: <path>
```
