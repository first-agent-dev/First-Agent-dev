# S1 Verification Report — Session Lifecycle, Authority, and Run Binding

Plan: `worklogs/implementation-plans/PLAN-cli-trace-S1-session-lifecycle.md`

Parent plan: `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`

Status: **PASS WITH FOLLOW-UP IMPLEMENTATION SUBPLAN REQUIRED**

Execution type: design/source verification only. No runtime source or test files
were edited by S1.

Baseline checked:

```text
origin/main = 3668e758c1522645a1bfb70787ebf53f7ef170a7
```

The unapproved runtime candidate diff was not used as the implementation
baseline.

## 1. Commands and evidence

### 1.1 Baseline identity

Command:

```bash
git rev-parse origin/main
```

Observed:

```text
3668e758c1522645a1bfb70787ebf53f7ef170a7
```

### 1.2 Parser inventory

A Python AST probe enumerated relevant `add_argument()` calls in the current
working tree. The baseline source was also checked at the same symbols.

Observed relevant arguments:

```text
line=326 args=['--workspace']
line=385 args=['--workspace', '-w']
line=399 args=['--run-id', '-i']
line=405 args=['--resume']
line=455 args=['--workspace', '-w']
line=462 args=['--run-id', '-i']
line=633 args=['--run-id', '-i']
line=650 args=['--workspace', '-w']
line=682 args=['--workspace']
```

Conclusion:

```text
--session-id is absent from the baseline parser for fa run and fa workflow.
```

### 1.3 Entrypoint identity probe

Source: `scripts/fa-entrypoint.sh:146-182, 203-232`.

Observed behavior:

```text
SESSION_ID="${FA_RUN_ID:-session-<timestamp>-<pid>}"
export FA_RUN_ID="$SESSION_ID"
SESSION_DIR="/sessions/${SESSION_ID}"
```

The entrypoint then clones `/repo` into `/sessions/<SESSION_ID>` and publishes
`/sessions/.active`. In command-override mode it executes the supplied command.
In auto-run mode it explicitly invokes:

```text
fa run ... --workspace "$WORKSPACE" ... --run-id "$FA_RUN_ID"
```

Conclusion:

```text
The baseline conflates persistent session identity and run identity.
The accepted target requires these identities to be separate.
```

### 1.4 Core run trace probe

Relevant baseline source facts:

```text
src/fa/cli.py:1750
  run_id = args.run_id or f"run-{os.getpid()}"

src/fa/cli.py:1765
  /home/fa/.fa/session-log/<run-id>/llm_bodies.jsonl

src/fa/cli.py:1842
  /home/fa/.fa/session-log/<run-id>/events.jsonl

src/fa/cli.py:1846
  EventLog(events_path, run_id=run_id, redactor=redactor)
```

Conclusion:

```text
The baseline trace layout is run-shaped. S1 selects a session-authority DB
separate from the per-run mirror/controller artifact directory.
```

### 1.5 Authority/schema probe

Baseline `SessionDatabase` creates:

```text
event_log
blackboard
session_meta
```

`event_log` and `blackboard` both carry `run_id`, but the constructor does not
carry or validate `session_id`. Event queries in the baseline are not scoped by
`run_id` at the `read_event_rows()` boundary.

Conclusion:

```text
The schema has a usable run_id field, but the scope contract is not enforced.
S5 must add session binding and run-scoped EventLog queries.
```

### 1.6 Blackboard construction probe

Baseline production construction is:

```text
SessionState
  → self.session_db = self.log.session_db when absent
  → Blackboard(workspace/.fa/blackboard,
               session_db=self.session_db,
               run_id=self.run_id)
```

The public `Blackboard` constructor also creates its own `SessionDatabase` when
no injected DB is passed. S1 therefore freezes the production rule but does not
remove the legacy/test constructor yet.

### 1.7 Read-path probe

Baseline `fa.stats.parse_session()` creates `EventLog(events_path)` and then
calls `read_all()`. This can create a DB beside a legacy JSONL file and can
reach JSONL fallback after an authority read failure.

S1 decision:

