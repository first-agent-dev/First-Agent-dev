# PLAN: CLI Runtime and Formal-Trace Substrate Re-baselining

Plan-ID: `PLAN-cli-trace-substrate-20260725`

Status: **DRAFT** — parent workplan remains review-gated; S2 subplan is
READY and S2 execution is authorized by the current operator request only.

Depth: **P3** — cross-module runtime substrate, CLI composition roots, state
authority, observable signals, and deployment verification.

Revision: v10 — S2 evidence closed locally; S3 liveness/contract audit
subplan authored and independently reviewed as READY FOR AUDIT EXECUTION.

Upstream context:

- User request: rebuild the working model of the CLI and trace surfaces before
  making further fixes.
- Base checkout: `3668e758c1522645a1bfb70787ebf53f7ef170a7`.
- Candidate uncommitted diff is preserved outside the repository at
  `/home/user/backups/First-Agent-dev-20260725Tcandidate-diff-from-3668e758c1522645a1bfb70787ebf53f7ef170a7.patch`.
- Candidate patch SHA-256:
  `ad975712a055697b6089c32f4e72c5f3258d460e98a40a40dd4b4aefff5f9070`.
- Forensic attachment is untrusted input:
  `/home/user/uploads/2026-07-25-live-fa-run-forensics.md`.
- Production wrapper `scripts/fa` / `/usr/local/bin/fa` is out of scope for
  the core implementation plan. Its deployment behavior is only recorded as
  a boundary condition.

> **Execution gate:** this document is a plan, not authorization to edit
> `src/fa/` or `tests/`. No implementation step may begin until this plan's
> blocking questions and slice order are reviewed by the operator.

---

## Preflight log

### Roots checked

#### Container and deployment roots

- `docker-compose.fa.yml`:
  - `first-agent` runs as `1000:1000`;
  - source bind is `/repo` read-only;
  - `/sessions` is writable per-session workspace storage;
  - `/srv/first-agent/state` is mounted as `/home/fa/.fa`;
  - `fa-egress-proxy` is a separate key-holding service;
  - the agent receives `FA_EGRESS_PROXY_URL` and
    `FA_PROXY_TOKEN_FILE`, but `FA_DEBUG_LLM_BODIES` is not a compose-level
    environment entry.
- `scripts/fa-entrypoint.sh`:
  - command-override mode executes supplied command directly;
  - default mode creates/resumes `/sessions/<session-id>` from `/repo`;
  - `FA_AUTO_RUN` launches a child `fa run` process;
  - source `PYTHONPATH` is prepended only when `<workspace>/src/fa/__init__.py`
    exists.
- `scripts/fa`:
  - host convenience wrapper delegates agent commands through
    `docker compose exec`;
  - no explicit `-e FA_DEBUG_LLM_BODIES=...` forwarding is present;
  - wrapper is not a core product root for this plan.

#### CLI roots

- `src/fa/cli.py:287` — `build_parser()`.
- `src/fa/cli.py:741` — `_cmd_chunk()`.
- `src/fa/cli.py:779` — `_cmd_inner_loop_smoke()`.
- `src/fa/cli.py:935` — `_cmd_help()`.
- `src/fa/cli.py:1512` — `_cmd_workflow()`.
- `src/fa/cli.py:1666` — `_cmd_run()`.
- `src/fa/cli.py:2043` — `_cmd_routing_check()`.
- `src/fa/cli.py:2079` — `_cmd_selfcheck()`.
- `src/fa/cli.py:2194` — `_cmd_probe()`.
- `src/fa/cli.py:2296` — `_cmd_stats()`.
- `src/fa/cli.py:2517` — `_cmd_authoring_check()`.
- `src/fa/cli.py:2534` — `_cmd_egress_proxy()`.
- `src/fa/cli.py:2646` — `main()`.

#### Runtime roots

- `src/fa/inner_loop/coder_loop.py:286` — `drive_session()`.
- `src/fa/inner_loop/loop.py:434` — `run_session()`.
- `src/fa/inner_loop/state.py:92` — `EventLog`.
- `src/fa/inner_loop/state.py:244` — `SessionState`.
- `src/fa/inner_loop/session_db.py:29` — `SessionDatabase`.
- `src/fa/blackboard/blackboard.py:155` — `Blackboard`.
- `src/fa/providers/chain.py:255` — `ProviderChain`.
- `src/fa/output.py:148` — `OutputEvent`.
- `src/fa/output.py:161` — `EventBus`.
- `src/fa/output.py:200` — `ConsoleRenderer`.

### Greps run → verified findings

| Search | Verified finding |
|---|---|
| `add_parser(` / `set_defaults(func=...)` | 11 CLI command roots exist in one large `cli.py`; the parser and command execution are co-located. |
| `SessionDatabase(` | `SessionState`/`EventLog` use per-run DB; `Blackboard` still has a standalone constructor path that can create its own DB when no injected DB is supplied; this requires an authority audit. |
| `EventLog(` | CLI, workflow aggregate export, stats, observability tools, and test fixtures instantiate logs through multiple paths. |
| `EventBus(` / `.emit(` | `EventBus` is assembled in `_cmd_run`; producers are distributed across `coder_loop.py`, `cli.py`, `state.py`, and `spawn_subagent.py`. |
| `OutputEvent` / `_handle_` | `EventType` has 16 literals and `ConsoleRenderer` has 16 handlers. Existing structural checker reports all non-dormant types as having producers, but the checker is regex-based and must itself be audited. |
| `kind=` / `LogKind` | `LogKind` has 33 literals; current contract checker finds 30 distinct producers and reports 3 planned/dead values. |
| `FA_DEBUG_LLM_BODIES` | Exact gate exists in `debug_bodies.py`; `_cmd_run` wraps the transport before provider-chain construction. |
| `flow_state` / `eval_report` | Workflow controller owns machine-readable artifacts separate from the narrative PR draft. `_cmd_workflow` later creates an aggregate `SessionOutcome` with `turns=0`; this is a candidate data-accuracy gap requiring a focused verification, not an accepted fact from an old note. |
| `read_all()` | Full-event reads are used by loop/runtime/stats/global-history paths; performance and authority semantics are not yet treated as one verified contract. |

### Gold patterns mirrored

- `tests/test_cli.py` — real `_cmd_run` with fake transport and temporary HOME.
- `tests/test_cli_ergonomics.py` — parser and workflow composition tests with
  role-aware fake transport.
- `tests/test_event_type_c1_producers.py` — EventBus producer tests.
- `tests/test_session_db_authority.py` — SQLite/JSONL authority tests.
- `tests/test_inner_loop_audit_sink.py` — EventLog resume and AuditHook path.
- `tests/test_fa_entrypoint.py` — shell entrypoint behavior using controlled
  stubs.
- `tests/test_container_build_invariants.py` — static Docker/deployment
  contract tests.
- `tests/test_stats_global_wiring.py` — derived global-history consumer proof.

### Existing checks run

```text
python scripts/check_producer_consumer_contract.py  → PASS
python scripts/check_log_kind_contract.py           → PASS
python scripts/check_no_mocked_dataclasses.py       → PASS
```

These are useful gates but not sufficient proof: the first two use source
regexes and do not replace a path-complete C1/C2 inventory.

### Conflicts/invariants found

- **ADR-7 / reference authority:** `session.db` is the hot-path machine
  authority; JSONL is a human-readable mirror.
- **ADR-7 / tests-writing:** event producer and consumer must both be verified;
  producer kill-check is primary.
- **ADR-10:** deterministic harness and layer-boundary fail-fast are required.
- **ADR-11-I9:** product behavior is not done until a composition-root test
  fails when the production call site is removed.
- **ADR-12:** agent-side provider keys are absent; provider calls go through
  the egress proxy in deployment.
- **ADR-13:** container works in a writable per-session clone, not in the
  read-only host checkout.
- **ADR-14/15:** stateful runtime and formal substrate are intended direction,
  but the current plan does not assume every documented future surface is
  shipped or live.
- **CLI ergonomics/workflow research:** `fa run` is the single-role invoker;
  `fa workflow` is the multi-role controller. Do not collapse them.

### As-is liveness snapshot

Liveness scale: L0 absent, L1 import-reachable, L2 root-reachable but not
verified for the claimed production path, L3 behavior plus producer kill-check.

| Surface | Current evidence | As-is status |
|---|---|---:|
| `fa run` parser and local composition root | `tests/test_cli.py` plus fake transport | L3 for offline C2; L2 for direct Docker deployment |
| `fa run` EventLog/SQLite bootstrap | unit/C1 tests exist; fresh-run defect was reproduced | L2 on base; candidate patch is not approved |
| `fa run` EventBus live stderr | handlers and many tests exist; full path matrix not closed | L2 |
| `fa run` provider chain | adapter/chain tests and CLI fake transport | L3 for offline adapter path; L2 for proxy deployment |
| `FA_DEBUG_LLM_BODIES` core capture | C2 candidate test exists; one operator direct run reported | L3 local; L2 deployed image |
| `fa workflow` linear/repair/adaptive | `tests/test_cli_ergonomics.py` has role-aware fake-transport tests | L3 offline; L2 container/runtime path |
| `fa inner-loop-smoke` | real registry/hook smoke tests | L3 for deterministic smoke path |
| Blackboard conflict path | dedicated unit/C1 tests; standalone-vs-injected authority needs audit | L2 |
| `fa stats` session projection | parser/unit/C2 tests exist | L2 until checked against a fresh production trace and DB/mirror policy |
| global-history projection | dedicated tests; workflow aggregate accuracy needs verification | L2 |
| entrypoint/session workspace creation | shell tests and static Docker checks; no live compose proof in this session | L2 |
| host wrapper | tests exist, but explicitly out of current core scope | N/A for this plan |

### Unresolved questions promoted to Q#

- Q1: What is the physical shape of the session authority DB?
  **Resolved:** Option A — one physical DB per persistent session, with
  session-scoped Blackboard/meta rows and run-scoped `event_log` rows filtered
  by `run_id`. S1 freezes the exact path and manifest contract.
- Q2: What is the exact read-side policy when `session.db` is unavailable or
  empty but `events.jsonl` exists? **Resolved: clean cutover.** Current
  `fa stats` reads only the new session DB format. Old JSONL/old per-run DB
  artifacts remain untouched and are reported as unsupported/legacy. No legacy
  reader or automatic migration belongs in the first implementation.
- Q3: Which CLI root is the first post-baseline production acceptance target?
  **Accepted:** direct `fa run` first, workflow second.
- Q4: Does the operator want an implementation plan for all 11 CLI commands in
  one program of work, or a sequence beginning with `fa run` and adding one
  command family per approved slice? **Accepted:** sequence; no giant PR.
- Q9: Should live EventBus/stderr apply SecretRedactor now?
  **Accepted direction:** keep the current behavior for now and document live
  output redaction as a backlog item; do not make it a blocking first slice.
- Q10: What exact CLI/session lifecycle contract implements Option A?
  **Resolved by S1:** Q10-A — CLI-owned `SessionManager`, `--session-id`,
  default new session creation, explicit existing-session attachment, a new
  `run_id` per invocation, Candidate A session namespace, no automatic
  migration, and a single logical workspace/session owner. Evidence:
  `worklogs/implementation-plans/cli-trace-S1-verification-report.md`.

---

## Operator discussion record — session/run identity (DRAFT)

This section records the current discussion state. It is not an implementation
approval; it records accepted design directions and remaining S1 details.

### Accepted logical model

```text
session_id
  stable identity of one persistent user session and its workspace

run_id
  identity of one `fa run` or `fa workflow` execution inside a session

event_id
  identity of one event produced by that execution
```

The intended user behavior is:

```text
Session A:
  work today
  continue tomorrow
  keep workspace A and Blackboard A

Session B:
  separate workspace
  separate Blackboard
  no state mixing with Session A
```

Default behavior:

```text
new `fa run` / `fa workflow`
  → create a new session by default

explicit session selector
  → attach the run to an existing session

all runs/workflows
  → receive their own run_id and own trace set
```

The CLI option name is accepted as `--session-id`, but it is not a production
flag until the S1 lifecycle contract is implemented and tested.

### Authority is domain-specific, not one total ranking

The phrase “`session_id` → session DB → workspace → Blackboard” is useful as a
rough mental model, but these objects do not all answer the same question and
should not be treated as one linear authority chain:

| Domain | Source of truth | Why |
|---|---|---|
| Session identity | `session_id` plus a validated session manifest/DB record | Names the namespace; an ID by itself is not data authority. |
| Session/run metadata and trace | session-authority DB | Machine-readable, transactional, queryable state. |
| Blackboard state | Blackboard tables in the session-authority DB | Logical domain owned by the session; DB is the storage authority. |
| Current code/files | the session workspace and its git state | The DB records evidence/metadata about files; it does not replace file contents. |
| Human-readable history | DB-backed `fa stats` projection | A formatted read view, not a second authority. |

Therefore the target is not “the DB outranks the workspace for everything.” It is:

```text
session_id selects the namespace
session DB is SSOT for session/run metadata, events, and Blackboard records
workspace is SSOT for current file contents and git state
fa stats is a read projection from the DB
```

### What `EventLog` does

`EventLog` is the facade for the append-only execution history of one run. It
records facts such as:

- user/model messages;
- provider attempts and logical provider call IDs;
- tool calls and tool results;
- hook decisions;
- context/compaction events;
- session stop and summary events.

It is not the persistent session memory or the Blackboard. In a session-scoped
DB design, `EventLog` can remain run-scoped at the API level while querying the
shared session authority with `WHERE run_id = ?`.

### What the Blackboard does

The Blackboard stores structured session working state used for conflict
checking and planning, including content hashes, read/write sets, assumptions,
version dependencies, and file-version entries. Its natural lifetime is the
persistent session/workspace, not one individual `fa run` invocation.

### Option A — one physical DB per session

```text
session A
  session.db
    blackboard rows: session-scoped
    session_meta: session-scoped
    event_log rows: filtered by run_id

run A-1 → run_id=A-1 → events.jsonl mirror A-1
run A-2 → run_id=A-2 → events.jsonl mirror A-2
```

Advantages:

- one physical authority for Blackboard, metadata, and all run events in a session;
- no cross-DB transaction problem when a tool mutation creates both an event and
  a Blackboard entry;
- one DB can answer “what happened in this session?” and “what happened in this run?”;
- event identity can be globally unique within the session DB;
- this fits the formal-substrate goal of one authoritative state store.

Costs:

- every event query must be correctly scoped by `run_id`;
- the session DB grows across all runs in the persistent session;
- the current per-run `session.db` path/layout needs a compatibility migration;
- old readers that assume one DB equals one run can mix data unless changed;
- per-run trace export remains a separate projection rather than the DB itself.

### Option B — session DB plus separate per-run trace DB

```text
session A
  session.db
    Blackboard A
    session metadata A

run A-1
  run.db / events.jsonl
run A-2
  run.db / events.jsonl
```

Advantages:

- the physical lifetime of EventLog matches one run exactly;
- per-run trace deletion/archive is simple;
- current EventLog path is closer to this shape;
- a broken run DB does not make the persistent Blackboard DB unavailable.

Costs:

- there are two authorities for one execution;
- a file mutation, Blackboard entry, and EventLog event cannot be committed in
  one SQLite transaction across both DBs;
- cross-run/session debugging requires joins between DBs;
- every run must carry and validate `session_id` explicitly;
- failure policy becomes more complex: session DB can succeed while run DB fails,
  or the reverse.

### Accepted direction

**Option A is accepted in principle for the formal-substrate target.** The reason
is not “fewer files”; it is that one session authority avoids split-brain between
persistent Blackboard state and the execution events that explain how that state
was produced.

The remaining design spike must specify the session selector, manifest/path
layout, migration of existing per-run DBs, and exact query/index contract before
runtime edits begin.

The API shape must still keep scopes distinct:

```text
SessionDatabase
  physical authority: one persistent session

EventLog
  logical facade: one run_id, queries only that run's event rows

Blackboard
  logical facade: one session_id, queries session state
```

Option B is retained only as a fallback design if the migration/design spike
shows a hard retention, failure-isolation, or deployment constraint that makes
Option A unsafe. It is not the default and must not be selected merely to avoid
designing run-scoped queries.

### Candidate Option A path layouts

S1 must choose between these explicit layouts before runtime implementation.

**Candidate A — separate session namespace:**

```text
/home/fa/.fa/sessions/<session-id>/manifest.json
/home/fa/.fa/sessions/<session-id>/session.db

/home/fa/.fa/session-log/<run-id>/events.jsonl
/home/fa/.fa/session-log/<run-id>/llm_bodies.jsonl
/home/fa/.fa/session-log/<run-id>/flow_state.json
/home/fa/.fa/session-log/<run-id>/eval_report.json
```

**Candidate B — reuse the existing session-log namespace:**

```text
/home/fa/.fa/session-log/<session-id>/manifest.json
/home/fa/.fa/session-log/<session-id>/session.db

/home/fa/.fa/session-log/<run-id>/events.jsonl
/home/fa/.fa/session-log/<run-id>/llm_bodies.jsonl
/home/fa/.fa/session-log/<run-id>/flow_state.json
/home/fa/.fa/session-log/<run-id>/eval_report.json
```

In either layout, the session DB is the authority and per-run files are
mirrors/controller artifacts. The manifest is identity/path metadata, not a
replacement for the DB. S1 selects the layout by collision, binding,
deployment, inspection, and rollback criteria.

### Current code versus accepted model

Current code is closer to “one DB per run”:

```text
entrypoint workspace identity:
  /sessions/<session-id>

_cmd_run trace identity:
  /home/fa/.fa/session-log/<run-id>/

EventLog authority:
  session.db beside that run's events.jsonl

production Blackboard:
  JSONL mirror under <workspace>/.fa/blackboard/
  injected authority currently comes from EventLog's DB
```

This works only if the same stable identity is reused for the whole persistent
session. It does not cleanly model multiple runs inside one persistent session.
It also does not enforce that an explicitly supplied `SessionState.session_db`
matches `log.session_db`.

The next design step is therefore not “make Blackboard and EventLog use one DB”
in the abstract. It is:

```text
use the accepted Option A session lifetime
→ bind session_id to workspace and persistent Blackboard
→ bind run_id to one execution trace
→ define EventLog's scoped reader/writer API
→ choose the exact Option A path/manifest layout
```

---

## Accepted subagent direction (DRAFT)

The first subagent capability is now defined as **artifact-only**:

```text
main session workspace:
  read-only to the subagent

subagent artifact directory:
  writable only for this task

result:
  structured JSON envelope + bounded artifacts
```

This mode is intended for cheap stateless tasks such as:

- verifier;
- researcher;
- report generator;
- test runner.

The subagent must not edit the main codebase in this first mode. A future
code-editing mode with a real isolated worktree is deferred and is not part of
the first implementation slice.

This does not mean that `cwd=<artifact-directory>` is enough. A shell command
can still use `..` or absolute paths. The implementation therefore needs an
explicit read/write boundary: the session workspace is an allowed read root,
and the task artifact directory is the only allowed write root. The current
single-root `SandboxHook`/`evaluate_bash` path does not yet express this
boundary, so V24/V25 remain implementation work, not accepted behavior.

---

## Verified present-logic findings added in revision v2

These are not claims copied from old notes. They were checked against the
current source and, where practical, reproduced with a focused probe. They are
candidate work items, not approved implementation decisions.

| ID | Finding | Evidence | Impact | Priority |
|---|---|---|---|---:|
| V1 | Event IDs are allocated by `COUNT(*) + 1`, not atomically by the database. | Two `EventLog` instances constructed for one path, then appended concurrently, produced `['ev-000001', 'ev-000001']` in `session.db`. | Duplicate event IDs make replay/correlation ambiguous exactly when multiple stages or threads share a run. | P0 |
| V2 | `EventLog.kind_counts` advances before the authoritative write. | A focused probe forced `append_event_row()` to raise; `kind_counts` became `{'tool_call': 1}` while `_next_id` stayed `1` and no DB row existed. | In-memory metrics can report events that never committed. | P1 |
| V3 | `EventLog.read_all()` still falls back to JSONL when the DB is empty or unreadable. | A manually populated JSONL beside an empty DB was returned by `read_all()`; a DB read exception is caught and parsed from the mirror. | A correctness reader can silently consume a non-authoritative surface. This is different from the counter fix. | P0 |
| V4 | `Blackboard.read()` and `Blackboard.query()` also fall back to JSONL after authority failure. | A forced `read_blackboard_row()` failure returned the mirror entry and logged only a warning. | Conflict detection and planning can use stale/partial state while appearing healthy. | P0 |
| V5 | Constructing `EventLog` from `fa.stats.parse_session()` creates a new `session.db` beside a legacy JSONL file. | A JSONL-only temp session had no DB before `parse_session()` and an empty DB afterwards. | A read-only derived command mutates the trace directory and changes future session discovery. | P1 |
| V6 | Blackboard writes use `INSERT OR REPLACE` despite append-only/substrate language. | `SessionDatabase.write_blackboard_row()` explicitly uses `INSERT OR REPLACE`; duplicate IDs therefore overwrite prior rows. | History/conflict lineage can be erased without an explicit version transition. | P1 |
| V7 | `SessionDatabase` has no run identity binding in its constructor or read queries. | `EventLog` objects with different `run_id` values on one DB both read both rows. | A path collision or accidental DB reuse can mix sessions while each row still carries a different `run_id`. | P1 |
| V8 | Session initialization has an undocumented fail-open/fallback matrix. | `SessionState.__post_init__()` catches failures for Blackboard, telemetry, worktree, PTY, transaction, and artifact store, then continues with different fallbacks. | Safety-critical and convenience failures are not expressed as one auditable policy; a fallback may change security semantics. | P0 |
| V9 | Workflow aggregate duration is hardcoded to zero. | `_cmd_workflow()` calls global-history export with `duration_ms=0`. | `fa stats --global-history` cannot report workflow wall time even after a successful run. | P1 |
| V10 | `DEFAULT_STATE_ROOT = Path.home() / ...` is evaluated at import time. | `src/fa/inner_loop/state.py:52` binds the home directory before later `HOME` changes. | Tests and embedders that change HOME after import can write/read the wrong session root; runtime configuration is split between import-time and call-time resolution. | P1 |
| V11 | `_cmd_run()` mutates process-global `NO_COLOR`. | `src/fa/cli.py:_cmd_run` writes `os.environ['NO_COLOR']` and never restores it. | Repeated in-process CLI calls can affect later commands/tests; the command root has hidden global state. | P2 |
| V12 | The full pytest suite can leave tracked hook scripts mode-dirty. | After the full suite, `git diff --summary` showed `100755 => 100644` for four `src/fa/hygiene/hooks/*` files. The installer test mutates source executable bits. | Test verification itself pollutes the candidate diff and can hide real changes in an agent workflow. | P1 |
| V13 | Entrypoint clone failure does not immediately terminate setup. | `scripts/fa-entrypoint.sh` logs clone failure, removes the partial directory, then continues to publish/use `SESSION_DIR`. | Auto-run and command-override behavior after failed workspace creation is not a single explicit state; failure classification is deferred to later checks. | P1 |
| V14 | Debug-body rows do not contain a complete transport outcome schema. | `DebugBodyTransport._write()` records request/response bodies, provider, slug, attempt and logical ID, but not URL, HTTP status, network error, or transport name. | A body row can prove payload content but cannot alone explain a failed/empty response attempt. | P2 |
| V15 | `edit_file` writes the file without a pre-write Blackboard conflict check. | `edit_file.py` calls `_write_blackboard_entry()` only after `path.write_text()`; unlike `write_file.py`, it has no `detect_conflict()` call. A focused probe with an existing conflicting Blackboard row changed the file and returned success. | The formal read/write conflict contract is asymmetric: edits can bypass stale-read protection while still producing a post-write audit row. | P0 |
| V16 | `SessionState` does not reject an explicitly supplied `session_db` that differs from `log.session_db`. | `__post_init__()` only fills `self.session_db` when it is `None`; it does not assert identity when both are supplied. | A caller can create a state whose EventLog and Blackboard write to different authorities. | P0 |
| V17 | Wrong-root/missing Blackboard conditions are treated as “ignore conflict, continue mutation.” | `write_file._check_conflict()` and edit helpers return/continue on root mismatch or Blackboard errors; a mutation can proceed without formal conflict proof. | Context leakage or authority failure degrades into unguarded writes instead of a deterministic deny. | P0 |
| V18 | Subagent workspace creation falls back to the main workspace after failure. | `SessionState.create_subagent_workspace()` returns `self.workspace_root` after a manager failure. SharedDir is accepted only as an intentional read-root choice for the artifact-only mode; it is not permission to write the main workspace. | A workspace-manager failure can silently turn an artifact-only task into a main-workspace mutator. | P1 / intent confirmed, enforcement gap |
| V19 | `worktree_mode=isolated` is accepted then downgraded to shared with a stdout warning. | `WorktreeManagerFactory.from_flags()` prints a warning and returns `SharedDirWorktreeManager` for `isolated`. | The first artifact-only mode does not need isolated code editing; therefore `isolated` should be explicitly unsupported until a real isolated mode is implemented, not downgraded. | P0 / confirmed configuration-truth gap |
| V20 | Subagent cleanup failure is swallowed while the tool may still report success. | `SessionState.cleanup_subagent_workspace()` logs and returns; `spawn_subagent` continues to completion/result handling. | Orphaned worktrees/session state can accumulate, and a successful envelope can hide a failed cleanup boundary. | P1 |
| V21 | Subagent spawn-limit counter failure is best-effort and can permit repeated spawns. | `SubagentRunner._check_spawn_limit()` catches `increment_subagent_spawns()` errors, logs, and returns success from the guard path. | A safety/resource limit can silently stop enforcing after one counter failure. | P0 |
| V22 | Spawn-limit check and increment are not one atomic admission operation. | `_check_spawn_limit()` reads `session.subagent_spawns`, compares it, then increments through a separate call; concurrent spawn requests can both pass the same limit. | A configured concurrency/resource cap can be exceeded even when the counter itself is thread-safe. | P1 |
| V23 | Live `EventBus` payloads carry raw model text/tool params while durable `EventLog` content is redacted. | `coder_loop.py` sends `response.text` and `dict(call.params)` directly in `OutputEvent`; `ConsoleRenderer` prints model text for verbose/debug. | Redaction coverage differs by sink; an operator/debug path can expose values that the durable redacted trace does not. | Deferred by operator decision |
| V24 | `fs.spawn_subagent` describes an isolated, role-bounded tool but accepts an arbitrary shell command and can receive `SharedDirWorktreeManager`. | `build_spawn_subagent_tool()` declares `permission="workspace"`; `SubagentRunner.run_stateless()` calls `subprocess.run(..., shell=True, cwd=workdir)`; the v0.1 factory returns `SharedDir` even when isolation is requested. | This contradicts the accepted artifact-only contract until writes are restricted to the task artifact directory. | Confirmed implementation gap |
| V25 | The `SandboxHook` evaluates `fs.spawn_subagent` against the parent `workspace_root`, not a subagent-owned write root. | `SandboxHook.handle()` routes `fs.spawn_subagent` through `evaluate_bash(... workspace_root=self.workspace_root, allow_general_write=True)` before `SubagentRunner` chooses `workdir`. | The current gate and executor do not share the accepted artifact-only read/write boundary. | Confirmed implementation gap |
| V26 | The entrypoint currently uses `FA_RUN_ID` as the session workspace identity. | `scripts/fa-entrypoint.sh:150-151` sets `SESSION_ID="${FA_RUN_ID:-...}"` and exports the same value as `FA_RUN_ID`; the accepted model requires a stable `session_id` plus a new `run_id` per invocation. | Multiple runs cannot be represented cleanly inside one persistent session without separating the two identities at the entrypoint/CLI boundary. | Confirmed lifecycle gap |

