# PLAN: S2 — SessionManager and Session-Authority Wiring

Plan-ID: `PLAN-cli-trace-S2-session-manager-and-authority`

Status: **READY** — implementation complete for the approved local S2 scope;
verification evidence is recorded in
`worklogs/implementation-plans/cli-trace-S2-verification-report.md`.

Revision: v3 — implementation and verification evidence added; deferred S5/S4
work remains explicitly outside S2.

Parent workplan:

- `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`

S1 authority:

- `worklogs/implementation-plans/PLAN-cli-trace-S1-session-lifecycle.md`
- `worklogs/implementation-plans/cli-trace-S1-verification-report.md`

Baseline:

```text
origin/main = 3668e758c1522645a1bfb70787ebf53f7ef170a7
```

## 0. Scope and execution boundary

### Idea implemented by S2

Turn the accepted session/run design into a small production seam:

```text
SessionManager
  → resolves/creates session_id
  → validates workspace + manifest
  → opens one session-authority DB
  → allocates a new run_id
  → gives _cmd_run/_cmd_workflow a scoped SessionContext

EventLog
  → remains a run-scoped facade
  → writes event rows into the session authority
  → reads only rows for its run_id

Blackboard
  → remains session-scoped
  → uses the same session authority

fa stats
  → reads the new DB format
  → does not create or silently import legacy JSONL/DB data
```

### Concrete intent

Implement the smallest production seam that makes the following true:

```text
session_id is stable across days and runs;
run_id is new for every fa run/fa workflow invocation;
Session A cannot read Session B state;
Run A-1 cannot read Run A-2 event rows;
Blackboard A persists across runs A-1/A-2;
old trace files are not silently migrated or used as authority.
```

### S2 shape

S2 is one subplan with two sequential checkpoints and five implementation
steps:

```text
S2-A — authority bootstrap seam, SessionManager, manifest, parser, entrypoint
S2-B — session DB injection, scoped EventLog/Blackboard, DB-backed stats
```

The authority bootstrap seam is part of S2.1, before `SessionManager.begin_run`
is exercised. S2-A must be green before S2-B begins. If S2-B reveals a schema
or policy choice not already covered here, stop and promote it to Q12+ rather
than expanding the patch silently.

Plan-review identity correction:

```text
one top-level `fa workflow` invocation → one new workflow run_id
all internal role stages in that invocation reuse that run_id in S2
stage/role identity remains in event fields and workflow artifacts
no new `workflow_id` or per-stage run namespace is introduced in S2
```

This matches the accepted identity model (`run_id` identifies one `fa run` or
one `fa workflow` execution), the current `_WorkflowContext`, and the existing
single `flow_state.json`/`eval_report.json` artifact namespace. Per-stage run
IDs would require a separately approved workflow identity contract.

### Explicit non-goals

- No event allocator redesign beyond preserving a clear seam for S5.
- No Blackboard conflict-policy redesign beyond session-scope wiring.
- No `fs_spawn_subagent` implementation; Q11-B is a later slice.
- No EventBus redaction change; V23 remains deferred.
- No workflow repair/adaptive redesign.
- No automatic migration of old JSONL or per-run DBs.
- No `fa inspect` command.
- No host wrapper changes to `scripts/fa`.
- No production deployment in S2.

## 1. Before editing: source-verified current behavior

### 1.1 CLI parser

`src/fa/cli.py` currently has no `--session-id` argument for `fa run` or
`fa workflow`. It has `--run-id`, `--workspace`, and `--resume` on relevant
roots. The parser is built in one large module through `build_parser()`.

### 1.2 Entrypoint

`scripts/fa-entrypoint.sh:149-152` currently derives:

```text
SESSION_ID from FA_RUN_ID or a generated value
FA_RUN_ID is then overwritten with SESSION_ID
SESSION_DIR=/sessions/<SESSION_ID>
```

This is the V26 lifecycle defect. The shell script also owns clone setup and
uses a shell-local `WORKSPACE` variable before command override/auto-run.

### 1.3 Current run root

`_cmd_run()` currently derives `run_id` from `args.run_id` or process ID and
builds per-run paths under:

```text
/home/fa/.fa/session-log/<run-id>/
```

It constructs `EventLog` directly and later constructs `SessionState`.

### 1.4 Current state/authority