```text
new format:
  DB-backed stats only

old JSONL/old per-run DB:
  untouched, unsupported/legacy diagnostic

migration:
  no automatic migration
```

## 2. S1 decisions frozen

### D1 — Physical layout

Select Candidate A from the subplan:

```text
/home/fa/.fa/sessions/<session-id>/manifest.json
/home/fa/.fa/sessions/<session-id>/session.db

/home/fa/.fa/session-log/<run-id>/events.jsonl
/home/fa/.fa/session-log/<run-id>/llm_bodies.jsonl
/home/fa/.fa/session-log/<run-id>/flow_state.json
/home/fa/.fa/session-log/<run-id>/eval_report.json
```

Reason:

- session authority and run artifacts have different lifetimes;
- session and run directory names cannot collide by namespace accident;
- the current per-run trace directory remains recognizable to operators;
- the session DB path is not inferred from a per-run JSONL path;
- old per-run DBs can remain untouched;
- the layout is easy to validate with path-containment checks.

### D2 — SessionManager ownership

`SessionManager` is the canonical logical owner of:

- session ID validation/generation;
- manifest creation and validation;
- session DB resolution;
- session-to-workspace binding;
- run-to-session binding.

The entrypoint must not remain a second independent logical session owner. During
implementation, the existing clone operation may be reused, but clone ownership
must be mediated by the SessionManager contract or a shared helper. The executor
must not implement two competing session-creation paths.

### D3 — Session creation and attachment

```text
fa run / fa workflow without --session-id:
  create a new session_id
  create or provision its workspace
  initialize its session DB
  create a new run_id

fa run / fa workflow --session-id A:
  load and validate Session A manifest
  validate workspace A
  open session DB A
  create a new run_id
```

An unknown explicit session ID is an error. It must not silently create a new
session with the requested name.

### D4 — Workspace argument rule

```text
--session-id supplied:
  manifest workspace is authoritative
  an explicitly supplied --workspace must match it or the command exits 2

no --session-id:
  --workspace may be used as a controlled creation/testing input
  otherwise SessionManager provisions the default /sessions/<session-id> workspace
```

This prevents a caller from attaching to Session A while actually mutating a
workspace belonging to Session B.

### D5 — Run identity

Every invocation receives a new run ID.

```text
--session-id A:
  continue the persistent session
  create a new run_id

--run-id R:
  may remain for controlled tests/forensics
  R must be new/unclaimed; reusing an existing run ID exits 2

--resume:
  deprecated compatibility behavior
  if retained, it requires --session-id and creates a new run_id
  it must not append a new invocation to the old run trace
```

A top-level workflow invocation attaches through `session_id` and receives
one new workflow `run_id`; internal stages reuse that invocation run ID in the
current S2 slice so `flow_state.json`, `eval_report.json`, and the shared event
facade remain one coherent workflow trace. Per-stage run IDs would require a
separate workflow identity contract and are not part of S2.

### D6 — Manifest schema

Minimum manifest:

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

Rules:

- `manifest.session_id` must equal the requested session ID;
- workspace path must be under the approved workspace root;
- DB path must be under the approved FA state root;
- paths are resolved before use;
- corrupt/missing/foreign manifest fails closed;
- manifest updates use atomic temp-file plus rename;
- manifest contains no provider keys, proxy tokens, raw prompts, or body contents.

### D7 — Run binding

The session authority stores an explicit binding:

```text
run_binding:<run-id>
  value = {
    "run_id": "...",
    "session_id": "...",
    "created_at": "..."
  }
```

The exact storage encoding remains implementation detail, but the contract is:

```text
one run_id belongs to exactly one session_id
EventLog reads only its run_id rows
Blackboard reads session-scoped state
```

### D8 — Clean cutover

Current-format stats behavior:

```text
valid session DB:
  read DB rows and format them for humans

old JSONL/old per-run DB:
  do not create a DB
  do not auto-import
  return explicit unsupported/legacy diagnostic
```

Recommended CLI error contract:

```text
exit code: 2
structured code: legacy_trace_unsupported
stderr: current FA sessions require session.db; legacy JSONL/DB was not migrated
```