### Plain interpretation

The most dangerous discovery is not the original F-01 warning by itself. It is
the combination:

```text
multiple EventLog instances
+ COUNT(*) + 1 allocation
+ no UNIQUE(event_id)
+ workflow/shared run paths
= duplicate correlation IDs are possible
```

The second dangerous combination is:

```text
SQLite authority read fails or is empty
+ EventLog/Blackboard silently read JSONL
+ caller continues
= the operator sees a successful-looking stale state
```

The third is verification hygiene:

```text
full pytest
→ source hook mode mutation
→ dirty git diff
```

The fourth is write-path asymmetry:

```text
write_file: conflict check → write → Blackboard record
edit_file: write → Blackboard record
```

So a green test for `write_file` does not prove the `edit_file` safety path.
That is exactly the kind of path/matrix gap the plan must close.

The isolation equivalent is:

```text
subagent worktree creation fails
→ current code falls back to main workspace
→ tool still has a path to mutate
```

For a coding agent, that is not a harmless convenience fallback. It changes the
permission boundary and must be treated differently from a missing analytics
artifact.

There is a related configuration truth problem:

```text
worktree_mode=isolated
→ warning printed to stdout
→ SharedDirWorktreeManager returned
→ runtime is not isolated
```

The correct future contract is either “isolated is not an accepted v0.1 value,
so config fails before execution” or “isolated is implemented and verified.” A
truthy warning followed by a weaker security mode is not an acceptable third
state.

That means “tests passed” is not yet equivalent to “the worktree remained
trustworthy” or “all mutating tools obey the same authority contract.” The
updated plan therefore treats allocator correctness, read-fallback semantics,
initialization policy, mutation-path symmetry, isolation failure, and test
isolation as first class substrate contracts before optimizing or extracting the
CLI.

These findings expand S3/S5/S6/S9 and add CT9–CT11. They do not authorize
fixing all eighteen findings in one PR.

## High-ROI improvements discovered outside the original plan

These are ranked by diagnostic leverage per unit of change, not by novelty.
They are candidates for approved slices; none is an automatic implementation
instruction.

| Rank | Improvement | Why it is high ROI | First gate |
|---:|---|---|---|
| 1 | Database-serialized event identity | Prevents duplicate trace correlation IDs under workflow/concurrent writers; one fix protects every consumer. | S5 / CT9 |
| 2 | Explicit authority reader boundary | Removes the most dangerous “looks healthy” failure: stale JSONL returned after DB failure. | S5 / CT10 |
| 3 | One failure-policy matrix | Converts dozens of broad catches/fallbacks into deliberate fail-closed/fail-open contracts. | S3 / CT10 |
| 4 | Run provenance/attestation | Persist source revision, image revision, mount mode, config hash, and harness version in `session_meta`; this answers “what actually ran?” before debugging behavior. | S4 / CT2/CT8 |
| 5 | Trace-health summary | Count authoritative rows, mirror rows, mirror failures, listener failures, and debug-body rows without exposing bodies. It lets an operator detect an incomplete trace immediately. | S7 / CT2/CT3/CT5 |
| 6 | Correlation across durable/live/provider traces | Add a deliberate correlation contract between `run_id`, event identity, tool call ID, logical provider call ID, and EventBus output; today these are not one uniformly queryable key. | S6/S7 / CT3/CT5/CT9 |
| 7 | Clean-worktree verification gate | Prevents the test harness itself from creating false diffs, as the hook-mode mutation demonstrated. | S3 / CT11 |
| 8 | Workflow projection accuracy | Fix/verify duration, turns, role, route, and update-time fields before building more workflow UX. Bad analytics corrupts the next debugging session. | S8/S9 / CT6 |
| 9 | Schema version and migration check | `CREATE TABLE IF NOT EXISTS` is not a migration strategy. A persisted DB must expose compatible schema version or fail with an actionable diagnostic. | S5 / CT2 |
| 10 | CLI extraction only after behavior freeze | A verified command map makes extraction safe; doing it first only relocates hidden coupling. | S10 / CT1 |
| 11 | Tail/count query API | After authority semantics are stable, replace repeated full `read_all()` scans with DB-side count/tail queries. This is an efficiency win, not a substitute for correctness. | S9 / CT2 |
| 12 | Environment/path resolution discipline | Resolve `HOME`, `NO_COLOR`, run roots, and config paths at the process boundary; avoid import-time/global mutation hidden inside command roots. | S3/S7 / CT1/CT11 |

### Plain explanation of the highest-leverage idea

A useful formal substrate is not “many logs.” It is a chain of the same fact:

```text
one run
→ one authority identity
→ one event identity
→ durable DB row
→ optional JSONL mirror
→ optional live EventBus projection
→ optional provider/body projection
→ derived stats
```

If those layers cannot be joined and their failure states cannot be told apart,
more logging makes debugging worse: it creates more artifacts without proving
which one is true. The plan therefore prioritizes identity, authority, failure
policy, and provenance before adding new trace files or new CLI commands.

## 0. Executive intent

### IDEA

Rebuild a verified operational map of the First-Agent CLI and its formal trace
substrate before repairing code. Then harden the system as small vertical
slices, each with explicit authority, producer/consumer, path/matrix, and
negative-proof verification.

### PROJECT MEANING

In the CLI/runtime subsystem, this means turning the current collection of
working modules, mirrors, controller artifacts, and console signals into a
traceable contract graph:

```text
operator/container invocation
→ entrypoint/session workspace
→ argparse command root
→ session state/bootstrap
→ SQLite authority + JSONL mirror
→ EventBus live output
→ provider/tool/hook execution
→ workflow/stat projections
→ operator-verifiable artifacts
```

This belongs in the formal substrate because the project's purpose is not only
to run an agent; it is to make state queryable, versioned, inspectable, and
cheap to debug without re-reading an entire opaque conversation.

### GOALS

- **G1 — CLI root map:** every shipped command and its entrypoint, input,
  side-effect, output, exit-code, and artifact contract is documented and
  source-verified.
- **G2 — Trace source of truth:** every state/trace surface is classified as
  authority, mirror, derived projection, or standalone artifact; no plan step
  may call a mirror an authority.
- **G3 — Liveness audit:** every product claim has an L0–L3 status and every
  observable signal has producer, consumer, path inventory, and verification.
- **G4 — First vertical slice:** make direct-container `fa run` the first
  production acceptance path, including fresh/resume, DB/JSONL, EventBus,
  provider/proxy boundary, debug bodies, redaction, and operator metadata.
- **G5 — Incremental hardening:** after G1–G4 are approved, close authority,
  EventBus, Blackboard, workflow, stats, and deployment gaps in dependency
  order, not as another monolithic PR.
- **G6 — Context economy:** leave each future session with a small durable
  map and a bounded next slice, so the agent does not re-derive the whole
  architecture or flood the context with low-value trace noise.
- **G7 — Event identity correctness:** make event identity unique, monotonic,
  run-bound, and safe when more than one writer/`EventLog` instance exists.
- **G8 — Explicit failure policy:** separate authority failure, mirror failure,
  derived-artifact failure, and convenience fallback; no critical path may
  silently change its source of truth.
- **G9 — Verification hygiene:** the test/contract suite must be isolated,
  deterministic, and leave no tracked source mode or content mutations behind.
- **G10 — Deployment truth:** a direct container acceptance run must identify
  the code/image/mount/env tuple that actually produced its artifacts.

### NON-GOALS

- No immediate rewrite/extraction of the 2,600-line `src/fa/cli.py`.
- No host-wrapper forwarding change in `scripts/fa`.
- No WebUI implementation or API server implementation.
- No provider adapter redesign, new provider family, or cross-model fallback.
- No new EventType universe or discriminated-union migration in the first
  substrate slice.
- No parallel-agent/debate/DAG expansion.
- No automatic production deploy, commit, or push as part of plan execution.
- No claim that the existing full pytest suite equals production verification.
- No acceptance of old audit “SHIPPED” labels without current source and
  negative-proof verification.

### INTENT

Code and deployment verification must make it impossible to call a CLI/runtime
surface “production-ready” when only a consumer, unit helper, mirror, or fake
provider path has been tested. A claim reaches “verified” only when the real
composition root produces the expected durable/live artifact and a producer
kill-check fails when that producer is removed.

### MECHANISM SKETCH

First map `main()`/`build_parser()` and each command root. For the selected
vertical slice, drive the real `fa run` root with fake provider I/O in Pyramid A,
then execute the same command directly inside the deployed container with a
controlled run-id. Read only metadata/counts from `/home/fa/.fa/session-log/<run-id>/`.
Use `session.db` for correctness, JSONL/EventBus/debug-body files for explicitly
named mirrors or operator surfaces, and record every mismatch as a structured
gap rather than silently falling back.

### PROOF SKETCH

The proof root is first `cli:_cmd_run`, then the direct container entrypoint.
Primary oracles are SQLite rows, exit codes, structured output events, provider
call counts, and file existence/counts. For every new/changed signal, remove its
production producer and rerun the named C1/C2 test; the test must fail.

### SIZE

L — deliberately split into independently reviewable slices.

---

## 1. Non-goals and minimal-mechanism check

### 1.1 Why not rewrite `cli.py` first?

`build_parser()` and command roots are all in `src/fa/cli.py`, but extraction
before a behavior map would move uncertainty rather than remove it. The first
mechanism is an executable map plus contract tests. Extraction is allowed only
when a repeated seam is proven by the audit and a named consumer/test exists.

### 1.2 Why not fix every old gap immediately?

The repository already contains multiple prior plans with claims such as
“all implemented,” while current source and tests show mixed liveness. A single
large cleanup would recreate the failure mode the project is trying to remove:
partial implementation marked complete. The smallest honest mechanism is:

```text
map → baseline → one vertical slice → negative proof → next slice
```

### 1.3 Backup and rollback

The current uncommitted candidate patch is not silently discarded. It is
preserved outside the repo with base SHA, status, file list, size, and SHA-256.
No candidate change is accepted merely because its local tests pass.

---

## 2. Current state → target state

### 2.1 CLI topology

**AS-IS (source-verified):**

- `main()` builds one argparse parser and dispatches through `func`.
- 11 command roots live in one `cli.py`.
- `_cmd_run` is a large orchestration root that resolves task/config/secrets,
  builds provider chains, creates registries/hooks/state/output, and calls
  `drive_session`.
- `_cmd_workflow` is a controller that invokes staged `_cmd_run` calls and
  persists `flow_state.json`/`eval_report.json`.
- `inner-loop-smoke` is a deterministic registry/hook smoke path, not the
  LLM production path.
- `fa stats` is a derived reader, not hot-path authority.

**TO-BE (machine-checkable):**

- A CLI topology map exists with one row per command root and one row per
  composition boundary.
- `fa run` and `fa workflow` boundaries are explicit and tested separately.
- Every command has a documented exit-code and artifact contract.
- No implementation step relies on “the CLI” as an unnamed component.

### 2.2 State and trace topology

**AS-IS:**