`SessionState` currently has no first-class `session_id` field. It derives
`session_db` from `log.session_db` only when no DB was supplied. Production
Blackboard construction injects that DB, but a standalone Blackboard can create
a separate DB.

`SessionDatabase` currently creates its parent/schema and has tables:

```text
event_log
blackboard
session_meta
```

The current schema is per-run-shaped and does not enforce a session identity at
the DB boundary. Event read queries are not run-scoped.

### 1.5 Current stats

`fa.stats.parse_session()` constructs `EventLog(events_path)`, which can create
an authority DB while reading old JSONL. S2 must change the current-format path
to resolve the session DB explicitly and return a structured unsupported result
for old paths.

## 2. Contracts and gap IDs

### Parent contracts

- `CT1` — CLI dispatch and command-root contract.
- `CT2` — session authority and run-scoped trace contract.
- `CT4` — Blackboard conflict and session ownership contract.
- `CT6` — workflow controller/artifact contract.
- `CT8` — deployment topology contract.
- `CT9` — event identity and run-binding contract.
- `CT10` — authority failure-policy contract.

### Gaps addressed

- `V3` — remove hidden current-format JSONL fallback.
- `V4` — remove Blackboard mirror fallback from current authority path.
- `V5` — prevent stats from creating DB while reading old artifacts.
- `V7` — add session/run binding and scoped queries.
- `V16` — reject or normalize mismatched session DB injection.
- `V26` — separate entrypoint `session_id` from per-invocation `run_id`.

### Gaps deliberately deferred

- `V1`/`V2` — event allocator/counter correctness belongs to S5, but S2 must
  not make it harder to replace the current allocator.
- `V15`/`V17` — symmetric mutation conflict/fail-closed behavior belongs to S5.
- `V24`/`V25` — artifact-only subagent two-root enforcement belongs to a later
  subagent subplan.

## 3. Exact files allowed to change

### S2-A allowed files

- `src/fa/session/__init__.py` — NEW package export.
- `src/fa/session/manager.py` — NEW `SessionManager` and context dataclasses.
- `src/fa/inner_loop/session_db.py` — authority schema/open/reservation seam
  required before `SessionManager.begin_run`.
- `src/fa/cli.py` — parser and composition-root wiring only.
- `scripts/fa-entrypoint.sh` — session/run identity adapter only; no wrapper change.
- `tests/test_session_lifecycle.py` — NEW C0/C1/C2 lifecycle tests.
- `tests/test_session_db_authority.py` — only tests for the new session-schema,
  read-only-open, identity, and run-binding seam.
- `tests/test_cli.py` — only tests for the changed `fa run` root.
- `tests/test_cli_ergonomics.py` — only parser/workflow session argument tests.
- `tests/test_fa_entrypoint.py` — only identity/command handoff tests.

### S2-B allowed files

- `src/fa/inner_loop/session_db.py` — session-scoped schema/queries and
  read-only existing-DB open path.
- `src/fa/inner_loop/state.py` — `SessionState`/`EventLog` DI and run scope.
- `src/fa/blackboard/blackboard.py` — session-scoped facade binding.
- `src/fa/stats.py` — DB-backed current-format reader and unsupported legacy result.
- `src/fa/cli.py` — stats discovery/selector wiring only; no unrelated CLI change.
- `tests/test_session_db_authority.py` — authority and scope tests.
- `tests/test_inner_loop_audit_sink.py` — run-scoped EventLog tests.
- `tests/test_observability_runtime_authority.py` — read/authority tests.
- `tests/test_stats.py` — clean-cutover DB/stats tests.

### Documentation allowed at close only

- `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`.
- `worklogs/implementation-plans/PLAN-cli-trace-S2-session-manager-and-authority.md`.
- `worklogs/HANDOFF.md`.
- `knowledge/llms.txt` only if a new S2 artifact is added.

### Forbidden

- `scripts/fa` and `/usr/local/bin/fa`.
- provider adapter files.
- EventBus/renderer files unless a new blocking contract requires it.
- subagent files.
- workflow routing redesign.
- automatic migration code.

If any forbidden file is needed, stop and create Q12+.

## 4. Frozen implementation contract

### 4.1 Session roots

S2 uses Candidate A from S1:

```text
FA state root:
  /home/fa/.fa

session registry/authority:
  /home/fa/.fa/sessions/<session-id>/manifest.json
  /home/fa/.fa/sessions/<session-id>/session.db

per-run artifacts:
  /home/fa/.fa/session-log/<run-id>/
```