The exact wording may be refined in the runtime subplan, but the no-fallback,
no-write behavior is frozen.

## 3. Future runtime artifact boundary

The following source changes are deliberately deferred to the next approved
implementation subplan:

```text
SessionManager implementation and parser --session-id
session DB factory/path binding
EventLog session DB injection and run-scoped queries
run identity allocation and uniqueness
DB-backed stats reader
clean-cutover unsupported path
entrypoint integration without duplicate session ownership
```

Candidate future source files:

- `src/fa/cli.py`;
- a new `src/fa/session/manager.py` module, if extraction is justified;
- `src/fa/inner_loop/session_db.py`;
- `src/fa/inner_loop/state.py`;
- `src/fa/blackboard/blackboard.py`;
- `src/fa/stats.py`;
- `scripts/fa-entrypoint.sh` only if the ownership integration requires it.

No candidate file is edited by S1.

## 4. Verification mapping

| Contract | Verification | Oracle |
|---|---|---|
| session ID syntax/generation | C0 validation test in next runtime subplan | accepted/rejected ID and path |
| default session creation | C1/C2 composition test | manifest, workspace, session DB |
| explicit session attachment | C1/C2 | same workspace/DB, new run ID |
| two runs in one session | C1 | distinct run IDs, filtered event rows, shared Blackboard |
| session mismatch | C3 | exit 2, no mutation |
| old-format clean cutover | C2 | no DB created, structured unsupported result |
| run ID reuse | C1/C3 | explicit rejection, no mixed rows |
| `--resume` compatibility | C2 | new run ID, no old-trace append |
| direct-container context | C2/manual | actual `fa.__file__`, workspace/session path, artifact paths |

### Producer kill-check

S1 changes no runtime producer. Producer kill-check is **N/A by design**. S1
must not claim that session lifecycle behavior is already shipped.

## 5. S1 DoD

### State

S1 is complete when:

- `session_id`, `run_id`, and `event_id` each have one meaning;
- Option A physical layout is selected;
- Q10-A owner is selected and the entrypoint boundary is explicit;
- `--session-id` behavior is specified;
- `--resume` behavior is specified;
- old-format clean cutover is specified;
- run-to-session binding is specified;
- future runtime files and tests are named;
- no runtime source/test file was changed.

### Artifacts

- `PLAN-cli-trace-S1-session-lifecycle.md`;
- this verification report;
- parent main-plan update;
- `HANDOFF.md` update.

### Verification commands

```bash
git rev-parse origin/main
git diff --check
python scripts/check_doc_links.py
git status --short -- src/fa tests
```

Observed in S1:

```text
git rev-parse origin/main
  3668e758c1522645a1bfb70787ebf53f7ef170a7

git diff --check
  PASS

python scripts/check_doc_links.py
  OK: 168 markdown file(s) checked, no broken internal links.

src/fa and tests status
  pre-existing candidate changes present;
  no S1 runtime/test edits added
```

### Negative proof

S1 is invalid if:

- a later executor must guess whether DB scope is session or run;
- a later executor must guess what `--session-id` attaches to;
- a legacy stats read can silently create a DB;
- the plan claims workspace read-only without naming the enforcement root;
- the report claims a runtime producer kill-check even though no producer changed.

## 5.1 Post-review correction — 2026-07-27

The original D5 wording used “stage own run identity,” which was broader than
the accepted identity model and inconsistent with the source-verified
`_WorkflowContext`/`_run_stage()` implementation. The corrected interpretation
above is authoritative for S2: one workflow invocation has one `run_id`, and
stage role identity is carried by workflow events/artifacts. This is a wording
correction to the S1 report, not a claim that S1 changed runtime behavior.

## 6. S1 close status

```text
S1 STATUS: PASS WITH FOLLOW-UP IMPLEMENTATION SUBPLAN
Runtime source changed: NO
Runtime tests changed: NO
Main plan status: DRAFT
Next required artifact: implementation subplan for SessionManager/session authority
Blocking follow-up: Q11 remains for the later subagent slice only
```