- `session.db` is currently created in a per-run-shaped path for
  event/blackboard/meta data, but the accepted target is one physical DB per
  persistent `session_id` with run-scoped event rows.
- `events.jsonl` is a human-readable event mirror but legacy readers still
  contain compatibility fallback behavior.
- `EventBus` is ephemeral stderr output with `ConsoleRenderer` or
  `QuietRenderer` consumers.
- `llm_bodies.jsonl` is opt-in raw body capture with redaction and no normal
  production consumer beyond operator forensics.
- `flow_state.json` and `eval_report.json` are workflow controller artifacts.
- `attempt_history.json`, `pr_draft.md`, telemetry JSONL, and global-history DB
  are separate artifacts/projections with different authority.
- Blackboard may be constructed standalone or injected with a session DB;
  production session ownership and cross-run persistence are not yet closed.

**TO-BE:**

Every surface is assigned exactly one role:

```text
AUTHORITY:
  one approved session-authority DB per persistent session for hot-path
  event/blackboard/meta state; exact path is frozen by S1

MIRROR:
  events.jsonl, optional debug-body JSONL, optional blackboard JSONL

LIVE DISPLAY:
  EventBus → ConsoleRenderer/QuietRenderer

CONTROLLER TRUTH:
  flow_state.json / eval_report.json for workflow state and verdict

DERIVED PROJECTION:
  global_history.db / stats output / telemetry analytics

STANDALONE ARTIFACT:
  pr_draft.md / attempt_history.json / eval reports where explicitly owned
```

The final mapping must be verified against code and tests, not only written in
docs.

### 2.3 Liveness target

No surface is called shipped in the plan until its relevant target is L3:

- source producer exists;
- real composition root reaches it;
- structured artifact/signal is observed;
- consumer or operator path is verified;
- producer removal makes verification fail;
- all applicable path/matrix rows are covered or explicitly deferred.

---

## 3. Contracts

### CT1 — CLI dispatch and command-root contract

**Scope:** `src/fa/cli.py:build_parser`, `main`, and each `_cmd_*` root.

**IN:** argparse argv plus command-specific environment/config.

**OUT:** integer exit code; command-specific stdout/stderr; named artifacts.

**ERRORS:** malformed argv/config returns documented non-zero code; unexpected
runtime errors must not be silently converted into success.

**SIDE EFFECTS:** command-dependent; each must be listed in the CLI map.

**PRODUCER:** `set_defaults(func=...)` in `build_parser` selects the command
root.

**CONSUMER:** `main()` invokes `func(args)` and raises `SystemExit` with the
returned code.

**KILL-CHECK:** remove the relevant `set_defaults(func=...)` or command-root
invocation; the command C2 test must fail.

### CT2 — Session authority and run-scoped trace contract

**Scope:** `SessionDatabase`, `EventLog`, `SessionState`, Blackboard DI,
`session_id`, and `run_id`.

**Logical ownership:**

- `session_id` owns the persistent workspace, Blackboard, and session metadata;
- `run_id` owns one `fa run` / `fa workflow` execution trace;
- every event row carries the `run_id` that produced it.

**Physical DB shape:** Option A is accepted: one DB per persistent session
with session-scoped Blackboard/meta rows and run-scoped `event_log` rows. S1
freezes the exact path, manifest, indexes, and migration disposition.

**Schema:** `event_log`, `blackboard`, `session_meta`, plus explicit scope and
schema-version metadata.

**POST:** authoritative DB write is committed before logical event state is
advanced; mirror failure is separately observable; authority failure is not
silently accepted as a successful event write.

**READ:** current machine reads use the DB SSOT. The existing `fa stats` read
surface formats DB data for humans. In the first implementation, old JSONL/old
per-run DB artifacts are explicitly unsupported; no legacy reader, hidden
fallback, or automatic migration is allowed.

**PRODUCER:** `SessionDatabase.__init__`, event allocator/insert,
`append_event_row`, `write_blackboard_row`, `set_meta`.

**CONSUMERS:** run-scoped `EventLog`, session-scoped `Blackboard`,
`SessionState`, `coder_loop`, `loop.py`, observability tools, `fa stats`, and
global-history exporter.

**KILL-CHECK:** remove the authoritative DB write or replace it with mirror-only
write; the authority failure/split-brain test must fail. Remove `run_id` query
scoping; the run-isolation test must fail.

### CT3 — EventLog/EventBus observable-signal contract

**EventLog producer:** `log.append(kind=...)` at all runtime paths.

**EventBus producer:** `output.emit(OutputEvent(...))` at all kinds in
`CONSOLE_MIRROR_KINDS` and all live progress events.

**Consumers:**

- EventLog rows → `SessionDatabase`, `fa stats`, observability tools, global
  history, and operator forensic readers.
- `OutputEvent` → `EventBus` → `ConsoleRenderer`/`QuietRenderer`.

**DUAL-WRITE:** required only for the explicitly enumerated console-mirror
subset; audit-only kinds must not be falsely required to have a live display.

**KILL-CHECK:** remove the producer `log.append`/`output.emit` at the exact
path; its C1 test must fail. Removing only a renderer handler must fail the
paired consumer test.

### CT4 — Blackboard conflict and session ownership contract

**Target policy:** a production Blackboard belongs to `session_id` and persists
across runs attached to that session. It must use the approved session
authority shape from Q1. A standalone constructor is either explicitly
test-only/legacy or must require an explicit session authority; it must not
silently create a second production authority.

`EventLog` has a different logical scope: it represents one `run_id`. Under
Option A both facades may use one physical session DB while applying different
query scopes. Under Option B they use separate DBs with an explicit
`run_id -> session_id` link and cross-DB failure policy.

**PRODUCERS:** `write_file.py`, `edit_file.py`, and Blackboard write methods.

**CONSUMERS:** conflict detection before mutation; subagent plan queries;
operator/session inspection where applicable.

**KILL-CHECK:** remove the conflict query/write producer; the real write-tool C1
must allow no mutation and must fail its expected authority assertion.

**SECURITY:** include `../`, symlink, wrong-root, wrong-session and missing-
authority adversarial cases where path/session policy is part of the tested tool path.

### CT5 — Debug-body capture contract

**GATE:** exact `FA_DEBUG_LLM_BODIES=1` after strip; `detail=debug` is unrelated.

**PRODUCER:** `_cmd_run` transport wrapping at `src/fa/cli.py:1763` and
`DebugBodyTransport._write()`.

**CONSUMER:** operator forensic protocol reads only metadata/counts from the
current run directory; no normal console rendering of body contents.

**SECURITY:** secret values must not appear in `llm_bodies.jsonl`; redaction
must be verified on the composed CLI path, not only the unit decorator. The
plan must also decide whether live `EventBus` model text/tool params are
redacted or deliberately classified as a trusted operator-only channel; the
current asymmetry is not allowed to remain undocumented.

**KILL-CHECK:** remove wrapper or pass `redactor=None`; C2 must fail. Remove
live-output redaction if it is selected; the corresponding C2/C0 consumer test
must fail.

### CT6 — Workflow controller/artifact contract

**PRODUCERS:** `_cmd_workflow`, `_run_stage`, `_write_terminal_state`, and eval
artifact writers.

**CONSUMERS:** controller route logic, `load_flow_state`, `load_eval_report`,
operator inspection, global-history export where explicitly intended.

**SOURCE OF TRUTH:** `FlowState` for controller state; `EvalReport` for eval
verdict/route; `pr_draft.md` remains narrative only.

**KILL-CHECK:** remove a state/artifact write; the workflow C2 test must fail on
missing/incorrect state or route.

### CT7 — Provider and proxy boundary contract

**PRODUCERS:** `_build_provider_chain`, `ProviderChain.request`, provider
adapters, `Transport.post`.

**CONSUMERS:** `drive_session`, EventLog provider-attempt rows,
`ResponseInfo` consumer, debug-body wrapper, operator output.

**NON-GOAL:** no new provider adapter or fallback policy in the substrate
re-baseline.

**KILL-CHECK:** replace the real provider-chain call with a bypass; composed
C2 test must fail to observe expected attempt/correlation data.

### CT8 — Deployment topology contract

**PRODUCERS:** `docker-compose.fa.yml`, `Dockerfile.fa`,
`scripts/fa-entrypoint.sh`, direct `docker compose exec` invocation.

**CONSUMERS:** running container process, bind-mounted state, operator
metadata/count inspection.

**INVARIANT:** core code refers to `/home/fa/.fa/session-log/<run-id>/`; host
`/srv/first-agent/state` is deployment topology, not an application path.

**KILL-CHECK:** remove the direct-container env/command or point inspection at
host topology; deployment acceptance must fail.

### CT9 — Event identity and run-binding contract

**IN:** an append request from one logical run.

**POST:** the database, not an in-memory `COUNT(*) + 1`, allocates the event
identity atomically. The chosen representation must guarantee uniqueness for
concurrent writers and define whether gaps are acceptable after a failed
attempt. `event_id` must be unique or the database must expose a stronger
canonical row identity to every consumer.

**RUN BINDING:** a session authority opened for `session_id=A` must not
silently serve `session_id=B`. Within a shared session DB, an `EventLog`
opened for `run_id=A-1` must not return rows for `run_id=A-2`. Either the DB
path is structurally bound to one session and validated, or every authority
query is explicitly scoped by `session_id` and/or `run_id`.

**PRODUCER:** the authoritative event insert/allocator in
`src/fa/inner_loop/session_db.py`.

**CONSUMERS:** `EventLog`, `read_all()`, stats, global history, audit tools,
workflow aggregate readers.

**KILL-CHECK:** concurrent append test must fail if allocator is replaced by
`COUNT(*) + 1`; run-mixing test must fail if query binding is removed.

### CT10 — Authority failure-policy contract

Every fallback boundary must be classified:

| Boundary | Required default |
|---|---|
| `session.db` initialization/write/read for correctness | fail closed, structured error |
| JSONL mirror write | best effort, warning, never authority |
| old JSONL/old per-run DB in first format | explicit unsupported/legacy diagnostic; no DB creation and no automatic migration |
| Blackboard authority read/write | same policy as EventLog; no silent mirror substitution |
| EventBus/renderer failure | preserve durable state, surface operator warning/diagnostic |
| telemetry/artifact analytics | derived best effort, explicit warning |
| PTY unavailable | fallback only if stateful-shell contract remains explicit and tested |
| worktree isolation unavailable | fail closed for mutating/isolated paths; no silent shared-dir downgrade |
| feature flag load | per-flag safety matrix, not one global catch-all |

**PRODUCERS:** `SessionState.__post_init__`, EventLog/Blackboard readers and
writers, PTY/worktree factories, EventBus.

**CONSUMERS:** CLI exit path, tool result, operator stderr, session DB rows,
stats/diagnostics.

**KILL-CHECK:** force each boundary failure and assert the documented outcome;
a warning-only test is insufficient for a safety-critical path.

### CT11 — Verification hygiene contract

The verification command must be hermetic with respect to the repository:

- tests may mutate only `tmp_path`/temporary fixtures;
- executable mode of shipped hook sources must be restored or never mutated;
- `HOME`, `PATH`, `NO_COLOR`, and environment overrides must be scoped;
- a full verification run must not create untracked runtime artifacts in the
  source checkout or change tracked file modes.

**PRODUCER:** test fixture/helper/installer under test.

**CONSUMER:** `git status --short`, CI workspace, next agent session.

**KILL-CHECK:** run the full gate from a clean worktree and assert clean status
except for explicitly pre-existing candidate files.

---

## 4. Path and flag matrix

### 4.1 CLI/path inventory

