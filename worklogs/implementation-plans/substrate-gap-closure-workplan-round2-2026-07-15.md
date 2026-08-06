# Substrate Gap-Closure Workplan — Round 2 (Post-Audit, Decision-Locked)

**Date:** 2026-07-15  
**Scope:** Close all currently surfaced Stage A/B/C substrate gaps in verifiable slices  
**Status:** Active execution plan  
**Source inputs:**
- `knowledge/research/substrate-modernization-plan-2026-07-14.md`
- hostile audit round 2 over current working tree
- accepted operator decisions on DB authority, resume semantics, and subagent scope

---

## 0. Executive intent

This plan replaces any lingering ambiguity with a **closure-first**, **evidence-first**, **anti-theater** execution sequence.

The goal is **not** to add new extraordinary capabilities.
The goal is to make the intended substrate:

1. **functionally real**,
2. **correct under live wiring**,
3. **resilient under partial failure**,
4. **operationally observable**,
5. **aligned with locked §9 decisions**.

This plan assumes:
- we have time,
- we prefer fewer but cleaner slices,
- every slice must end in a real runtime proof, not symbol presence.

---

## 1. Newly locked decisions (operator-approved)

These are now binding and supersede prior ambiguity.

### D8 — Unified per-run DB authority

**Authoritative truth should be one unified per-run DB.**  
**Workspace/global databases should be derived projections, not hot-path authority.**

Implications:
- hot-path writes for `event_log`, blackboard records, compaction metadata, and session-level observability must converge into **one per-run `session.db`**;
- JSONL is either:
  - mirror-only, or
  - explicitly removed from authority paths;
- any workspace/global DBs become:
  - export/index/search surfaces,
  - not transactionally authoritative runtime state.

### D9 — Resume draft semantics

**Previous PR draft / resume text must be inserted as mutable non-cacheable summary/history.**

Implications:
- it is **not** governance,
- it is **not** part of `PinnedBuffer`,
- it is **not** compaction-exempt standing policy,
- it may be summarized, replaced, or compacted as mutable session context.

### D10 — Subagent scope contract

`fs_spawn_subagent` is locked as:
- **narrow-scope**
- **role-bounded**
- **stateless**
- **limited-function**
- **not a bypass around main-agent shell/tool safety**

Implications:
- subagent command execution must not create a weaker policy domain than `fs_run_bash`;
- shared-workspace mode is acceptable only if safety and write coordination remain explicit;
- generic arbitrary-shell nested execution is **out of contract**.

---

## 2. Hard invariants for all closure work

Every slice below must preserve these invariants.

### I1 — One authority per concern
No dual-authority read paths.
If two stores exist, one must be explicitly authoritative and the other derived.

### I2 — Presence is not enough
A feature is not done until it is:
- present,
- wired,
- correct,
- resilient.

### I3 — No silent degradation on critical paths
Critical failures must become one of:
- explicit warning + safe fallback,
- explicit degraded mode,
- explicit hard stop.

Critical path must never silently pretend success after losing authoritative state.

### I4 — Shared-workspace safety is a first-class requirement
Because §9.2 is locked to shared workspace by default, any write-capable path must be safe in that model.

### I5 — Governance text must be distinguishable from mutable session text
Standing constraints and mutable memory must never blur into one opaque block.

### I6 — Tests must target the real boundary
Provider-body behavior, DB authority reads, scheduler behavior, and subprocess paths must be tested at the real integration seam whenever possible.

### I7 — No marketing claims in code/comments without architectural truth
If cache anchors, PTY persistence, hybrid export, or compactor role selection are not real end-to-end, the code/comments/docs must not imply they are.

---

## 3. Current gap register (workplan authority)

This is the operative closure ledger for Round 2.