Tests inject temporary `state_root`, `workspace_root`, and source repo paths.
Production code must not depend on host path `/srv/first-agent/state`.

### 4.2 SessionManager construction and typed contexts

`SessionManager` must receive the deployment roots explicitly at construction;
the manager must not infer the host path `/srv/first-agent/state`:

```python
SessionManager(
    state_root: Path,          # production: Path.home() / ".fa"
    workspace_root: Path,      # production: /sessions
    source_workspace: Path | None = None,  # optional clone/template source
)
```

The parser must preserve whether `--workspace` was supplied. For `fa run` and
`fa workflow`, the parser default is `None`, not `Path.cwd()`; `None` means the
manager selects/provisions the default session workspace. `--workspace PATH` is
an explicit creation/attach override and is validated against the manifest.

S2-A must define frozen typed contexts with at least:

```text
SessionContext:
  session_id: str
  workspace_path: Path
  session_db_path: Path
  manifest_path: Path

RunContext:
  run_id: str
  session_id: str
  workspace_path: Path
  session_db_path: Path
  run_log_dir: Path
```

`SessionContext` may carry an already-open `SessionDatabase` only if ownership
and close/lifetime semantics are explicit; otherwise all production consumers
receive the same validated `session_db_path` plus the same `session_id`.
Do not pass loose dictionaries through the composition root when a frozen typed
dataclass can express the boundary.

### 4.3 SessionManager API

The exact implementation may use different private helpers, but the public
seam must express these operations:

```python
create_or_attach_session(
    *,
    session_id: str | None,
    workspace_override: Path | None,
) -> SessionContext

begin_run(
    session: SessionContext,
    requested_run_id: str | None,
) -> RunContext
```

Rules:

- no `session_id` → generate a new valid ID;
- explicit unknown `session_id` → structured error, no implicit creation;
- explicit existing session → validate manifest/workspace/DB;
- workspace mismatch → exit 2 before provider/tool execution;
- every invocation → new run ID;
- explicit reused run ID → exit 2;
- session DB directory and run artifact directory are created before use;
- manifest and run binding are written atomically;
- secrets and raw prompts never enter the manifest.

### 4.4 Manifest and run binding

Manifest fields:

```json
{
  "schema_version": "v1",
  "session_id": "session-A",
  "workspace_path": "/sessions/session-A",
  "session_db_path": "/home/fa/.fa/sessions/session-A/session.db",
  "created_at": "...",
  "last_used_at": "...",
  "status": "active"
}
```

The session DB records a run binding under a namespaced key such as:

```text
run_binding:<run-id>
```

with a JSON value containing `run_id`, `session_id`, and creation timestamp.
The implementation must choose one canonical encoding and test it; it must not
write two competing binding formats. The reservation must use a transactional
insert that rejects an existing binding; `INSERT OR REPLACE` is forbidden for
run admission.

Provisioning is a small state machine, not a multi-file best-effort sequence:

```text
new session: manifest status=provisioning
  → workspace/DB validation and initialization
  → DB session identity write + manifest status=active
attach: validate active manifest + DB identity before updating last_used_at
failure: no provider/tool start; remove only newly-created unowned workspace
         or leave an explicit failed/provisioning record that attach rejects
```

A new session may not bind an already-manifested workspace owned by another
session. The manager must check reverse ownership under the state root before
writing the new manifest.

### 4.5 Session DB scope and existing-DB policy

The new-format DB is session-scoped:

```text
session_meta:
  schema_version + session_id + run bindings
blackboard:
  session ownership is validated against the DB session identity;
  `run_id` is retained as producer provenance, but reads are session-scoped
event_log:
  session_id + run_id on every current-format row
  every production EventLog read filters by its run_id
```

S2 must add the required columns/indexes and an explicit schema identity check.
An existing DB with the old per-run schema, missing session identity, or an
incompatible schema version is **unsupported**, not implicitly altered. The
new-format constructor may create a fresh DB; stats must use a read-only
`open_existing` path that never creates a missing DB or parent directory.

S5 owns the final atomic event allocator and duplicate-ID uniqueness policy; S2
must preserve a clean insertion seam for S5.

### 4.6 Stats clean cutover and discovery

For a valid new session DB:

```text
fa stats [--session-id A] [--run-id R]
  → enumerate/resolve Candidate A manifest(s)
  → open existing session.db read-only
  → query DB rows by session scope and optional run_id
  → human-readable projection
```

`_cmd_stats` must not discover current runs by treating
`session-log/<run-id>/events.jsonl` as the source. It may use per-run JSONL only
for existence/count metadata if explicitly classified as a mirror; analytics
rows come from the session DB. The current-format parser API must accept an
already-validated session DB/source plus the target `run_id`, not construct
`EventLog(events_path)`.

For an old JSONL/old per-run DB path:

```text
no DB creation
no import
no hidden fallback
structured unsupported/legacy result
exit code 2
```

## 5. Step-by-step implementation

### Step S2.0 — Baseline and source identity guard

**Idea:** prove the executor starts from the exact baseline and does not apply
the old candidate patch.

**Concrete intent:** prevent S2 from implementing against unreviewed candidate
behavior or a different origin revision.

**Current behavior:** working tree contains an unapproved candidate diff; origin
main is `3668e758c1522645a1bfb70787ebf53f7ef170a7`.

**Code mechanism:** no production edit. Record `git rev-parse`, `git status`,
allowed paths, and candidate patch SHA before touching code.

**Production practice:** reproducible build/patch provenance; never implement
against an ambiguous tree.

**Failure behavior:** baseline mismatch or missing backup → stop before edits.

**DoD and negative proof:**

- base SHA matches parent plan;
- candidate patch remains unapproved;
- a disposable `git apply --check` passes for the candidate backup;
- changing the expected base makes the guard fail.

**Tests-writing class:** C0/source/provenance check.

**Producer kill-check:** N/A; no product producer changed.

**Allowed edit:** subplan/report metadata only.

### Step S2.1 — Add the session-authority bootstrap seam, typed SessionManager, and manifest boundary

**Idea:** establish the session DB authority seam before any manager run
reservation, then centralize session identity/path/workspace/manifest resolution
instead of scattering it across CLI and shell entrypoint.

**Concrete intent:** make `session_id` the persistent namespace and prevent
unknown/mismatched sessions from silently creating or using another workspace;
make run admission atomic without opening a second SQLite path.

**Current behavior:** no `--session-id`; entrypoint conflates `FA_RUN_ID` and
`SESSION_ID`; no Python session manifest/manager exists.

**Target behavior:** a typed `SessionManager` returns validated `SessionContext`
and `RunContext` using Candidate A paths.

**Code mechanism:** first extend `SessionDatabase` with explicit session
identity/schema-version validation, a transactional `reserve_run_binding()`
operation, and a non-creating `open_existing()` read path. Then add
`src/fa/session/manager.py` and package export; implement exact ID validators,
UUID-based ID generation, atomic manifest writes, manifest validation, reverse
workspace-ownership checks, and run binding reservation through the DB seam.
Inject roots for tests; resolve `Path.home()` at construction/boundary, not as a
hidden module-level side effect.

**Production practice:**

- immutable/frozen context dataclasses;
- atomic temp-file plus rename for manifests;
- `resolve()` plus explicit root containment;
- reject unknown explicit IDs;
- no secrets/prompts in manifests;
- idempotent attach, but not idempotent run reuse;
- clear typed domain errors at the boundary.

**Failure behavior:**

```text
invalid ID                 → structured invalid_params/config error
unknown explicit session  → exit 2; no workspace/DB mutation
corrupt manifest           → exit 2; no provider/tool execution
workspace mismatch         → exit 2; no run started
run ID already bound       → exit 2; no trace append
```

**DoD and negative proof:**

- C0 tests cover valid/invalid IDs and manifest parsing;
- C0/C1 authority tests cover fresh schema, `open_existing()` no-create
  behavior, session identity validation, and atomic run-binding reservation;
- C1 tests create and reattach a session using temporary roots;
- C1 test proves a second run gets a different `run_id` while reusing the
  same session DB/workspace;
- negative tests prove unknown session, path escape, corrupt manifest, and
  reused run ID fail closed;
- deleting the manifest validation call makes the negative test fail.

**Tests-writing class:** C0, C1, C3 for path/security cases.

**Producer kill-check target:** `SessionManager.create_or_attach_session()`
and `begin_run()`; removing the manifest/run-binding producer must make the
session attach/negative tests fail.