| ID | Path | Root | Current evidence | Planned verification |
|---|---|---|---|---|
| P1 | fresh single-role run | `_cmd_run` | local fake-transport tests; live operator run reported | C2 + direct container |
| P2 | resume same run-id | `_cmd_run`, `EventLog` | unit tests for IDs/draft; no full live resume | C1/C2 + metadata |
| P3 | no explicit run-id | `_cmd_run` / entrypoint | parser code; must verify generated ID and path | C2 + container |
| P4 | debug disabled | `_cmd_run` | unit/C2 matrix | C2, no body file |
| P5 | debug enabled | `_cmd_run` | candidate C2 + operator evidence | C2 + container, counts only |
| P6 | provider success | `ProviderChain.request` | adapter/CLI fake tests | C1/C2 |
| P7 | transient provider fallback | `ProviderChain.request` | provider-chain tests | C1 with attempts/cooldown |
| P8 | provider auth failure | `ProviderChain.request` | provider tests | C1 with chain behavior |
| P9 | request-shape fast-fail | `ProviderChain.request` | provider tests | C1 with no sibling retry |
| P10 | max-turn stop | `drive_session` | CLI test exists | C1/C2 with stop reason |
| P11 | hook deny before mutation | `_cmd_run` + hooks | CLI tests exist | C2 with DB + stderr dual-write |
| P12 | context budget no compaction | `drive_session` | focused tests exist | C1 path inventory |
| P13 | context budget with compaction | `drive_session` | focused tests exist but matrix must be re-audited | C1 matrix B |
| P14 | console output | `EventBus` + `ConsoleRenderer` | renderer/event tests | C1 producer + C0 consumer |
| P15 | quiet output | `QuietRenderer` | CLI tests partially cover | C2 stdout/stderr contract |
| P16 | workflow linear | `_cmd_workflow` | `test_cli_ergonomics.py` | C2 artifact and exit contract |
| P17 | workflow repair | `_run_repair` | offline role-aware tests | C2 budget/route matrix |
| P18 | workflow adaptive | `_run_adaptive` | offline tests | C2 planner re-entry matrix |
| P19 | deterministic smoke | `_cmd_inner_loop_smoke` | multiple C2 tests | C2 canonical artifact path |
| P20 | stats current run | `_cmd_stats` / `parse_session` | stats tests | C2 fresh production trace |
| P21 | global-history projection | `_cmd_stats` / exporter | dedicated tests | C2 workflow accuracy |
| P22 | blackboard read/write | `SessionState` + tools | unit/C1 tests | C1 same-DB authority and adversarial paths |
| P23 | entrypoint auto-run | `fa-entrypoint.sh` | shell tests | controlled container test |
| P24 | direct exec command override | `fa-entrypoint.sh` | shell tests | controlled container test |
| P25 | concurrent EventLog writers | `EventLog` + `SessionDatabase` | no current race proof | C1 stress test |
| P26 | DB read failure with mirror present | `EventLog.read_all` / `Blackboard.read/query` | fallback behavior exists | C3 policy test |
| P27 | old JSONL/old DB stats read | `stats.parse_session` | clean-cutover policy | C2 unsupported/no-write test |
| P28 | failed session clone | `fa-entrypoint.sh` | source path logs and continues | shell negative test |
| P29 | test-suite clean-worktree invariant | hygiene hook installer tests | current full suite can dirty modes | post-suite status gate |
| P30 | reused DB with different run-id | `SessionDatabase` / `EventLog` | rows are not query-filtered by run-id | C1 identity-isolation test |
| P31 | default new session | CLI/entrypoint session creation | session selector contract not implemented | C2 session lifecycle test |
| P32 | explicit existing session | CLI/entrypoint + workspace resolver | proposed flag not implemented | C2 attach/resume test |
| P33 | multiple runs in one session | `_cmd_run` / `_cmd_workflow` | persistent session model not implemented | C1 session/run scope test |

### 4.2 Flag/provider matrix

| ID | Configuration | Proves | Planned slice |
|---|---|---|---|
| A | `FA_DEBUG_LLM_BODIES=0`, standard output, provider success | default safe path | S7 |
| B | `FA_DEBUG_LLM_BODIES=1`, provider success | opt-in capture + redaction | S7 |
| C | `detail=debug` with env disabled | debug rendering is not body gate | S7 |
| D | `--output-mode quiet` | no live renderer noise, final output remains defined | S7 |
| E | compaction disabled | context warning/stop path | S6 |
| F | compaction enabled | full context/compaction signal matrix | S6 |
| P-openai | OpenAI-compatible adapter | canonical request/response + attempts | S7 |
| P-anthropic | Anthropic adapter | native request/response projection | later provider slice |
| P-proxy | egress proxy mode | no key in agent; proxy route works | S7 deployment |
| P-legacy | direct key-store mode, if still supported | explicit compatibility only | Q4 / later |
| F-authority | DB init/read/write failure | fail-closed and structured | S5 |
| F-mirror | JSONL mirror failure | DB remains correct; warning is observable | S5/S7 |
| F-blackboard | Blackboard DB read/write failure | no stale mirror success | S5/S6 |
| F-pty | PTY missing/timeout | explicit fallback or fail policy | S3/S5 |
| F-worktree | worktree isolation failure | no silent shared-dir mutation path | S5 |
| F-env | host env only vs `docker compose exec -e` | actual process sees intended flag | S4/S7 |

No matrix row may be marked covered by naming only; each row needs a named test
or an explicit N/A decision.

---

## 5. Step-by-step implementation plan

> Steps are ordered so that discovery and contracts precede code. Steps S0–S3
> may produce plans/reports/tests only; they must not silently change runtime
> behavior.

### Step S0: Preserve and isolate the candidate diff

Traces-to: G5, CT1–CT8.

Depends-on: none. Parallelizable-with: none.

Target liveness: candidate preservation, not product liveness.

Edit/artifact:

- `/home/user/backups/First-Agent-dev-20260725Tcandidate-diff-from-3668e758c1522645a1bfb70787ebf53f7ef170a7.patch`
- matching `.meta.txt` file.

Do:

1. Verify patch SHA-256 against the metadata file.
2. Verify candidate diff applies cleanly to base in a disposable worktree.
3. Compare candidate files against this plan's approved artifact inventory.
4. Keep the current worktree uncommitted until plan approval.

Do-not:

- do not treat candidate green tests as approval;
- do not deploy candidate code;
- do not silently fold candidate changes into later slices.

Exit criteria:

- [x] backup exists;
- [x] base SHA recorded;
- [x] patch SHA recorded;
- [ ] disposable apply check recorded.

### Step S1: Review and freeze the CLI/source-of-truth contract

Traces-to: G1, G2, G6, CT1–CT8.

Depends-on: S0. Parallelizable-with: none.

Target liveness: architecture map L0→L3-ready.

Edit/artifact:

- `worklogs/implementation-plans/PLAN-cli-trace-S1-session-lifecycle.md`;
- `worklogs/implementation-plans/cli-trace-S1-verification-report.md`;
- `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`
  only after S1 evidence is complete;
- later, only after approval, a compact CLI codemap under
  `knowledge/codemaps/` if the operator agrees it is an active consumer.

Do:

1. Record the accepted order: direct-container `fa run` is the first
   production acceptance root; `fa workflow` is the second.
2. Freeze the accepted logical identity model:
   `session_id` = persistent workspace/Blackboard identity;
   `run_id` = one run/workflow trace;
   `event_id` = one event.
3. Record the accepted Option A direction: one physical DB per session with
   session-scoped Blackboard/meta and run-scoped event rows.
4. Resolve Q10: session selector flag, default session creation, workspace
   resolution, manifest/path layout, run binding, and migration.
5. Preserve the accepted Q2 clean-cutover read semantics before changing code.
6. Confirm whether all 11 commands are in this program or whether the plan is
   intentionally staged by command family.
7. Freeze the authority table and CLI boundary table in the approved plan.

Do-not:

- do not extract code from `cli.py` yet;
- do not add a new `workflow inspect` command;
- do not alter wrapper behavior.

Exit criteria:

- [x] operator approved direct-container `fa run` before `fa workflow`;
- [x] operator accepted the logical session/run identity model and Option A direction;
- [x] operator selected clean-cutover DB-only reads;
- [x] Q10 manifest/path/entrypoint implementation contract is frozen by S1;
- [x] no plan step contains an unowned policy choice for S2.

### S2 plan-review correction record — 2026-07-27

The READY subplan was reviewed against the current source before runtime work.
The following corrections are now authoritative for S2:

- authority schema/open/reservation is established before `begin_run()` tests;
- workflow uses one `run_id` per top-level invocation, shared by internal stages;
- `fa stats` uses Candidate A manifest/DB discovery and a read-only existing-DB
  API; `_cmd_stats` wiring is explicitly in S2 scope;
- `--workspace` preserves `None` versus an explicit path;
- new sessions reject workspaces already owned by another manifest and handle
  provisioning failure explicitly;
- S2 claims injected authority only for `fa run`/`fa workflow`; direct
  constructors used by tests/legacy helpers remain outside that production
  claim and are never used by `fa stats`.

Evidence and detailed file/symbol instructions are in:
`worklogs/implementation-plans/PLAN-cli-trace-S2-session-manager-and-authority.md`
(Revision v2, PR-S2-1 through PR-S2-6).

### Step S2: Implement SessionManager and session-authority wiring

Traces-to: G1, G2, G4, G5, CT1, CT2, CT4, CT6, CT8, CT9, CT10.

Depends-on: S1. Parallelizable-with: none.

Target liveness: session lifecycle and authority wiring L1→L3 in local C1/C2;
direct deployment verification remains S4/S7.

Implementation authority:

- `worklogs/implementation-plans/PLAN-cli-trace-S2-session-manager-and-authority.md`

Execution shape:

```text
S2.0  baseline/source guard
S2.1  authority bootstrap seam + SessionManager + manifest
S2.2  --session-id and fresh run identity through fa run/workflow
S2.3  entrypoint integration with one logical session owner
S2.4  session DB/EventLog/Blackboard scope wiring
S2.5  DB-only fa stats clean cutover
```

S2.0 must pass before runtime edits. S2.1 must establish the session schema,
read-only-open path, and atomic run-binding reservation before manager lifecycle
claims are tested. S2.1 must pass before S2.2. S2.2/S2.3 must pass before S2.4.
S2.4 must pass before S2.5.

Identity rule corrected during S2 plan review:

```text
one top-level fa workflow invocation → one new run_id
internal workflow stages reuse that run_id in S2
no per-stage run IDs or new workflow_id are introduced in this slice
```

This preserves the accepted `run_id` meaning and the existing workflow artifact
namespace; a different stage-ID model requires a separate policy decision.

Allowed source/test files are listed in the S2 subplan. No host wrapper,
provider adapter, EventBus redaction, or subagent implementation is in scope.

Do:

1. Follow the S2 subplan's per-edit intent, mechanism, failure behavior, test
   class, kill-check, and post-edit reporting contract.
2. Run the source map checkpoint inside S2.0 before changing code.
3. Implement Candidate A: one physical session DB, run-scoped event rows,
   session-scoped Blackboard/meta, and a non-creating read path for stats.
4. Preserve S5 as the later owner of the final atomic event allocator,
   duplicate-ID uniqueness hardening, and remaining mutation conflict policy.
5. Keep clean cutover explicit: old JSONL/old DB artifacts are unsupported and
   are not automatically imported.

Do-not:

- do not implement S2 as a second per-run DB model;
- do not silently retain the old `FA_RUN_ID == SESSION_ID` behavior;
- do not make `--resume` append to an old run trace;
- do not use JSONL as current-format authority;
- do not edit the host wrapper;
- do not expand into Q11 subagent enforcement.

Exit criteria:

- [x] S2-A lifecycle tests pass;
- [x] S2-B authority/scope tests pass;
- [x] `fa run` and `fa workflow` resolve the same session contract;
- [x] two runs in one session share Blackboard/session DB but have filtered traces;
- [x] two sessions cannot read each other's state;
- [x] old-format stats does not create DB or import JSONL;
- [x] producer kill-checks pass for SessionManager, EventLog scope, and stats
  DB-reader wiring;
- [x] targeted/static/checkpoint gates pass locally;
- [x] main plan, S2 subplan, and S2 verification report contain actual evidence;
- [ ] direct-container production verification remains S4/S7 work.

Evidence:

```text
worklogs/implementation-plans/cli-trace-S2-verification-report.md

local full suite: 2014 passed, 15 skipped
changed-file Ruff/mypy/compile/shell/docs/contracts: PASS
repository-wide Ruff: baseline documentation/noqa findings remain
```

### S3 plan-review record — 2026-07-27

S3 is design/verification-only and is ready for audit execution. The reviewed
subplan explicitly covers:

- B0/C0/S2 source provenance;
- EventType, LogKind, and console-mirror two-sided inventories;
- dynamic producer/context analysis beyond regex checker PASS;
- explicit parent path index P1–P33;
- flag/failure and verification-hygiene matrices;
- residual V1–V26 classification without runtime fixes;
- producer-focused disposable kill-checks;
- direct-container claims remaining pending S4/S7/S11.

Subplan:
`worklogs/implementation-plans/PLAN-cli-trace-S3-liveness-contract-audit.md`

Review report:
`worklogs/implementation-plans/cli-trace-S3-plan-review-report.md`

Review verdict: **PASS — READY FOR AUDIT EXECUTION**. No blocking Q12+.

### Step S3: Run the liveness and contract audit after S2 wiring

Traces-to: G2, G3, G5, CT3, CT4, CT6, CT9, CT10.

Depends-on: S2. Parallelizable-with: none.

Target liveness: inventory all relevant signals at L1–L3 after the session/
authority wiring; no false production claims.

Edit/artifact:

- implementation subplan: `worklogs/implementation-plans/`
  `PLAN-cli-trace-S3-liveness-contract-audit.md`;
- plan review report: `worklogs/implementation-plans/`
  `cli-trace-S3-plan-review-report.md`;
- execution audit report: `worklogs/implementation-plans/`
  `cli-trace-substrate-liveness-audit-2026-07-25.md` (NEW at S3.6).

Do:

1. Enumerate all `EventType` producers and consumers by exact symbol/path.
2. Enumerate all `LogKind` producers and consumers.
3. For each `CONSOLE_MIRROR_KINDS` member, verify both durable and live
   producers occur on the intended path, not merely somewhere in the repo.
4. Compare regex contract-check results with AST/source context; record false
   positives and false negatives.