| ID | Sev | Area | Summary |
|---|---|---|---|
| FIND-001 | P0 | DB | EventLog/Blackboard dual-write split-brain under partial SQLite failure |
| FIND-002 | P0 | Subagent/Security | `fs_spawn_subagent` bypasses shell safety domain in shared workspace |
| FIND-003 | P1 | Cache | Prompt caching metadata dies before provider boundary |
| FIND-004 | P1 | Stage3 | Compactor role loaded but configured model not actually used in request |
| FIND-005 | P1 | Observability | `fs_usage` / `fs_chronicle_search` wired to wrong log path and wrong schema |
| FIND-006 | P1 | Bash | `fs_run_bash` large-output path uses nonexistent artifact API and fails with `internal_error` |
| FIND-007 | P1 | PTY | Stateful shell is not wired into live CLI harness |
| FIND-008 | P1 | Budget/Compaction | Stage machine collapses 80% mask / compact / hard-stop semantics |
| FIND-009 | P1 | Hybrid | `global_history.db` export absent |
| FIND-010 | P1 | Subagent | role/env/configured spawn limit contract is ignored or partially ignored |
| FIND-011 | P1 | DB topology | “Unified SQLite substrate” claim false; multiple hot-path authorities remain |
| FIND-012 | P1 | Scheduler | parallel batching drops denied results from returned tuple/order |
| FIND-013 | P1 | Search/Scheduler | `fs_instant_grep` is classified read-only but performs writes |
| FIND-014 | P1 | Governance | PinnedBuffer guarantee incomplete; stale pins persist; mutable resume text is pinned |
| FIND-015 | P2 | Logging | logging migration incomplete; runtime warning paths still use raw `print` |
| FIND-016 | P2 | PTY | `\r` resolution absent on capture paths |
| FIND-017 | P2 | Tests | significant anti-theater gaps remain |
| FIND-018 | P2 | Drift | dead/partial flags and symbols remain in production tree |

---

## 4. Architectural target state after closures

After this workplan completes, the substrate should look like this.

### 4.1 Runtime state plane

**One per-run authority DB:**
- `~/.fa/session-log/<run_id>/session.db`

Tables (minimum target set):
- `event_log`
- `blackboard`
- `session_meta` or equivalent for compaction/export/checkpoint bookkeeping
- optional telemetry rollup table if justified

### 4.2 Derived planes

Derived/mirror surfaces:
- `events.jsonl` as mirror-only if retained
- `blackboard.jsonl` as mirror-only if retained
- `~/.fa/global_history.db` as export/analytics projection
- FTS/grep indexes as derived caches only

### 4.3 Prompt/context plane

Prompt order should converge to:
1. base system prompt
2. standing governance pins
3. tool definitions
4. mutable session memory summary / resume context
5. live conversation / protected tail

Where:
- pins are full-fidelity governance,
- resume draft is mutable non-cacheable memory,
- compaction may summarize mutable context but not governance.

### 4.4 Subagent plane

`fs_spawn_subagent` should become:
- bounded by role,
- safety-equivalent to parent command policy,
- explicit in outputs,
- observable in event log,
- non-magical in shared workspace.

---

## 5. Execution strategy

We will close gaps in **PR-sized slices**, not one giant refactor.
Each slice ends with:
- code proof,
- focused tests,
- hostile re-check,
- explicit done definition.

Recommended order is risk-first, not convenience-first.

---

# 6. Slice plan

## Slice 0 — Contract freeze and cleanup of plan ambiguity

### Purpose
Turn accepted operator decisions into written engineering contract so later slices do not regress into prior ambiguity.

### Closes
- decision ambiguity behind FIND-011 / FIND-014 / FIND-010

### Scope
- write/update decision note(s)
- update workplan references to D8/D9/D10
- mark superseded assumptions from earlier docs/comments

### Concrete tasks
1. Record D8 unified DB authority explicitly.
2. Record D9 mutable resume semantics explicitly.
3. Record D10 limited-function subagent semantics explicitly.
4. Mark old worktree-isolation / multi-DB hot-path ideas as superseded where they create implementation pressure.