**Allowed files:**

```text
src/fa/inner_loop/session_db.py
src/fa/session/__init__.py
src/fa/session/manager.py
tests/test_session_db_authority.py
tests/test_session_lifecycle.py
```

### Step S2.2 — Wire `--session-id` and new run identity through CLI roots

**Idea:** make `fa run` and `fa workflow` consume the same session resolver and
never use the old implicit PID/run conflation.

**Concrete intent:** both CLI roots must have identical session selection rules:
new session by default, existing session only with `--session-id`, and new
`run_id` for every invocation.

**Current behavior:** `_cmd_run` and `_cmd_workflow` have separate run/workspace
handling; neither parser has `--session-id`; workflow stages use old resume/run
semantics.

**Target behavior:** parser accepts `--session-id`; both roots call the shared
SessionManager boundary; a top-level workflow invocation receives one new
`run_id`, and all internal stages carry the selected `session_id` while reusing
that workflow run ID. No per-stage run namespace is introduced in S2.

**Code mechanism:**

- add `--session-id` to the `run` and `workflow` parsers;
- resolve session/run context before provider/tool factories;
- pass resolved workspace to the existing root;
- replace implicit `run-<pid>` behavior for production invocation;
- reject reused explicit run IDs;
- make workflow stage calls pass session identity and the workflow run
  identity; internal stage continuation must remain explicit and must not be
  mistaken for a second top-level invocation;
- retain `--run-id` only as a controlled new-ID override;
- make public `--resume` a deprecated compatibility path that requires
  `--session-id`, allocates a new top-level run ID, and never appends to the
  old run trace; the existing workflow-internal draft continuation is a
  separate private stage behavior and reuses the workflow run ID.

**Production practice:** one composition boundary, one resolver, no duplicated
CLI-specific session policy, fail before provider/network/tool side effects.

**Failure behavior:** parser/identity/path errors return `2`; provider is not
constructed and `Transport.post` call count remains zero.

**DoD and negative proof:**

- C2 parser tests prove `--session-id` is accepted by both roots;
- C2 default-new-session test proves two top-level invocations create
  different session IDs and run IDs;
- C1 attach test proves `--session-id A` uses the same workspace/DB and a new
  run ID;
- C2 mismatch/unknown/reused-ID tests return `2` before provider calls;
- workflow test proves every stage binds to the selected session and the
  invocation's one workflow run identity; no stage silently creates a second
  workflow namespace;
- removing the SessionManager call from either root makes the corresponding
  C2 test fail.

**Tests-writing class:** C1/C2, with C3 path mismatch cases.

**Producer kill-check target:** the real `_cmd_run` / `_cmd_workflow` session
resolution call site, not only parser construction.

**Allowed files:**

```text
src/fa/cli.py
tests/test_cli.py
tests/test_cli_ergonomics.py
```

### Step S2.3 — Reconcile entrypoint ownership

**Idea:** make the entrypoint an adapter to the canonical SessionManager rather
than a second session allocator.

**Concrete intent:** remove the V26 identity conflation and prevent direct
`docker compose exec` from depending on shell-local entrypoint state.

**Current behavior:** entrypoint creates `/sessions/<FA_RUN_ID>` and exports the
same value as `FA_RUN_ID`; later command override/exec behavior is a separate
process boundary.

**Target behavior:** SessionManager is the logical owner of manifest/DB/run
identity. The entrypoint is only a filesystem/container adapter: it may clone
or reuse a workspace, but it passes `FA_SESSION_ID`/`--session-id` and never
maps a session identifier into `FA_RUN_ID`. Command-override mode must not rely
on shell-local variables surviving a later `docker compose exec` process.

**Code mechanism:** update `scripts/fa-entrypoint.sh` only after S2.1/S2.2 have
working SessionManager contracts; replace the old `SESSION_ID=FA_RUN_ID`
assignment with explicit `FA_SESSION_ID` handoff; auto-run passes
`--session-id` and does not invent a run ID when the CLI manager can allocate
one. Preserve command override behavior, and test direct exec with explicit
`--session-id`/`--workspace` rather than assuming PID-1 shell state.

**Production practice:** avoid two implementations of lifecycle; preserve
container standby/health behavior; fail closed on clone/manifest failure; keep
host wrapper out of scope.