5. Enumerate path inventory P1–P33 and flag rows lacking a real test.
6. Identify tests that only instantiate consumers or fake the composition root.
7. Run the audit against the base checkout and separately annotate candidate
   patch changes; do not mix statuses.
8. Reproduce V1, V2, V3, V4, V5, V7, V12, V15, V16, V17, V18, V19, V20,
   V21, V22, V23, V24, V25, and V26 with focused probes before proposing fixes. V6, V9, V10,
   V11, V13,
   and V14
   require source-plus-test verification or an explicit reason not to pursue
   them.
9. Add a failure-policy matrix for SessionDatabase, Blackboard, EventBus,
   PTY, worktree, telemetry, artifact store, and feature flags.
10. Inspect the verification suite itself for repository side effects: modes,
    HOME/PATH/NO_COLOR mutation, subprocess state, and generated artifacts.
11. Capture pre/post `git status --short`, `git diff --summary`, selected
    environment variables, and generated files around the full gate. Separate
    the intentional candidate baseline from newly introduced mutations.

Do-not:

- do not add a new contract checker merely because the existing output is
  green;
- do not mark a handler-only test as producer proof;
- do not delete existing tests to make the inventory smaller.

Exit criteria:

- [ ] every signal has producer/consumer status;
- [ ] every path has test status;
- [ ] checker trust limitations are documented;
- [ ] a prioritized gap register exists;
- [ ] first implementation slice is selected from evidence.

Kill-check:

- The audit is invalid if its report remains identical after removing a real
  producer call from a disposable copy. The audit itself must detect that
  producer absence.

### Step S4: Establish the direct-container baseline

Traces-to: G4, CT1, CT2, CT5, CT7, CT8.

Depends-on: S1 and S2. Parallelizable-with: S3 after Q3 default is accepted.

Target liveness: deployed direct `fa run` L2→L3 for metadata/count path.

Edit/artifact:

- no source edit;
- operator-preserved command output and run metadata.

Do:

1. Use direct `docker compose exec -T -e FA_DEBUG_LLM_BODIES=1` inside the
   configured compose file; do not use `scripts/fa`.
2. Use an explicit session selector and explicit run-id once the approved CLI
   flag contract exists. Until then, record the current command shape rather
   than pretending the selector is already implemented.
3. Use a one-turn task selected by the operator.
4. After the run, inspect only:

   ```bash
   docker compose -f /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml exec -T first-agent ls -lh /home/fa/.fa/session-log/<run-id>
   docker compose -f /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml exec -T first-agent wc -l /home/fa/.fa/session-log/<run-id>/events.jsonl /home/fa/.fa/session-log/<run-id>/llm_bodies.jsonl
   ```

5. Query session SQLite metadata/counts inside the container without printing
   body files; inspect the session DB and the per-run trace artifacts separately.
6. Record image revision/source path and whether `/workspace/src` shadowing is
   active for the agent process.

Do-not:

- do not use host `/srv/first-agent/state` as an application path in code;
- do not print `llm_bodies.jsonl`;
- do not treat a successful LLM response as proof of complete trace integrity.

Exit criteria:

- [ ] container command path is recorded;
- [ ] session directory and files are recorded;
- [ ] DB/event/body counts are recorded;
- [ ] source/image revision is recorded;
- [ ] any mismatch is classified before code changes.

### Step S5: Close remaining authority correctness after S2 wiring

Traces-to: G2, G3, G5, CT2, CT4, CT9, CT10.

Depends-on: S2, S3, and S4. Parallelizable-with: none.

Target liveness: authority correctness and mutation safety L2→L3.

Candidate files, subject to plan approval:

- `src/fa/inner_loop/session_db.py`;
- `src/fa/inner_loop/state.py`;
- `src/fa/blackboard/blackboard.py`;
- `src/fa/inner_loop/tools/write_file.py`;
- `src/fa/inner_loop/tools/edit_file.py`;
- `src/fa/inner_loop/subagent_runner.py` only if a remaining authority/resource
  boundary requires it;
- `src/fa/inner_loop/tools/observability.py` only for scoped current-format reads;
- `src/fa/stats.py` only for correctness gaps left after S2's DB-backed reader.

Do:

1. Reproduce the base F-01 ordering defect in a focused test first.
2. Verify S2's session DB path, session/run binding, and scoped reader/writer
   contracts before changing authority internals.
3. Replace `COUNT(*) + 1` with a database-serialized identity allocation
   strategy; compare using the existing `event_log.id AUTOINCREMENT`, an
   explicit sequence/reservation row, and a transaction that returns the
   canonical event identity. Select one only after the concurrency test and
   SQLite behavior are documented.
4. Add a uniqueness/run-binding strategy: reject duplicate `event_id` values
   and prevent one `SessionDatabase` from silently serving multiple run IDs.
5. Decide whether Blackboard duplicate IDs are append-only conflicts or
   explicit version updates; remove accidental `INSERT OR REPLACE` semantics
   if append-only is the contract.
6. Add an explicit schema version/migration check; `CREATE TABLE IF NOT EXISTS`
   alone must not be presented as migration support.
7. Move in-memory counters (`kind_counts` and related rollups) after the
   authoritative commit, or make their speculative state explicit and
   rollback-safe.
8. Make `write_file` and `edit_file` use the same pre-write conflict contract;
   post-write Blackboard logging is not a substitute for pre-write denial.
9. Preserve public facade APIs where possible to reduce caller churn.

Do-not:

- do not blindly apply the current candidate patch;
- do not migrate telemetry/global-history in this slice;
- do not introduce a second session DB under `workspace/.fa/blackboard`;
- do not make JSONL the hidden degraded authority.

Exit criteria:

- [ ] fresh nested run creates schema before count;
- [ ] authority write failure cannot report clean success;
- [ ] mirror failure is observable and does not create mirror-ahead state;
- [ ] Blackboard and EventLog authority identity is verified;
- [ ] mismatched explicit `SessionState.session_db` is rejected or normalized;
- [ ] duplicate/concurrent event identity test is green;
- [ ] run-id reuse/mixing test is green;
- [ ] `kind_counts` cannot advance on a failed authoritative append;
- [ ] write_file/edit_file conflict paths are symmetric with real session state;
- [ ] wrong-root/Blackboard failure paths deny mutating operations;
- [ ] subagent isolation failure cannot fall back to the main workspace;
- [ ] Blackboard duplicate-ID semantics are explicit and tested;
- [ ] clean-cutover unsupported behavior is documented and tested;
- [ ] current-format stats has no DB-creation side effect during read.

Kill-checks:

- remove the authoritative DB write → authority test fails;
- remove same-DB Blackboard injection → tool authority test fails;
- replace database allocation with `COUNT(*) + 1` → concurrency test fails;
- move in-memory counters before commit → failed-append metric test fails;
- restore hidden JSONL fallback → DB-failure policy test fails;
- restore `INSERT OR REPLACE` when append-only is selected → duplicate-ID test fails.

### Step S6: Close EventLog/EventBus two-sided and path-complete contracts

Traces-to: G3, G5, CT3.

Depends-on: S3 and S5. Parallelizable-with: S7 only after CT2 is stable.

Target liveness: observable signals L1/L2→L3 for selected paths.

Candidate files:

- `src/fa/output.py`;
- `src/fa/inner_loop/coder_loop.py`;
- `src/fa/inner_loop/loop.py`;
- `src/fa/inner_loop/state.py`;
- `src/fa/cli.py`;
- `src/fa/inner_loop/tools/spawn_subagent.py`;
- `src/fa/observability/cost_guardian.py`;
- `scripts/check_producer_consumer_contract.py`;
- `scripts/check_log_kind_contract.py`;
- targeted tests under `tests/`.

Do:

1. Build a producer/consumer/path table from exact call sites.
2. Verify `EventBus` listener exception policy and whether a swallowed
   renderer exception is sufficiently observable for operator debugging.
3. Verify dual-write correspondence for the intended mirror subset.
4. Test both happy and failure paths for context budget, compaction,
   hook-deny, provider retry, tool result, subagent, and config warning.
5. Test `ConsoleRenderer` and `QuietRenderer` as separate consumers.
6. Verify dynamic producer forms, especially `spawn_subagent`'s local
   `kind`/`event_type` variables, are not reported as absent merely because a
   regex cannot see a literal at the call site.
7. Verify every swallowed listener/renderer exception has an operator-visible
   diagnostic policy; do not confuse logger output with durable session truth.
8. Replace or strengthen regex checker only where a false positive/negative is
   demonstrated by the audit; do not build a speculative general AST system.

Do-not:

- do not add EventTypes without naming a consumer and active use;
- do not make every audit-only LogKind console-visible;
- do not accept “checker PASS” without a producer mutation test.

Exit criteria:

- [ ] path inventory P11–P14 and P22 is complete;
- [ ] producer C1 and consumer tests are paired;
- [ ] matrices E/F and output modes are covered;
- [ ] checker mutation tests prove the checker catches removed producers;
- [ ] dual-write policy is explicit.

### Step S7: Close the direct `fa run` vertical slice

Traces-to: G4, G5, CT1, CT2, CT3, CT5, CT7, CT8.

Depends-on: S5 and S6. Parallelizable-with: none.

Target liveness: P1–P15 L2→L3, first for local C2 then deployment.

Candidate tests:

- `tests/test_cli.py` for real `_cmd_run` composition;
- `tests/test_session_db_authority.py` for authority identity;
- `tests/test_inner_loop_audit_sink.py` for resume/audit;
- `tests/test_event_type_c1_producers.py` for EventBus producer paths;
- new direct-container verification script/test only if an active consumer is
  approved.

Do:

1. Cover fresh run and resume with explicit run-id.
2. Cover `FA_DEBUG_LLM_BODIES=0/1` and `detail=debug` negative control.
3. Cover body redaction on the composed path.
4. Assert provider call count and exit reason for early failure/authority
   failure.
5. Assert DB event rows and JSONL mirror counts separately.
6. Assert live stderr consumer behavior for standard/quiet/debug output.
7. Record/verify run provenance and trace-health metadata without exposing body
   contents: code/image revision, config hash, DB count, mirror count, capture
   count, and failure counters.
8. Verify correlation joins across `run_id`, event ID, tool call ID, and
   provider `logical_call_id`; document any intentional non-join.
9. Run `fa run` repeatedly in one process with and without `--no-color` and
   with temporary HOME/flags; prove command-local environment state does not
   leak into the next invocation.
10. Run the direct container protocol from S4 against the approved image.

Do-not:

- do not call the wrapper to claim core CLI proof;
- do not inspect only stdout/final model text;
- do not mark the slice L3 based on local fake transport alone.

Exit criteria:

- [ ] P1–P15 matrix rows have explicit verification;
- [ ] local C2 producer kill-checks pass;
- [ ] container run has DB/events/body metadata evidence;
- [ ] redaction evidence exists without exposing raw body contents;
- [ ] source/image drift is ruled out.

### Step S8: Verify workflow as a separate controller surface

Traces-to: G1, G3, G5, CT1, CT6, CT7.

Depends-on: S7. Parallelizable-with: S9 only after artifact authority is clear.

Target liveness: P16–P18 L2→L3.

Candidate files:

- `src/fa/cli.py` workflow roots;
- `src/fa/inner_loop/workflow_artifacts.py`;
- `src/fa/inner_loop/global_history.py`;
- `tests/test_cli_ergonomics.py`;
- `tests/test_workflow_paths.py`;
- `tests/test_global_history_export.py`.

Do:

1. Verify linear, repair, and adaptive modes independently.
2. Verify `FlowState` owns controller truth and `EvalReport` owns verdict/route.
3. Verify `pr_draft.md` remains narrative, not controller truth.
4. Verify repair/replan budgets, role preconditions, terminal states, and
   artifact persistence.
5. Verify aggregate global-history fields from a workflow trace, especially
   turns, role string, duration, and route.
6. Decide whether workflow is part of the first production deployment gate or
   a second gate after direct `fa run`.

Do-not:

- do not add persisted workflow resume semantics without a state-by-state
  transition contract;
- do not add a generic transition engine for elegance;
- do not add inspect/status CLI surface in this slice.

Exit criteria:

- [ ] each workflow mode has a C2 path and negative budget/route cases;
- [ ] artifacts are read back by their real consumer;
- [ ] aggregate projection accuracy is verified;
- [ ] no controller claim relies on PR draft prose.

### Step S9: Verify stats and derived projections

Traces-to: G2, G3, G5, CT2, CT6, CT7.

Depends-on: S5 and S8. Parallelizable-with: S10.

Target liveness: P20–P21 L2→L3.

Candidate files:

- `src/fa/stats.py`;
- `src/fa/cli.py::_cmd_stats`;
- `src/fa/inner_loop/global_history.py`;
- `tests/test_stats.py`;
- `tests/test_stats_global_wiring.py`;
- relevant observability tests.

Do:

1. Verify session discovery uses the intended authority/compatibility path.
2. Verify parser behavior for complete, incomplete, malformed, and DB-only
   traces.
3. Verify compaction, provider attempts, guards, tool errors, recovery, and
   cost events are either parsed or explicitly marked unsupported.