### Required verification
- grep-able decision records exist
- no open architecture ambiguity remains for DB authority / resume semantics / subagent scope

### Done definition
A future contributor can read one source and know:
- what is authoritative,
- what is mutable,
- what subagent is allowed to be.

---

## Slice 1 — Unified per-run DB authority and split-brain removal

### Purpose
Eliminate the most dangerous integrity defect class: partial success across JSONL/SQLite or EventLog/Blackboard authority boundaries.

### Closes
- FIND-001
- FIND-011
- foundational dependency for FIND-005, FIND-009, FIND-013

### Scope
- move hot-path blackboard authority into the same per-run `session.db`
- remove ambiguous dual-authority reads
- define mirror-only behavior for JSONL if retained
- make write failure semantics explicit

### Concrete tasks
1. Refactor `EventLog` so authoritative append success depends on DB success, not JSONL success.
2. Refactor blackboard writes so authoritative blackboard state is stored in the per-run DB.
3. Ensure blackboard read/query/conflict detection uses per-run DB as hot-path authority.
4. If JSONL mirrors stay:
   - make them best-effort,
   - never allow stale SQLite or stale JSONL to silently eclipse the other.
5. Add explicit degraded/hard-stop behavior when authoritative DB writes fail.
6. Introduce a minimal `session_meta` table if needed to store export/checkpoint/compaction state cleanly.

### Design rules
- one transaction domain for event + blackboard hot-path state
- no implicit workspace-level authority for active run correctness
- derived projections may lag, authority may not lie

### Required tests
1. **Split-brain repro test — EventLog**
   - force SQLite write failure after JSONL mirror would have succeeded
   - assert no stale-authority read path can pretend success
2. **Split-brain repro test — Blackboard**
   - same defect class for blackboard writes/queries
3. **Authority read test**
   - prove read path is DB-first and consistent under mirror issues
4. **Concurrent run-local write test**
   - two write paths in one run do not lose rows or diverge

### Anti-theater requirements
- do not mock `sqlite3.connect`
- real temporary DB file required
- must assert the actual authoritative read surface, not only append return value

### Done definition
The audit repro:
- “JSONL has two rows, SQLite has one, reader only sees one”

must no longer reproduce.

---

## Slice 2 — Runtime observability surfaces must read the active authority

### Purpose
Make `fs_usage`, `fs_chronicle_search`, and similar runtime observability tools actually reflect the active run.

### Closes
- FIND-005
- contributes to FIND-017

### Scope
- bind observability tools to active session/run authority instead of guessed workspace paths
- parse actual runtime schemas
- stop JSONL scans as authoritative runtime query path

### Concrete tasks
1. Rework event-log path resolution for observability tools.
2. Prefer session DI or run-id-based DB access over `workspace/.fa/events.jsonl` guesses.
3. Update `fs_usage` to parse the usage schema the loop really writes.
4. Decide whether `fa stats` remains post-hoc JSONL parser or also grows a DB-aware path.
5. Align descriptions/docs with real data source.

### Required tests
1. live one-turn session → `fs_usage` returns non-TBD usage
2. active run with known event rows → `fs_chronicle_search` returns them from authority path
3. path resolution test proves active session log is used, not stale workspace path

### Anti-theater requirements
- no fake hand-constructed path constants only
- tool must be exercised through actual registry/session wiring

### Done definition
Observability tools reflect the active run without path guessing.

---

## Slice 3 — Stage C correctness pass: compaction ladder, configured compactor, provider-boundary truth

### Purpose
Turn Stage C from “partly wired but semantically wrong” into an explicit, verified state machine.

### Closes
- FIND-003
- FIND-004
- FIND-008
- contributes to FIND-014 and FIND-017

### Scope
- correct threshold/state machine semantics
- ensure configured compactor role actually reaches provider request body
- make cache-control claims true or explicitly reduce claim scope