**Failure behavior:** failed provisioning writes explicit status/diagnostic and
must not launch `fa run` against an ambiguous workspace.

**DoD and negative proof:**

- shell tests prove no `FA_RUN_ID`/`SESSION_ID` conflation;
- command override and auto-run tests prove the selected workspace/session
  context is explicit;
- clone failure enters the documented failed/standby state;
- a test with stale/missing workspace cannot start a run;
- removing the entrypoint/SessionManager handoff makes the command-context
  test fail.

**Tests-writing class:** C2 shell/container-boundary tests.

**Producer kill-check target:** entrypoint/session handoff plus the CLI
SessionManager call; no host wrapper test is accepted as a substitute.

**Allowed files:**

```text
scripts/fa-entrypoint.sh
tests/test_fa_entrypoint.py
```

### Step S2.4 — Bind SessionState/EventLog/Blackboard to session DB

**Idea:** move the physical SQLite authority from per-run construction to the
session context while keeping EventLog run-scoped.

**Concrete intent:** all runs in Session A share the same authority DB and
Blackboard, but each EventLog reads only its own run rows.

**Current behavior:** EventLog constructs a DB beside per-run events JSONL;
SessionState only inherits `log.session_db` when no DB is supplied; Blackboard
can create its own standalone DB. Many unit fixtures and non-S2 CLI helpers use
these constructors directly.

**Code mechanism:**

- add `session_id` to SessionState/authority context;
- inject the session DB and session identity into the production `fa run` and
  workflow EventLog/Blackboard composition roots;
- add `session_id` to event rows and required scope metadata;
- make EventLog read/query methods require `run_id` scope;
- make Blackboard read/write methods require session scope;
- reject mismatched explicit `log.session_db`/`state.session_db`;
- create new-format session schema with version marker and required indexes;
- preserve a clean seam for S5's atomic event allocator;
- allow best-effort JSONL mirror writes where the existing facade contract
  requires them, but never use JSONL as a current-format reader or authority;
- preserve direct `EventLog()`/`Blackboard()` construction only as an explicit
  test/legacy compatibility path; S2 must not claim that path is production
  session authority wiring, and `fa stats` must never invoke it.

**Production practice:** dependency injection at the composition root; no
standalone authority creation in production; schema versioning; short SQLite
transactions; explicit scope in method signatures; no hidden fallback.

**Failure behavior:** DB/schema/scope failure is structured and fail-closed for
correctness; mirror/derived artifacts are not used as authority.

**DoD and negative proof:**

- C1 test creates two runs in one session DB and proves filtered reads;
- production composition test proves the injected DB/session identity is used;
  compatibility constructors are tested separately and cannot satisfy this
  kill-check;
- C1 test creates two sessions and proves no cross-session rows;
- C1 test proves Blackboard persists across two runs in one session;
- C3 test rejects mismatched session DB/path/manifest;
- C3 test proves old JSONL-only stats does not create a DB;
- removing `WHERE run_id = ?` makes run-isolation test fail;
- removing session DB injection makes same-authority test fail.

**Tests-writing class:** C1/C3.

**Producer kill-check target:** SessionState composition root and EventLog/
Blackboard injection call sites.

**Allowed files:**

```text
src/fa/inner_loop/session_db.py
src/fa/inner_loop/state.py
src/fa/blackboard/blackboard.py
tests/test_session_db_authority.py
tests/test_inner_loop_audit_sink.py
tests/test_observability_runtime_authority.py
```

### Step S2.5 — Switch `fa stats` to DB-only current format

**Idea:** make the existing human-readable stats surface consume the DB SSOT
without mutating old trace directories.

**Concrete intent:** current-format stats are machine-correct and old-format
artifacts are explicitly unsupported, not silently imported.

**Current behavior:** `parse_session(events_path)` constructs EventLog and may
create DB/fallback to JSONL.

**Code mechanism:**

- resolve one or more session/run sources from Candidate A manifests without
  constructing a missing DB;
- use `SessionDatabase.open_existing()` and query the DB-backed reader by
  `session_id`/`run_id`;
- render the existing `SessionAnalytics` human-readable output;
- reject old JSONL/old DB-only paths with structured
  `legacy_trace_unsupported` and exit code `2`;
- do not add `fa inspect`;
- do not create/import DB during read.

**Production practice:** read commands must be side-effect-free; one existing
consumer is reused; error codes are deterministic; no compatibility policy is
hidden in a generic EventLog facade.