4. Verify global-history is derived and cannot influence hot-path correctness.
5. Verify workflow aggregate duration, turns, role identity, and update time are
   measured from the actual controller run rather than hardcoded defaults.
6. Measure/read-all complexity only after correctness policy is stable.

Do-not:

- do not add typed event-union migration just to remove `dict.get()` calls;
- do not silently change old-session compatibility while changing authority.

Exit criteria:

- [ ] derived consumers agree with authority rows on a fresh trace;
- [ ] malformed/partial traces have deterministic behavior;
- [ ] no derived DB is imported by hot-path correctness code;
- [ ] known unparsed kinds are explicit.

### Step S10: Decide whether CLI extraction is warranted

Traces-to: G1, G6, CT1.

Depends-on: S2, S3, S7, S8, S9. Parallelizable-with: none.

Target liveness: structural refactor only; behavior remains L3.

Candidate files, only if evidence demands extraction:

- `src/fa/cli.py`;
- new command modules under `src/fa/cli/` (NEW only after approval);
- parser/help tests;
- import/topology tests.

Do:

1. Use the verified command map to identify real duplication and seam
   boundaries.
2. Extract one command family at a time, starting with no behavior change.
3. Keep `build_parser()` as the public parser composition root unless a
   replacement has an active consumer and migration test.
4. Preserve exact flags, help registry, exit codes, output streams, and
   artifact paths.
5. Add import-topology and C2 parity tests before deleting old functions.

Do-not:

- do not split `cli.py` because it is large alone;
- do not create a framework/registry abstraction without a repeated consumer;
- do not change CLI UX and module topology in one unreviewed patch.

Exit criteria:

- [ ] old/new command invocations produce equivalent structured outcomes;
- [ ] no command loses its parser/help/exit contract;
- [ ] removed producer/consumer call sites are caught by parity tests;
- [ ] extraction reduces verified coupling rather than moving it.

### Step S11: Controlled deployment and closeout

Traces-to: G4, G5, CT1–CT8.

Depends-on: S7–S10 as selected by approved scope. Parallelizable-with: none.

Target liveness: selected production surface L2→L3.

Do:

1. Human reviews final diff and candidate backup disposition.
2. Build/rebuild the approved image with exact source revision recorded.
3. Verify container health and proxy health separately.
4. Test both environment modes: host-only `FA_DEBUG_LLM_BODIES=1` must not be
   assumed to reach an already-running container; explicit
   `docker compose exec -T -e FA_DEBUG_LLM_BODIES=1` must reach the process.
5. Run direct `docker compose exec -T -e ... first-agent fa run ...` with
   explicit run-id.
6. Inspect only `ls -lh`, `wc -l`, and safe SQLite counts/metadata.
7. Compare container source revision, image label, bind-mounted source, and
   `fa.__file__` for the actual process.
8. Exercise failed session clone/invalid auto-run setup and verify entrypoint
   transitions to an explicit failed/standby state rather than continuing with
   an ambiguous workspace.
9. Preserve output and classify failures as source drift, image drift,
   filesystem permission, proxy, provider, authority, or rendering.
10. Only after human approval commit/push through the PR workflow.

Do-not:

- do not use `scripts/fa` for the core acceptance proof;
- do not print sensitive body files;
- do not call a local pytest pass a production deploy verification.

Exit criteria:

- [ ] deployed commit and image revision recorded;
- [ ] direct-container run completed;
- [ ] session DB/events/body metadata verified;
- [ ] proxy boundary verified without agent-side provider key;
- [ ] no unresolved source/image drift;
- [ ] handoff updated with exact evidence.

---

## 6. Verification plan

### CT1 — CLI roots

**Test class:** C2.

**Oracle:** exit code, parser trajectory, named artifact, stdout/stderr contract.

**Kill-check:** remove `set_defaults(func=...)` or root call; command test fails.

**Paths:** P1–P3, P16–P19, P20–P24.

### CT2 — authority

**Test class:** C0/C1/C3, then C2.

**Oracle ranking:** SQLite rows/counts → event IDs → exit code → mirror counts
→ free text.

**Kill-check:** remove DB write, reorder bootstrap, or replace authority with
mirror; focused authority test fails.

**Paths:** P1, P2, P11, P20, P22.

### CT3 — EventLog/EventBus

**Test class:** C1 producer + C0/C1 consumer + contract checker.

**Oracle:** event type/kind and fields, both durable and live capture.

**Kill-check:** remove exact producer `log.append`/`output.emit`; named test fails.

**Paths:** P11–P14, P19, P22.

### CT4 — Blackboard

**Test class:** C1/C3.

**Oracle:** conflict deny reason, no file mutation, same DB path, authoritative
blackboard row.

**Kill-check:** remove conflict producer or change DB injection; write-tool test
fails.

**Paths:** P11, P22.

### CT5 — debug bodies

**Test class:** C2 + manual direct-container metadata protocol.

**Oracle:** file exists/absent, row count, redaction invariant, correlation
fields, no secret in raw body file.

**Kill-check:** remove wrapper or redactor injection; C2 fails.

**Paths:** P4, P5.

LIVE-PATH PROOF (local):

```text
root: cli:_cmd_run
matrix: A/B/C
 test: tests/test_cli.py::test_fa_run_debug_body_capture_follows_exact_env_gate
oracle: llm_bodies.jsonl row + correlation + redaction + absent-file negative path
kill-check: removing src/fa/cli.py:1763 wrapper or redactor=redactor fails test
producer: src/fa/cli.py:_cmd_run:1763
consumer: operator forensic metadata protocol; DebugBodyTransport._write
paths-covered: 2/2 flag rows
contract-check: local PASS; deployment verification pending
pyramid: A
```

### CT6 — workflow artifacts

**Test class:** C2.

**Oracle:** `flow_state.json`, `eval_report.json`, route/budget fields, exit
code, aggregate projection.

**Kill-check:** remove artifact write or route consumer; named workflow test
fails.

**Paths:** P16–P18.

### CT7 — provider/proxy

**Test class:** C1/C2 plus direct deployment.

**Oracle:** attempts, status, logical correlation ID, response normalization,
proxy health, no key in agent filesystem/environment.

**Kill-check:** bypass provider chain or proxy route; provider-path test fails.

**Paths:** P6–P9, P5, P-proxy, P-openai.

### CT8 — deployment

**Test class:** C2/manual controlled container acceptance.

**Oracle:** process exit, health, safe metadata counts, source/image revision,
mount paths.

**Kill-check:** wrong command/env/mount or stale image must be detected by the
acceptance protocol.

**Paths:** P1, P4, P5, P23, P24.

### CT9 — event identity

**Test class:** C0/C1 concurrency and identity-isolation tests.

**Oracle:** unique event IDs, monotonic DB row identity, explicit run binding,
no duplicate rows after concurrent append.

**Kill-check:** replace the allocator with `COUNT(*) + 1`; the concurrent test
must fail. Reuse one DB under two run IDs; the isolation test must fail or the
implementation must reject it explicitly.

**Paths:** P1, P2, P25, P30.

### CT10 — failure policy

**Test class:** C3 forced-failure matrix plus C1 composition roots.

**Oracle:** exact structured error/exit behavior, authority row presence/absence,
mirror state, no silent fallback, operator-visible warning where required.

**Kill-check:** change a fail-closed branch to warning-only or a strict reader
to mirror fallback; the named failure test must fail.

**Paths:** P26, P28, F-authority, F-mirror, F-blackboard, F-pty,
F-worktree.

### CT11 — verification hygiene

**Test class:** C2 full-gate harness test/manual post-gate check.

**Oracle:** pre/post `git status`, file modes, temporary HOME/PATH, generated
artifacts, subprocess environment.

**Kill-check:** remove cleanup/isolation; the post-gate status assertion must
fail. The pre-existing candidate diff is captured before the gate and excluded
from the “new mutation” comparison.

**Paths:** P23, P24, P29.

---

## 7. Risks, rollback, open questions

### Risks

| ID | Risk | Mitigation | Detection |
|---|---|---|---|
| RK1 | Another giant PR recreates partial implementation | one slice, one approval, one L3 DoD | plan step/artifact inventory and diff review |
| RK2 | Old notes contain stale “shipped” claims | RN disposition + source verification | current grep/tests/negative variant |
| RK3 | Candidate patch is mistaken for approved design | external backup + explicit candidate label | SHA/base/status metadata |
| RK4 | SQLite authority change breaks old stats/JSONL | explicit Q2 policy and compatibility tests | DB-only/legacy/malformed matrix |
| RK5 | EventBus checker passes vacuously | AST/context audit and producer mutation | checker kill-check |
| RK6 | Blackboard remains split-brain | same-DB identity assertion | C1 write/conflict test |
| RK7 | local fake provider hides proxy/container failure | direct-container acceptance after local C2 | compose exec evidence |
| RK8 | CLI extraction changes UX or exit codes | parity C2 tests before deletion | argv/output/artifact comparison |
| RK9 | raw debug traces leak secrets | redaction C2 + metadata-only operator protocol | raw-body secret assertion |
| RK10 | `read_all()` performance fix changes authority semantics | correctness slice before optimization | DB/mirror comparison tests |
| RK11 | event-id fix uses another non-atomic counter | allocator spike + concurrent writer test before implementation | duplicate-ID stress test |
| RK12 | clean cutover hides a valuable old artifact | explicit unsupported diagnostic and no-write test; reopen compatibility only as a separate approved plan | legacy JSONL/old-DB probe |
| RK13 | test suite itself corrupts repository metadata | temp-copy fixtures and clean-worktree post-gate | `git diff --summary` after full gate |
| RK14 | fail-open fallback weakens worktree/secret/sandbox boundary | failure-policy matrix and adversarial C3 tests | forced factory/path failures |

### Rollback

- Candidate implementation rollback: do not apply the external candidate patch;
  it remains at the recorded SHA-256 path.
- Approved code slice rollback: revert one slice commit; no schema migration is
  allowed without a separate migration/rollback plan.
- DB compatibility rollback: preserve existing files and read policy until Q2
  is resolved; no deletion of `events.jsonl`, blackboard mirrors, or old
  workflow artifacts.
- Deployment rollback: record previous image/source revision and use the
  approved compose rebuild/restart procedure; do not change host bind topology.

### Open questions

#### Blocking

- **Q1:** Physical authority shape.
  - **Resolved:** Option A — one physical DB per persistent session; Blackboard
    and session metadata are session-scoped; `event_log` rows are run-scoped
    and filtered by `run_id`.
  - S1 freezes the exact Candidate A path, manifest, selector, workspace-owner,
    and no-automatic-migration contract.

- Q2: What is the exact read-side policy when `session.db` is unavailable or
  empty but `events.jsonl` exists? **Resolved: clean cutover.** Current `fa stats`
  reads only the new session DB format. Old JSONL/old per-run DB artifacts remain
  untouched and are reported as unsupported/legacy. No legacy reader or automatic
  migration belongs in the first implementation. A future compatibility reader
  is a separate backlog decision, not a hidden fallback.

- **Q10:** What exact CLI/session lifecycle contract implements Option A?
  **Resolved by S1:** Q10-A — CLI-owned `SessionManager`, `--session-id`,
  default new session creation, explicit existing-session attachment, a new
  `run_id` per invocation, Candidate A session namespace, single logical
  workspace owner, and no automatic migration. Evidence:
  `worklogs/implementation-plans/cli-trace-S1-verification-report.md`.

- **Q11:** What exact artifact-only subagent boundary is used?
  **Selected direction:** Q11-B — two-root sandbox policy. The session
  workspace is a read root; the task artifact directory is the only write root;
  the same policy must reach both the SandboxHook and the executor. The first
  mode remains reports/test outputs only; code-editing/isolation mode is deferred.
  - **Blocking for the subagent slice; not a blocker for the first direct
    `fa run` authority slice.**

#### Non-blocking with default

- **Q3:** First deployment gate.
  - Default: direct `fa run`; workflow is second gate.

- **Q4:** Program breadth.
  - Default: sequence command families; do not test all 11 as one first PR.

- **Q5:** Event-schema modernization.
  - Default: defer discriminated union/property-typed state until trace contracts
    and current path inventory are stable.

- **Q6:** Event identity representation.
  - Default: use the existing SQLite `INTEGER PRIMARY KEY AUTOINCREMENT` row
    identity as the serialization point, preserving the public `ev-...` form
    only if the transaction can return it atomically; gaps after failed writes
    are acceptable, duplicate IDs are not.
  - Gated step: S5.

- **Q7:** Should the full verification gate be required to leave `git status`
  clean when a pre-existing candidate diff exists?
  - Default: assert no *new* changes relative to a pre-test snapshot; do not
    require a clean absolute tree while the candidate patch is intentionally
    preserved.
  - Gated step: S3/S11.

- **Q8:** Which provenance fields are acceptable in `session_meta`?
  - Default: source revision, image revision/digest, harness version, config
    hash, session-id, run-id, and feature-flag summary; never provider key
    values, raw prompts, or body contents.
  - Gated step: S4/S7/S11.