### Concrete tasks
1. Replace the collapsed compaction gate with explicit states:
   - warn
   - Stage 2 mask
   - Stage 3 compact
   - hard stop
2. Lock exact boundary semantics for 70/80/90-style ladder or updated model-aware equivalent.
3. Ensure Stage 3 uses configured compactor model identity, not hardcoded slug.
4. Make fallback compaction always produce a valid 4-header summary.
5. Decide what to do with cache-control:
   - wire it through real provider bodies, or
   - de-scope/disable claim until supported.
6. Add explicit provider-boundary tests for Anthropic/OpenAI request bodies.

### Required tests
1. exact-edge threshold tests (`69/70/79/80/89/90` or equivalent)
2. Stage 2 trigger test
3. Stage 3 trigger-after-Stage2-insufficient test
4. provider-body compactor model propagation test
5. malformed/empty Stage 3 output fallback test
6. prompt-cache metadata reaches actual provider-body test

### Anti-theater requirements
- tests must inspect provider transport/body layer, not only intermediate `RequestInfo.messages`
- tests must not rely on comments like “90%” while passing an 80% threshold mock

### Done definition
Stage C has a real, documented state machine and real provider-boundary truth.

---

## Slice 4 — Governance plane repair: PinnedBuffer vs mutable resume/session context

### Purpose
Separate hard governance from mutable context and make pin behavior deterministic.

### Closes
- FIND-014
- supports D9

### Scope
- resume text leaves pinned plane
- stale/missing pin behavior becomes explicit
- hash semantics become truthful

### Concrete tasks
1. Remove previous PR draft / resume text from `PinnedBuffer` injection path.
2. Insert resume draft as mutable non-cacheable summary/history segment.
3. Clear stale pin cache entries during refresh.
4. Define missing pinned file behavior:
   - warning only,
   - degraded mode,
   - or hard fail for a strict subset.
5. Define what “verification via SHA-256” actually means in runtime terms.
6. Add clear prompt ordering contract tests.

### Required tests
1. delete pinned file mid-session → stale content must not persist
2. modify pinned file mid-session → behavior matches locked policy
3. resume draft appears in mutable segment, not pinned segment
4. governance survival test across Stage2/Stage3 prompt rebuild

### Anti-theater requirements
- must test actual prompt assembly ordering
- cannot merely assert hash string presence in text

### Done definition
Governance and mutable session memory are cleanly separated and reproducible.

---

## Slice 5 — Subagent hardening to intended narrow contract

### Purpose
Convert `fs_spawn_subagent` from a loosely bounded nested shell surface into the intended limited-function tool.

### Closes
- FIND-002
- FIND-010
- contributes to FIND-017

### Scope
- role fidelity
- config-driven spawn limit fidelity
- env semantics
- parent-equivalent safety policy
- lifecycle and observability

### Concrete tasks
1. Explicitly define allowed subagent roles and what each role may do.
2. Make `role` affect actual execution/envelope semantics.
3. Wire configured `max_subagent_spawns_per_session` into real runtime path.
4. Decide whether env injection is supported; if yes, implement correctly; if no, remove misleading surface.
5. Ensure subagent command path is checked by equivalent sandbox/intent/secret policy before execution.
6. Add spawn start/end/fail events with correlation fields.
7. Define shared-workspace conflict semantics clearly.
8. Define parent SIGTERM/interrupt behavior toward child processes.

### Required tests
1. malicious nested shell denied by same policy class as parent shell
2. `researcher` vs `verifier` behavior difference test
3. configured spawn limit non-default test
4. lifecycle cleanup / termination test
5. shared-workspace audit trail test

### Anti-theater requirements
- not enough to assert the tool exists and returns success under default path
- tests must prove role, limit, and safety semantics

### Done definition
`fs_spawn_subagent` is no longer a bypass path and matches its limited-function contract.

---

## Slice 6 — Bash correctness and live PTY truthfulness