**Failure behavior:** missing/corrupt/unsupported source returns the documented
non-zero result and does not create files.

**DoD and negative proof:**

- C2 current-format stats discovers/accepts Candidate A session DB and
  filters run rows;
- C2 old JSONL directory remains unchanged after stats;
- C0/C1 read-only-open test proves a missing DB and parent directory remain
  absent;
- C2 DB-only session with empty/partial rows has deterministic output;
- C3 corrupt manifest/DB returns error without mirror fallback;
- removing DB reader wiring makes the current-format C2 test fail.

**Tests-writing class:** C1/C2/C3.

**Producer kill-check target:** `_cmd_stats`/`parse_session` DB reader call; no
consumer-only formatter test is sufficient.

**Allowed files:**

```text
src/fa/stats.py
tests/test_stats.py
tests/test_stats_global_wiring.py
```

## 5.1 Plan-review record — 2026-07-27

The first READY review found six execution gaps against the source-verified
baseline. They are corrected in this revision rather than left as executor
assumptions:

| ID | Gap | Evidence | Correction |
|---|---|---|---|
| PR-S2-1 | Run reservation was scheduled after the manager API that needs it. | `SessionDatabase` was allowed only in S2-B while `begin_run()` promised DB-backed binding. | S2.1 now establishes schema identity, `open_existing()`, and transactional run reservation before manager tests. |
| PR-S2-2 | Workflow stage IDs were inconsistent with the accepted `run_id` meaning and existing artifacts. | `_WorkflowContext` and `_run_stage()` use one ID for `flow_state`, `eval_report`, and all stages; no `workflow_id` exists. | S2 uses one run ID per top-level workflow invocation; stage identity remains role/event metadata. |
| PR-S2-3 | DB-only stats had no discovery/read-only API and `cli.py` was forbidden in S2-B. | `_cmd_stats` scans `session-log`; `parse_session()` constructs `EventLog`, whose DB constructor creates files. | S2.5 adds Candidate A discovery, `SessionDatabase.open_existing()`, explicit stats CLI wiring, and no-create tests. |
| PR-S2-4 | Workspace default/ownership and partial provisioning were underspecified. | `--workspace` defaults to `Path.cwd()`; no reverse ownership or provisioning state was named. | Parser default becomes `None`; manager receives roots, checks ownership, uses provisioning/active states, and fails closed. |
| PR-S2-5 | “All authority wiring” would incorrectly include direct test/legacy constructors. | Source-wide grep found many direct `EventLog()` fixtures and non-S2 helper paths. | Production `fa run`/workflow injection is the S2 claim; direct constructors remain explicit test/legacy compatibility paths. |
| PR-S2-6 | Entrypoint ownership wording implied shell state could be authoritative. | `FA_RUN_ID` is currently assigned from `SESSION_ID`; direct `docker compose exec` is a separate process. | Entrypoint passes explicit `FA_SESSION_ID`; SessionManager owns manifest/DB/run identity; direct exec tests pass explicit context. |

No runtime code was changed during this review. The revised execution must still
stop for any new policy question not covered by the frozen contracts above.

## 6. Verification plan

### Matrix

| ID | Configuration/path | Required proof |
|---|---|---|
| A | new `fa run` without session selector | new session, workspace, DB, run ID |
| B | new `fa workflow` without session selector | same session resolver, one workflow run ID shared by its stages |
| C | `fa run --session-id A` | reuse Session A, new run ID |
| D | `fa workflow --session-id A` | reuse Session A, one new workflow run ID, stage bindings |
| E | two runs in Session A | shared Blackboard/session DB, filtered event rows |
| F | Session A vs Session B | no cross-session reads/writes |
| G | reused explicit run ID | exit 2, no append |
| H | `--resume` compatibility | no old-run append |
| I | workspace mismatch | exit 2, zero provider calls |
| J | old JSONL/old DB stats | unsupported, no DB creation |
| K | corrupt/missing manifest | exit 2, no run |
| L | failed workspace provisioning | failed/standby state, no ambiguous run |

### Oracle ranking

```text
session DB rows/counts
→ manifest fields
→ run/session IDs
→ exit code/error code
→ provider call count
→ workspace/trace filesystem effects
→ human-readable output
```

### Full-path proof