- **Q9:** Should live stderr/EventBus apply SecretRedactor now?
  - Default: no. Keep current behavior and add live-output redaction to the
    backlog. This does not change the already-required redaction policy for
    durable `EventLog` content and `llm_bodies.jsonl`.
  - Gated step: backlog only; not a first-slice blocker.

---

## 8. Research-note disposition

| ID | Note item | Verdict | Why | Anchor |
|---|---|---|---|---|
| RN1 | Attached forensic F-01 ordering diagnosis | **Accept** | Base source and local reproduction confirm invalid ordering; exact fix direction fits SessionDatabase ownership. | CT2/S5 |
| RN2 | Attached forensic F-02 wrapper forwarding claim | **Rewrite** | Wrapper lacks explicit `-e`, but actual container inheritance still requires live verification; core wrapper and wrapper boundary must remain separate. | CT5/CT8/S4/S7 |
| RN3 | Attached forensic F-03 “no C2 proof” | **Reject as current-state claim** | Current candidate tree now has C2 proof; its historical status is stale. The requirement for C2/kill-check is accepted. | CT5/S7 |
| RN4 | 2026-07-19 observability audit “F-01 shipped with fallback” | **Reject as policy** | It conflicts with the current authority contract; source review wins over the old shipped label. | CT2/S5 |
| RN5 | 2026-07-19 edge audit “all implemented” | **Rewrite** | The note itself lists partial/deferred gaps and uses heuristic status; every row must be reclassified against current source/tests. | G3/S3 |
| RN6 | Root-cause analysis: producer/consumer and matrix kill-checks | **Accept** | It matches tests-writing and is directly applicable to this re-baseline. | CT3/S3/S6 |
| RN7 | Existing gap-closing plan: central `SessionDatabase`, short-lived SQLite connections, mirror-only JSONL | **Accept with rewrite** | Central authority and short transactions fit current code; the proposed broad typed-event Phase 6 is deferred until current substrate is verified. | CT2/S5 |
| RN8 | Existing substrate Slice 0/1 plan | **Accept with rewrite** | Authority/split-brain verification order is useful; current code already partially landed, so plan must audit Blackboard and read semantics afresh. | CT2/CT4/S5 |
| RN9 | Workflow plan: `fa run` single-role, `fa workflow` controller | **Accept** | This boundary is source-verified and reduces ambiguity. | CT1/CT6/S8 |
| RN10 | CLI ergonomics proposal: structured help/WebUI-ready registry | **Defer** | Valuable, but not the first substrate gate; adding UX while runtime truth is uncertain expands surface. | Q4/S10 |
| RN11 | OpenHands EventStream prior art | **Accept as prior art only** | Supports explicit state/event/runtime separation; does not authorize copying a service topology or adding FastAPI now. | G2/CT3 |
| RN12 | Docker official `compose exec -e` documentation | **Accept** | Confirms the explicit direct-container env injection mechanism for deployment verification. | CT8/S4 |
| RN13 | SQLite AUTOINCREMENT / ROWID documentation | **Accept as design input** | The existing table already has an AUTOINCREMENT row identity; this is a candidate serialization point, not yet an approved schema change. | CT9/S5 |
| RN14 | Existing `observability-logging-analytics` codemap | **Rewrite** | Useful layer decomposition, but its historical line numbers and “JSONL authority” wording are stale; current source and DB policy win. | G2/CT2/CT3 |
| RN15 | Existing `fa-workflow` plan/memo | **Accept boundary, defer expansion** | `fa run` vs `fa workflow` separation is useful; workflow resume/inspect/evidence expansion stays out of first vertical slice. | CT1/CT6/S8 |
| RN16 | Full-suite hygiene probe showing hook mode mutations | **Accept as new gap** | This is directly observable in the current worktree after the suite and needs a deterministic test-isolation contract. | G9/CT11/S3 |

---

## 9. Definition of Done

### Plan-level DoD

This plan is complete for review only when:

- [x] the operator approved the `fa run` → `fa workflow` slice order;
- [x] Q1 Option A and Q2 clean-cutover read policy have explicit decisions;
- [x] Q10 session lifecycle/path/manifest contract is frozen by S1;
- [ ] Q11 two-root artifact-only enforcement contract is frozen for its later subplan;
- [ ] all referenced symbols/files were preflight-verified;
- [ ] old-note claims have Accept/Reject/Rewrite/Defer dispositions;
- [ ] no implementation step contains an unowned policy choice;
- [ ] candidate patch is backed up and labeled as unapproved;
- [ ] plan status is changed from DRAFT only after review.

### Execution DoD for the first approved vertical slice

STATE:

- before: local tests and old audit claims exist, but direct container trace
  contract is not fully verified;
- after: direct `fa run` has a source-verified and deployment-verified trace
  map with explicit authority/mirror/live/derived roles.

ARTIFACTS:

- source-verified CLI/trace map;
- liveness/gap report;
- focused C1/C2 tests;
- direct-container metadata evidence;
- no raw debug-body output in operator evidence;
- approved code diff and updated handoff.

CONTRACTS:

- CT1–CT11 status must be `PLANNED` before implementation, then
  `IMPLEMENTED` and `VERIFIED` only with named command output.
- CT9 event identity has a concurrency/uniqueness proof;
- CT10 failure-policy matrix has forced-failure proofs;
- CT11 full verification leaves no newly introduced worktree mutations.

Negative proof:

- removing each selected producer makes its test fail;
- replacing authority with a mirror makes authority tests fail;
- running with disabled debug env does not create body capture;
- wrong/stale container source or mount path is detected;
- workflow/stats claims cannot pass by reading only narrative prose.

The first slice is **not done** merely because:

```text
pytest is green
ruff is green
mypy is green
```

Those are necessary gates, not production-path proof.

---

## 10. Anti-theater and READY gate

Status remains **DRAFT** until all applicable gates are reviewed:

- [x] preflight log exists and names real roots/symbols;
- [x] depth P3 is declared;
- [x] executive intent and non-goals are concrete;
- [x] contracts have named producer/consumer surfaces;
- [x] path and matrix inventory exists;
- [x] research-note dispositions exist;
- [x] Q1 physical authority shape resolved as Option A;
- [x] Q2 clean-cutover read policy resolved;
- [x] Q10 session/CLI lifecycle and migration contract resolved by S1;
- [x] Q11 artifact-only contract direction resolved; enforcement is a later subagent slice;
- [x] operator approved direct-container `fa run` first;
- [ ] every implementation step has an approved artifact inventory;
- [ ] deployment acceptance command and run-id policy are approved;
- [x] all IDs resolve in a plan self-lint;
- [x] no candidate patch is silently treated as implementation baseline.

Until the unchecked boxes are closed, the plan must not be labeled READY and
no implementation agent may execute S5 or later.

---

## 11. Artifacts inventory

| Artifact | Path | Action | Owner |
|---|---|---|---|
| Candidate backup patch | `/home/user/backups/First-Agent-dev-20260725Tcandidate-diff-from-3668e758c1522645a1bfb70787ebf53f7ef170a7.patch` | preserve | S0 |
| Candidate backup metadata | `/home/user/backups/First-Agent-dev-20260725Tcandidate-diff-from-3668e758c1522645a1bfb70787ebf53f7ef170a7.meta.txt` | preserve | S0 |
| Full draft bundle | `/home/user/backups/First-Agent-dev-20260725Tfull-draft-final.tar.gz` | preserve | S0 |
| Main plan | `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` | maintain | S1 |
| S1 session-lifecycle subplan | `worklogs/implementation-plans/PLAN-cli-trace-S1-session-lifecycle.md` | add | S1 |
| S1 verification report | `worklogs/implementation-plans/cli-trace-S1-verification-report.md` | add after S1 execution | S1 |
| S2 implementation subplan | `worklogs/implementation-plans/PLAN-cli-trace-S2-session-manager-and-authority.md` | add | S2 |
| S2 verification report | `worklogs/implementation-plans/cli-trace-S2-verification-report.md` | maintained with actual S2 evidence | S2 |
| S3 implementation subplan | `worklogs/implementation-plans/PLAN-cli-trace-S3-liveness-contract-audit.md` | reviewed READY plan | S3 |
| S3 plan review report | `worklogs/implementation-plans/cli-trace-S3-plan-review-report.md` | maintain review evidence | S3 review |
| CLI/trace codemap | `knowledge/codemaps/cli-runtime-trace-substrate-2026-07-25.md` | add only after approval | S3 |
| Liveness audit | `worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md` | add only after S2 | S3 |
| Authority implementation | `src/fa/inner_loop/session_db.py`, `state.py`, `blackboard.py`, tools | edit only after approval | S5 |
| Event contracts | `src/fa/output.py`, loop/coder/CLI producers, checker/tests | edit only after S3 | S6 |
| Direct `fa run` proof | `tests/test_cli.py` and focused authority/output tests | edit only after approved test plan | S7 |
| Workflow proof | `tests/test_cli_ergonomics.py`, workflow/global-history tests | edit only after S7 | S8 |
| Derived projection proof | `tests/test_stats.py`, `tests/test_stats_global_wiring.py` | edit only after S5/S8 | S9 |

---

## 12. Current approval request

Before implementation, approve or change these defaults:

1. **Order — ACCEPTED:** direct-container `fa run` first; `fa workflow` second;
   stats and CLI extraction after both.
2. **Logical authority model — ACCEPTED:** `session_id` is the SSOT identity of
   a persistent workspace/session; each default `fa run` / `fa workflow` creates
   a new session; an explicit session selector attaches to an existing session;
   every run/workflow has its own `run_id` and trace set.
3. **Physical authority shape — ACCEPTED:** Option A — one DB per
   persistent session with session-scoped Blackboard/meta and run-scoped event
   rows filtered by `run_id`. S1 resolved Q10-A: CLI-owned `SessionManager`,
   `--session-id`, new `run_id` per invocation, Candidate A session namespace,
   single logical workspace owner, and no automatic migration.
4. **Read surface — ACCEPTED:** DB is machine SSOT and current data is read by
   a DB-backed existing `fa stats` reader. Clean cutover is selected because
   there is no valuable existing corpus to migrate; old JSONL/DB artifacts stay
   untouched and are reported as unsupported/legacy. No first-slice legacy reader,
   automatic migration, or new `fa inspect` command.
5. **Scope — ACCEPTED:** first execution slice is direct `fa run` plus
   authority/EventBus/debug-body trace; not all 11 CLI commands in one PR.
6. **Candidate patch — ACCEPTED:** keep as backup only; do not apply automatically.
7. **Event identity — PENDING S5:** use a database-serialized allocator;
   duplicate IDs are unacceptable even if gaps after failed writes are allowed.
8. **Verification hygiene — ACCEPTED:** test hook copies in `tmp_path`, not
   tracked source files; add a post-gate “no new worktree mutations” check with
   the pre-existing candidate diff treated as baseline.
9. **Gap handling — ACCEPTED:** classify V1–V26 one by one as confirmed defect,
   intended-but-undocumented, not a gap, deferred, or unverified. Do not open
   26 separate PRs before dependency order is known.
10. **Live output redaction — DEFERRED:** keep current EventBus/stderr behavior
    for now and document redaction as backlog. This does not remove the current
    redaction requirement for durable EventLog and `llm_bodies.jsonl`.
11. **Subagent first mode — ACCEPTED:** artifact-only reports/test outputs.
    Q11-B is selected: two-root sandbox policy. The subagent does not edit code
    files; it returns a structured envelope plus bounded artifacts. The session
    workspace is a read root and the task artifact directory is the only write
    root. Code-editing/isolation mode is deferred.

Until these are approved, this plan remains **DRAFT**.

---

## 13. Subplan execution protocol

The main workplan is the durable source of truth. Each approved slice receives
one English-only subplan under `worklogs/implementation-plans/`.

A subplan must contain:

- slice scope and explicit non-goals;
- source-verified current behavior;
- exact files, symbols, and contracts in scope;
- dependency and stop conditions;
- per-edit intent, mechanism, production practice, and failure behavior;
- targeted tests and the required `tests-writing` class (C0/C1/C2/C3);
- producer kill-check and consumer proof where applicable;
- path/flag matrix for the slice;
- rollback and artifact handling;
- falsifiable Definition of Done;
- actual command output after execution.

The execution prompt for every slice must require the executor to:

```text
1. State the exact intent and contract before editing.
2. State the files/symbols allowed to change.
3. Stop if a new policy question appears; promote it to Q#.
4. For every edit, explain the mechanism and the production rationale.
5. Run targeted tests after each edit and the relevant checkpoint suite.
6. Run the producer kill-check for every wiring claim.
7. Report actual verification commands and results.
8. Update the main workplan only after the subplan DoD is evidenced.
```

The next subplan is design/verification work, not a runtime patch:

```text
PLAN-cli-trace-S1-session-lifecycle.md
```

S1 must close Q2/Q10 details and produce the source-verified session lifecycle,
manifest/path, DB scope, legacy-artifact, and migration contract before S5
runtime authority implementation begins.