### Purpose
Repair the main shell tool semantics so runtime matches claimed behavior.

### Closes
- FIND-006
- FIND-007
- FIND-016
- contributes to FIND-015 and FIND-018

### Scope
- artifact offload correctness
- stateful shell wiring decision
- carriage-return cleaning
- doc/runtime truth alignment

### Concrete tasks
1. Fix artifact offload API mismatch in bash path.
2. Decide explicitly:
   - wire PTY/stateful shell into live CLI harness now, or
   - de-scope stateful persistence claims until wired.
3. Implement `\r` normalization for capture output.
4. Apply cleaner on all relevant capture paths.
5. Audit shell tool descriptions to match actual runtime behavior.

### Required tests
1. large-output bash command no longer fails as `internal_error`
2. if PTY stays in scope: persistent env/cwd test through live harness
3. CR cleaning examples:
   - `foo\rbar\n -> bar`
   - progress bar spam cases
4. fallback path and PTY path both covered

### Anti-theater requirements
- direct `PtyPool` tests do not count as proof of CLI/main harness wiring
- at least one test must exercise live `fa run`-style session state path if persistence remains claimed

### Done definition
Shell behavior is either truly stateful in the live harness, or honestly documented as stateless.

---

## Slice 7 — Scheduler and search safety residuals

### Purpose
Make tool batching and search classification true to their safety assumptions.

### Closes
- FIND-012
- FIND-013
- FIND-017 residuals

### Scope
- result-order preservation
- denied-result preservation
- hidden write removal from “read-only parallel” paths
- real git fast-path coverage

### Concrete tasks
1. Fix `_execute_batch_parallel()` return ordering/arity so denied results are preserved.
2. Remove or isolate hidden writes from `fs_instant_grep` query path.
3. Reclassify `fs_instant_grep` if necessary until truly read-only.
4. Add git fast-path grep integration tests inside a temp git repo.
5. Evaluate colon/content parsing robustness explicitly.

### Required tests
1. batch with one denied read tool returns full ordered result tuple
2. empty-index `instant_grep` does not violate read-only assumptions
3. `git grep` fast-path test executes real git command in a temp repo
4. fallback path test still passes outside git repo

### Done definition
Parallel-read batching assumptions become true in code, not just comments.

---

## Slice 8 — Logging standardization and runtime sink configuration

### Purpose
Finish the migration from ad-hoc warning prints to coherent runtime logging.

### Closes
- FIND-015
- supports operability for all other slices

### Scope
- runtime warnings/errors only; CLI UX prints may remain deliberate
- explicit logging configuration

### Concrete tasks
1. Replace runtime `print("WARNING: ...")` paths with logger calls.
2. Add explicit runtime logging configuration or documented logging bootstrap.
3. Preserve human-facing CLI prints where intentionally UX-oriented.
4. Sample-audit broad exception blocks for compliance.

### Required tests / checks
1. grep count of runtime warning prints drops materially
2. representative failure paths emit logger records
3. compaction/session warnings visible with configured runtime logging

### Done definition
Runtime diagnostics are coherent, grep-able, and consistently sinked.

---

## Slice 9 — Hybrid export implementation (`global_history.db`)

### Purpose
Close the still-open §9.1 product commitment after hot-path authority is fixed.

### Closes
- FIND-009

### Scope
- export from per-run authority DB to global history projection
- idempotence and failure semantics

### Concrete tasks
1. Define export schema:
   - run id
   - timestamps
   - role/model
   - session summary
   - compaction summary presence
   - outcome / stop reason
   - selected telemetry rollups
2. Define export trigger(s): session end minimum; checkpoints optional.
3. Define export idempotence strategy.
4. Define export failure policy.
5. Ensure export is projection-only, not hot-path authority.

### Required tests
1. `test_global_history_export_idempotent`
2. concurrent export safety test
3. terminal state export completeness test