```text
root: cli:_cmd_run and cli:_cmd_workflow
matrix: A/B/C/D/E/F/G/H/I/J/K/L
producer: SessionManager resolution + CLI root call
consumer: SessionState/EventLog/Blackboard/stats
paths-covered: 12/12 required paths
kill-check: remove SessionManager call or run_id scoping → named C1/C2 fails
pyramid: A
```

## 7. Risks and rollback

| ID | Risk | Mitigation | Detection |
|---|---|---|---|
| S2-R1 | SessionManager and entrypoint create competing workspaces | one canonical owner and handoff test | duplicate clone/path test |
| S2-R2 | DB scope migration mixes runs | explicit session_id/run_id fields and query filters | two-run/two-session C1 |
| S2-R3 | `--resume` appends to an old run | new run ID requirement and rejection test | old-run row count test |
| S2-R4 | clean cutover breaks useful operator history | preserve old files; explicit unsupported result; no delete | old-format stats test |
| S2-R5 | stats becomes a second authority | DB-only reader; no writes during read | DB/mirror side-effect test |
| S2-R6 | new SessionManager grows into a framework | keep one resolver boundary, no inspect/list commands | artifact inventory/diff review |

Rollback:

- revert S2-A/S2-B checkpoint separately;
- do not delete old per-run DB/JSONL artifacts;
- do not run automatic migration during rollback;
- keep the candidate runtime patch outside the approved S2 diff;
- restore the previous image only after recording source/image revisions.

## 8. Definition of Done

### State

Before S2:

```text
no --session-id
entrypoint conflates SESSION_ID and FA_RUN_ID
session DB is per-run-shaped
EventLog/Blackboard scope is not enforced
stats can create/fallback through JSONL
```

After S2:

```text
SessionManager owns session/run resolution
--session-id exists on fa run/fa workflow
session DB is resolved by session_id
EventLog rows are run-scoped
Blackboard is session-scoped
new fa stats reads DB only
old artifacts are unsupported without writes
entrypoint and CLI have one logical session owner
```

### Artifact/contract DoD

- [x] S2-A targeted tests pass: 127-test consolidated S2 gate includes lifecycle,
  CLI, workflow, and entrypoint paths;
- [x] S2-A kill-checks pass: SessionManager root producer and entrypoint negative
  provisioning proof fail when removed in disposable copies;
- [x] S2-B targeted tests pass: DB scope, Blackboard, and stats tests are green;
- [x] S2-B kill-checks pass: EventLog run scope and stats DB reader fail when
  removed in disposable copies;
- [x] C0/C1/C2/C3 matrix rows are covered for the approved local scope;
- [x] no automatic migration exists;
- [x] no hidden JSONL fallback exists for injected current-format authority;
- [x] no forbidden files were changed by S2;
- [x] main plan, S2 subplan, and S2 verification report contain actual evidence;
- [x] full suite checkpoint passes: 2014 passed, 15 skipped;
- [x] relevant changed-file static checks pass: Ruff, strict mypy, py_compile,
  bash -n, contract checks, and documentation links;
- [x] worktree post-gate contains no unexpected new mutations.

### Per-edit reporting contract

After each edit, the executor must report in chat:

```text
EDIT: <number>
IDEA: <what is being implemented now>
INTENT: <concrete invariant>
CURRENT → TARGET: <behavior change>
MECHANISM: <exact file:symbol/code path>
PRODUCTION PRACTICE: <why this shape is safe/maintainable>
FAILURE BEHAVIOR: <exit/error/deny/fallback>
TEST CLASS: C0/C1/C2/C3
DOD: <specific assertions>
KILL-CHECK: <producer call site and failing test>
COMMANDS: <actual commands run>
RESULT: <actual output>
DIFF: <files changed>
```

If an edit reveals a new policy choice, stop immediately and add Q12+ before
continuing.

## 8.1 Verification evidence pointer

Full actual command output and the deferred-scope classification are recorded
in:

```text
worklogs/implementation-plans/cli-trace-S2-verification-report.md
```

Local S2 is **PASS WITH FOLLOW-UP**. Direct-container production verification
is intentionally pending S4/S7; final event allocator and mutation safety remain
owned by S5.

## 9. Handoff

S2 is ready to execute only after this subplan is approved against the parent
workplan. The first execution step is S2.0 baseline/provenance guard; it must
not edit runtime code until its baseline check passes.