### Done definition
`global_history.db` exists as a derived, safe cross-run projection.

---

## Slice 10 — Anti-theater verification hardening

### Purpose
Prevent recurrence of “looks landed, not really landed” defects.

### Closes
- FIND-017
- FIND-018 residuals

### Scope
- targeted integration tests only
- no giant coverage theater

### Concrete tasks
1. Add provider-body tests for cache-control and compactor model selection.
2. Add live authority-path tests for observability tools.
3. Add split-brain regression tests.
4. Add subagent role/limit/safety tests.
5. Add PTY/CR tests for the actual live path or explicitly scoped fallback.
6. Remove or demote dead flags/symbols where they cannot be justified.

### Done definition
Critical risks have tests that fail when wiring is removed or semantics drift.

---

## 7. Verification discipline (mandatory)

Every slice must end with these categories.

### V1 — Static proof
- exact symbols changed
- exact paths changed
- grep proof for removed ambiguity where relevant

### V2 — Runtime proof
- one focused integration test or repro that exercises the real boundary

### V3 — Failure proof
- at least one intentional failure path exercised
- must verify safe fallback / degraded mode / hard stop

### V4 — No-regression proof
- run the narrowest relevant existing suite
- plus any new tests from the slice

### V5 — Anti-theater check
Ask explicitly:
- does the test stop too early?
- does it inspect only mocks/intermediate state?
- would the bug still pass if provider/DB boundary were wrong?

If yes, the test is not sufficient.

---

## 8. Recommended execution order

Risk-first order:

1. **Slice 0** — contract freeze  
2. **Slice 1** — unified authority / split-brain removal  
3. **Slice 5** — subagent hardening  
4. **Slice 3** — Stage C correctness  
5. **Slice 4** — governance plane repair  
6. **Slice 6** — bash + PTY truthfulness  
7. **Slice 2** — observability tool rewiring  
8. **Slice 7** — scheduler/search residuals  
9. **Slice 8** — logging standardization  
10. **Slice 9** — global export  
11. **Slice 10** — anti-theater hardening and final hostile re-audit

---

## 9. What must be true before we can claim “Stage C shipped” honestly

Minimum ship bar:

1. one per-run DB is the real hot-path authority
2. no split-brain on partial DB failure
3. Stage C uses correct threshold ladder semantics
4. configured compactor model reaches provider boundary
5. prompt caching claim is either true end-to-end or removed
6. pins are governance only; resume draft is mutable session memory
7. `fs_spawn_subagent` is no longer a bypass around shell safety
8. bash large-output and CR handling are correct
9. observability tools read live authority
10. critical anti-theater tests exist and fail on unwiring

If any of the above are false, the “shipped” claim remains overstated.

---

## 10. Immediate next action

**Next execution slice should be Slice 0 + Slice 1 preparation.**

That means, before code changes:
1. write the decision record for D8/D9/D10,
2. inventory all current writes/reads that touch:
   - `event_log`
   - blackboard
   - telemetry
   - compaction metadata
3. design the unified per-run schema and migration path,
4. define JSONL mirror policy explicitly,
5. only then start editing write paths.

This sequencing prevents another false landing where symptoms are patched but authority remains ambiguous.

---

## 11. Non-goals for this closure wave

To preserve focus, this wave does **not** prioritize:
- new extraordinary agent features,
- autonomous expansion of subagent capabilities,
- speculative Stage D additions,
- broad documentation beautification unrelated to closure,
- performance tuning before correctness of authority and safety domains.

---

## 12. Final note

This plan is intentionally heavier than a normal feature plan because the current failure mode is **partial reality**:
features exist just enough to look landed, while still failing under live boundary conditions.

Therefore, this closure wave optimizes for:
- fewer moving parts,
- stronger authority boundaries,
- honest contracts,
- end-to-end proofs.

That is the shortest path to a substrate that is actually trustworthy inside the First-Agent harness.
