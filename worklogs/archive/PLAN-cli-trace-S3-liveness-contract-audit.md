> **Status:** archived 2026-08-25 — moved per b_full, verification reports exist (S1-S4) / code-proven IMPLEMENTED (S14b)

# PLAN: S3 — Liveness and Contract Audit

Plan-ID: `PLAN-cli-trace-S3-liveness-contract-audit`

Status: **READY FOR AUDIT EXECUTION** — plan review passed; runtime/test edits
remain forbidden in S3.

Depth: **P2** — cross-module source audit, producer/consumer inventory, path
matrix verification, failure-policy classification, and test-hygiene analysis;
no runtime implementation.

Revision: v2 — explicit P1–P33 path index and completed plan review.

Plan review report:

- `worklogs/implementation-plans/cli-trace-S3-plan-review-report.md`

Parent plan:

- `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`

Previous slice evidence:

- `worklogs/implementation-plans/cli-trace-S2-verification-report.md`
- `worklogs/implementation-plans/PLAN-cli-trace-S2-session-manager-and-authority.md`

## 0. Scope and execution boundary

### IDEA

Produce a source-verified liveness and contract audit after S2 session/authority
wiring. The audit must distinguish structural presence, real composition-root
reachability, observed behavior, producer proof, consumer proof, path coverage,
and deployment evidence. A green regex checker or full pytest run is not enough.

### CONCRETE INTENT

Turn the current signal/path inventory into a falsifiable audit artifact that
answers, for every selected surface:

```text
What is the producer?
What is the consumer?
Which composition root reaches it?
Which flags/error branches trigger it?
Which durable/live/derived channels receive it?
Which test observes it?
Does removing the producer make that test fail?
What remains unverified or deferred?
```

### PROJECT MEANING

In the formal-trace substrate this becomes the evidence layer between S2 wiring
and S4/S5/S6 implementation. S3 does not repair findings. It prevents S5/S6
from choosing fixes based on stale labels, consumer-only tests, regex false
positives, or an unscoped path claim.

### GOALS

- **S3-G1 — Signal inventory:** enumerate current `EventType`, `LogKind`, and
  `CONSOLE_MIRROR_KINDS` definitions, producers, consumers, and dynamic forms
  with exact file/symbol/line evidence.
- **S3-G2 — Two-sided liveness:** classify producer, consumer, dual-write, and
  current C1/C2 proof independently; identify consumer-only and producer-only
  theater.
- **S3-G3 — Path/matrix coverage:** map parent paths P1–P33 and relevant flag/
  failure rows to actual tests, manual probes, or explicit gaps.
- **S3-G4 — Authority/failure audit:** classify S2 authority behavior and
  residual V1–V26 findings as fixed, partial, deferred, unverified, or unsafe;
  do not silently re-open resolved policy.
- **S3-G5 — Verification hygiene:** verify that the audit/full gate leaves no
  new source modes, content, environment, or generated artifacts behind.
- **S3-G6 — Next-slice selection:** select the first implementation slice from
  evidence and map it to S5/S6/S7 without implementing it in S3.

### NON-GOALS

- No edits under `src/fa/`.
- No edits under `tests/`.
- No edits to `scripts/check_producer_consumer_contract.py` or
  `scripts/check_log_kind_contract.py` unless a separate approved subplan is
  created after S3 proves a concrete checker defect.
- No EventType/LogKind changes.
- No authority allocator, Blackboard mutation, EventBus, provider, workflow,
  stats, sandbox, or subagent fixes.
- No direct-container deployment or image rebuild; that remains S4/S7/S11.
- No raw `llm_bodies.jsonl` output.
- No automatic candidate patch application, commit, push, or deploy.
- No broad code-quality cleanup because a gap is discovered.

### STOP RULE

Stop and promote a new blocking `Q12+` if the audit requires choosing a product
policy rather than recording evidence, including:

- changing an authority/fallback default;
- declaring a dynamic signal intentionally live or intentionally dormant;
- changing the accepted workflow/session identity model;
- changing the S5/S6 ownership boundary;
- adding a new production checker or runtime signal;
- using a source snapshot whose revision cannot be identified.

## 1. Readiness preflight — source-verified current state

### 1.1 Baseline and worktree identity

Fresh readiness commands on 2026-07-27:

```text
HEAD        = 3668e758c1522645a1bfb70787ebf53f7ef170a7
origin/main = 3668e758c1522645a1bfb70787ebf53f7ef170a7
branch      = fa/20260725-session-authority-debug-wiring
```

The active tree contains the pre-existing unapproved candidate diff plus the
implemented S2 changes and documentation artifacts. S3 must not call this one
undifferentiated “baseline.” It uses three named source views:

```text
B0 — base:
  disposable worktree at origin/main

C0 — candidate comparator:
  disposable base worktree with the external candidate patch applied and
  candidate-only changes labelled; never applied to the active tree

S2 — subject:
  the active worktree after S2 implementation, identified by HEAD, status,
  file list, and S2 report; this is the only view whose post-S2 liveness is
  eligible for current claims
```

If C0 cannot be produced by `git apply --check`, record C0 as unavailable and
continue only with B0/S2; do not synthesize candidate status from prose.

### 1.2 Contract checker readiness evidence

Current source/checker results:

```text
python scripts/check_producer_consumer_contract.py
  EventType literals: 16
  ConsoleRenderer handlers: 16
  producer emit() calls: 31 across 15 types
  C1 tested: 20 types
  cost_alert: dormant
  result: PASS

python scripts/check_log_kind_contract.py
  LogKind members: 33
  CONSOLE_MIRROR_KINDS members: 15
  literal log.append producers: 30 distinct kinds
  soft orphan warnings: service_unavailable, subagent_spawn_done, timeout
  result: PASS
```

These results are **not sufficient proof**:

- `scripts/check_producer_consumer_contract.py` uses regular expressions over
  `OutputEvent`/handler text and a hard-coded producer-file list;
- `scripts/check_log_kind_contract.py` uses source-window heuristics and does
  not prove same-branch dual-write correspondence;
- dynamic `kind` assignment is present at
  `src/fa/inner_loop/tools/spawn_subagent.py:72`;
- a checker can pass while the real composition root never reaches a producer;
- a C0 consumer test can pass while the producer is dead.

S3 must preserve these limitations in the report rather than “fixing” the
checker solely to improve the count.

### 1.3 Composition roots and signal surfaces

Verified audit roots:

```text
CLI roots:
  src/fa/cli.py:build_parser
  src/fa/cli.py:_cmd_run
  src/fa/cli.py:_cmd_workflow
  src/fa/cli.py:_cmd_stats
  scripts/fa-entrypoint.sh

loop/runtime roots:
  src/fa/inner_loop/coder_loop.py:drive_session
  src/fa/inner_loop/loop.py:run_session
  src/fa/inner_loop/state.py:EventLog / SessionState
  src/fa/inner_loop/tools/spawn_subagent.py

signal definitions/consumers:
  src/fa/output.py:EventType
  src/fa/output.py:LogKind
  src/fa/output.py:CONSOLE_MIRROR_KINDS
  src/fa/output.py:ConsoleRenderer._handle_*
  src/fa/output.py:EventBus

authority/derived roots:
  src/fa/inner_loop/session_db.py:SessionDatabase
  src/fa/blackboard/blackboard.py:Blackboard
  src/fa/stats.py:parse_session_db
  src/fa/inner_loop/global_history.py
```

Gold verification patterns:

```text
tests/test_event_type_c1_producers.py
tests/test_output.py
tests/test_cli.py
tests/test_cli_ergonomics.py
tests/test_session_db_authority.py
tests/test_observability_runtime_authority.py
tests/test_fa_entrypoint.py
```

### 1.4 Current S2 liveness boundary

S2 has local L3 evidence for:

```text
SessionManager/manifest/run binding local C1/C2/C3
fa run/fa workflow session selector local C2
injected EventLog run scoping local C1/C3
injected Blackboard session identity local C1/C3
DB-only current stats local C2/C3
entrypoint identity/failure shell C2
```

S2 does not provide L3 deployment evidence for:

```text
direct Docker compose execution
image/source/mount identity
proxy/provider path
live EventBus redaction
```

S3 must not upgrade these surfaces beyond L2 merely because local tests pass.

## 2. Current state → target state

### AS-IS — verified audit problem

| Dimension | Current evidence | Liveness / trust status |
|---|---|---:|
| EventType definition/handlers | 16 literals and 16 handlers in `src/fa/output.py` | L1 structural |
| EventType producer checker | 31 regex-detected emit calls across 15 types; one dormant type | L2 heuristic |
| LogKind definition/producer checker | 33 members, 30 literal producer kinds, 3 soft orphan warnings | L2 heuristic |
| Dynamic producers | `spawn_subagent.py:72` passes dynamic `kind` | L1/L2 until context audit |
| C1 producer proof | checker reports 20 tested types, but path/source mapping is incomplete | L2 until path table |
| Parent P1–P33 inventory | exists in main plan; several rows reflect pre-S2 state | stale/needs reclassification |
| Failure-policy matrix | parent contract exists; no single post-S2 evidence table | L1 |
| Verification side effects | S2 final gate had identical pre/post status/mode/hash | L3 for the tested local gate |
| Direct deployment | no current S3 evidence | L0/L2 depending surface |

### TO-BE — machine-checkable audit state

The S3 audit report must contain:

```text
one row per EventType
one row per LogKind
one row per CONSOLE_MIRROR_KINDS member
one row per parent path P1–P33
one row per selected flag/failure matrix row
one row per residual V1–V26 disposition
one row per failure-policy boundary
```

Each signal row must include:

```text
name
source definition
producer file:symbol:line(s)
consumer file:symbol:line(s)
composition root
trigger/flag/error branch
durable channel
live channel
derived consumer
checker result
C1/C2/C3 test reference
producer kill-check reference
status: L0/L1/L2/L3 or explicit DEFERRED/N/A
confidence: source / AST / runtime / deployment
```

No report row may use `checker PASS`, `pytest green`, or `implemented` as its
only evidence.

## 3. Contracts

### S3-CT1 — Audit artifact contract

**Producer:** S3 audit execution commands and disposable probes produce
`worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md`.

**Consumer:** S4/S5/S6 planning and human PR review consume the report to choose
an implementation owner and reject unsupported liveness claims.

**POST:** the report contains source snapshot identity, exact inventories,
path/matrix tables, checker limitations, residual gap dispositions, and a
prioritized next-slice recommendation.

**ERRORS:** missing source snapshot, incomplete inventory, unbounded raw-body
output, or a report that cannot distinguish base/candidate/S2 status → audit
FAIL; no S3 READY/complete claim.

**KILL-CHECK:** remove a real producer in a disposable S2 copy and rerun the
inventory; the report/check result must change and classify the producer as
absent. A report unchanged by producer removal is invalid.

### S3-CT2 — EventType two-sided contract inventory

**Definition:** `src/fa/output.py:EventType`.

**Producer:** every `output.emit(OutputEvent(...))` path and every typed/dynamic
helper that can produce an EventType.

**Consumer:** every `ConsoleRenderer._handle_<type>` handler and any non-console
consumer explicitly named by the source.

**Dual-write:** record whether the path also calls `log.append`; do not assume
all EventTypes are durable mirrors.

**KILL-CHECK:** producer removal in a disposable source copy must remove the
producer from the audit inventory and make the named mutation test fail where a
C1 test claims the signal.

### S3-CT3 — LogKind and console-mirror inventory

**Definition:** `src/fa/output.py:LogKind` and
`src/fa/output.py:CONSOLE_MIRROR_KINDS`.

**Producer:** literal and dynamic `EventLog.append(kind=...)` sites, including
`state.py`, `coder_loop.py`, `loop.py`, hooks, CLI, and `spawn_subagent.py`.

**Consumer:** `SessionDatabase.event_log`, `EventLog.read_all`, stats/global
history/observability readers, and EventBus/renderer paths for mirror kinds.

**KILL-CHECK:** remove a dynamic/literal producer in a disposable source copy;
the inventory must lose the site and the selected producer test must fail.

### S3-CT4 — Path/matrix liveness contract

**Producer:** the real composition root and trigger branch for each P#/flag/
failure row.

**Consumer:** the named test, operator artifact, or explicit deferred owner.

**POST:** each parent P1–P33 row has exactly one status: `VERIFIED`, `PARTIAL`,
`UNVERIFIED`, `DEFERRED`, or `N/A — reason`, with a command/test/probe reference.

**KILL-CHECK:** remove the producer call from a disposable copy for at least
one representative path in each audited signal family; the path proof must
fail or become `UNVERIFIED`.

### S3-CT5 — Failure-policy classification contract

Audit boundaries:

```text
SessionDatabase initialization/read/write
EventLog authority read/write and JSONL mirror
Blackboard authority read/write and mirror
EventBus listener/renderer
PTY fallback
worktree creation/isolation
telemetry/artifact store
feature flag loading
stats/global-history derived reads
entrypoint clone/provisioning
```

Each row must classify:

```text
boundary owner
failure injected
current behavior
required policy from CT10
observability channel
whether current behavior matches
owner slice for any fix
```

S3 records mismatches; it does not repair them.

### S3-CT6 — Verification hygiene contract

**Producer:** test fixtures, shell helpers, installer tests, subprocess wrappers,
and the full verification gate.

**Consumer:** `git status`, file modes, environment snapshots, generated-file
inventory, and the next agent session.

**KILL-CHECK:** run the gate against a disposable source copy with cleanup
removed or a tracked-source fixture reintroduced; the post-gate mutation check
must detect the difference.

## 4. Path and flag matrix

### 4.1 S3 audit paths

| ID | Trigger/surface | Root/source | Audit proof |
|---|---|---|---|
| S3-P1 | all EventType definitions/handlers | `output.py` | AST/source inventory + checker comparison |
| S3-P2 | literal EventLog producers | `state.py`, `coder_loop.py`, `loop.py`, hooks, CLI | AST/source inventory |
| S3-P3 | dynamic `kind`/`event_type` producers | `spawn_subagent.py`, helper paths | assignment-flow/source-context inventory |
| S3-P4 | console mirror dual-write paths | `coder_loop.py`, `state.py`, `spawn_subagent.py`, CLI | branch-context table, not file presence only |
| S3-P5 | C1 producer tests | `tests/test_event_type_c1_producers.py` and relevant tests | root/test/oracle/kill-check table |
| S3-P6 | current S2 authority paths | SessionManager/CLI/EventLog/Blackboard/stats | S2 report cross-check + source probe |
| S3-P7 | workflow/controller paths | `_cmd_workflow`, `_run_stage`, artifact readers | source/test matrix |
| S3-P8 | failure-policy boundaries | DB/mirror/EventBus/PTY/worktree/flags | forced-failure/source classification |
| S3-P9 | verification hygiene | full pytest/static/contract gate | pre/post snapshot |

### 4.2 Parent path inventory coverage

S3 must audit all P1–P33 from the parent plan, but it may classify a path as
`DEFERRED` or `N/A` when the parent explicitly assigns it to S4/S5/S6/S7/S8/S9.
A path is not `VERIFIED` merely because a related test file exists.

The inherited parent path set is explicitly:

| Parent IDs | Surface family | Required S3 treatment |
|---|---|---|
| P1, P2, P3 | fresh/resume/no-explicit-run-id `fa run` | current S2 local status plus deployment dependency |
| P4, P5 | debug disabled/enabled | composed C2 status plus S4/S7 deployment status |
| P6, P7, P8, P9 | provider success/retry/auth/request-shape failure | producer/consumer/path evidence and owner slice |
| P10, P11 | max-turn and hook-deny paths | root/oracle/dual-write evidence |
| P12, P13 | context budget without/with compaction | branch inventory and C1 status |
| P14, P15 | console and quiet output | EventBus producer/consumer matrix |
| P16, P17, P18 | workflow linear/repair/adaptive | controller/artifact and stage evidence |
| P19 | deterministic inner-loop smoke | separate non-LLM root status |
| P20, P21 | current stats/global-history projection | authority/derived boundary status |
| P22 | Blackboard read/write | session authority and mutation-policy boundary |
| P23, P24 | entrypoint auto-run/direct command override | shell C2 versus direct-container status |
| P25 | concurrent EventLog writers | S5 dependency; no false S2/S3 L3 claim |
| P26, P27 | DB failure with mirror / old-format stats | CT10 failure and clean-cutover evidence |
| P28, P29 | failed clone / clean-worktree gate | C2/C3 and hygiene evidence |
| P30 | reused DB with different run ID | scope/identity negative proof |
| P31, P32, P33 | default session / explicit attach / multiple runs | current S2 lifecycle proof and remaining deployment owner |

Required S3 matrix columns:

```text
P#
current source root
S2 status
actual test/probe
oracle
producer kill-check
remaining owner
status/confidence
```

### 4.3 Flag/failure matrix

| Matrix | Required S3 classification |
|---|---|
| `FA_DEBUG_LLM_BODIES=0/1` + `detail=debug` | S2 local proof versus deployment pending |
| output console/quiet | producer/consumer path and test status |
| compaction off/on | all producer branches and missing paths |
| provider success/retry/auth/shape failure | durable/live/derived signals and test status |
| SessionDatabase failure | fail-closed proof or residual gap |
| mirror failure | DB truth and observable warning status |
| Blackboard failure | fail-closed versus fallback status |
| PTY unavailable | fallback policy and test status |
| worktree isolation failure | fail-closed policy and remaining V18/V19/V24/V25 status |
| host-only versus explicit `docker compose exec -e` | deployment-only status |

## 5. Step-by-step audit execution

### Step S3.0 — Baseline/source identity guard

Traces-to: S3-G2, S3-G5, S3-CT1, S3-CT6.

Depends-on: S2. Parallelizable-with: none.

Target liveness: audit provenance L0→L2.

Allowed changes: temporary `/tmp` probes and the S3 plan/report artifacts only.

Do:

1. Verify `HEAD`, `origin/main`, branch, candidate patch SHA/size, and S2
   verification report path.
2. Create disposable B0/C0/S2 source views as defined in §1.1.
3. Capture pre-audit status, diff summary, file modes, selected environment
   values (`HOME`, `PATH`, `NO_COLOR`, `FA_DEBUG_LLM_BODIES`), and generated
   artifact inventory.
4. Prohibit raw body-file output in all probe commands.

Do-not:

- do not apply C0 to the active tree;
- do not call a current-tree claim a base-tree claim;
- do not write probe artifacts under the repository source tree.

Exit criteria:

- [ ] source views and revisions are recorded;
- [ ] candidate patch is verified external/unapproved;
- [ ] pre-audit snapshot exists;
- [ ] no runtime/test file changed.

### Step S3.1 — Build the hybrid source inventory

Traces-to: S3-G1, S3-G2, S3-CT2, S3-CT3.

Depends-on: S3.0. Parallelizable-with: none.

Target liveness: signal inventory L1→L2.

Do:

1. Parse `EventType`, `LogKind`, and `CONSOLE_MIRROR_KINDS` with AST handling
   both `Assign` and `AnnAssign` forms; record exact definition locations.
2. Walk all production Python ASTs for literal and nonliteral `.append(kind=)`
   and `.emit(OutputEvent(...))` calls.
3. Track local assignments into dynamic `kind`/`event_type` values at least
   through the enclosing function/branch; record unresolved flows instead of
   dropping them.
4. Extract `ConsoleRenderer._handle_*` consumers and non-console readers.
5. Run both existing regex checkers and store their raw metadata/counts only;
   do not print body files or treat checker output as the audit oracle.
6. Compare AST/source inventory against checker output and classify each
   difference as checker false positive, checker false negative, dynamic form,
   dormant/intentional, or unresolved.

Do-not:

- do not add a general AST checker to the repository in S3;
- do not infer dynamic reachability from a string literal alone;
- do not mark a signal L3 from a handler-only test.

Exit criteria:

- [ ] every EventType has definition/producer/consumer rows;
- [ ] every LogKind and mirror kind has producer/consumer rows or explicit
  dormant/deferred status;
- [ ] dynamic producer sites are named;
- [ ] checker limitations and mismatches are recorded.

Kill-check:

- remove a representative literal producer and a representative dynamic
  producer in disposable S2 copies; the inventory must change and the selected
  producer proof must fail.

### Step S3.2 — Build the two-sided producer/consumer/path table

Traces-to: S3-G2, S3-G3, S3-CT2, S3-CT3, S3-CT4.

Depends-on: S3.1. Parallelizable-with: none.

Target liveness: signal claims L1/L2→L2/L3-classified.

Do:

1. For every EventType, join definition → producer → consumer → composition
   root → test/probe.
2. For every LogKind, join producer → DB/mirror → stats/observability/global
   history/console consumer where applicable.
3. For every `CONSOLE_MIRROR_KINDS` member, verify branch-level dual-write
   correspondence; file-level co-occurrence is insufficient.
4. Identify tests that instantiate a renderer/formatter/consumer without
   booting the producer root; classify them as consumer-only evidence.
5. Identify producer paths with no C1/C2/C3 proof and assign the remaining
   owner slice.
6. Record intentional audit-only kinds that must not be forced into console
   output.

Exit criteria:

- [ ] two-sided table is complete;
- [ ] producer-only/consumer-only/dynamic/unresolved cases are explicit;
- [ ] dual-write status is branch-specific;
- [ ] each claimed L3 row has a named producer kill-check.

### Step S3.3 — Audit P1–P33 and flag/failure matrix

Traces-to: S3-G3, S3-G4, S3-CT4, S3-CT5.

Depends-on: S3.2. Parallelizable-with: none.

Target liveness: path inventory L0/L1→L2/L3-classified.

Do:

1. Re-read parent P1–P33 against current S2 source; update stale pre-S2
   descriptions without editing the parent path table until the report is
   complete.
2. For each path, name the actual test/probe, oracle, producer kill-check, and
   unresolved deployment dependency.
3. Audit the flag/failure matrix in §4.3, including success and forced-failure
   paths.
4. Separate local fake-transport proof, real composition-root proof, and direct
   container proof.
5. Mark each row `VERIFIED`, `PARTIAL`, `UNVERIFIED`, `DEFERRED`, or
   `N/A — reason`; do not use “covered” without an oracle.
6. Keep S2-resolved lifecycle paths distinct from remaining V1/V2/V15/V17/V24/V25
   implementation gaps.

Exit criteria:

- [ ] P1–P33 each has a status and evidence reference;
- [ ] no row is marked production L3 from local-only evidence;
- [ ] all matrix rows have a test/probe or explicit owner/defer reason;
- [ ] S2 fixes are not reclassified as unresolved without source evidence.

### Step S3.4 — Reproduce/classify residual V findings

Traces-to: S3-G4, S3-CT5.

Depends-on: S3.3. Parallelizable-with: none.

Target liveness: gap register L0→L2 with ownership.

Do, using disposable copies and temporary fixtures only:

1. Recheck S2-resolved findings V3/V4/V5/V7/V16/V26 and record fixed proofs.
2. Recheck V1/V2, V6, V8, V9, V10, V11, V13, V14, V15, V17, V18, V19,
   V20, V21, V22, V23, V24, and V25 against current source.
3. For each result record:
   `confirmed`, `fixed`, `partial`, `deferred`, `unverified`, or `not-a-gap`;
   exact source/probe; impact; owner slice; and kill-check requirement.
4. Do not implement any fix surfaced by a probe. Promote a policy choice to
   Q12+ and stop the dependent audit step.

Required hygiene:

```text
copy hook/source fixture to tmp_path before chmod/mutation
never mutate tracked hook sources
never print raw llm_bodies.jsonl
```

Exit criteria:

- [ ] every V1–V26 has one current disposition;
- [ ] S2 fixed claims have negative proofs where applicable;
- [ ] no residual gap is assigned to an unapproved owner;
- [ ] high-priority next slice is selected from evidence.

### Step S3.5 — Failure-policy and verification-hygiene audit

Traces-to: S3-G4, S3-G5, S3-CT5, S3-CT6.

Depends-on: S3.4. Parallelizable-with: none.

Target liveness: policy matrix L0→L2.

Do:

1. Force or source-audit each CT10 boundary without changing production code.
2. Record exact current error/exit/fallback behavior and compare it to the
   required policy.
3. Capture pre/post status, mode, environment, subprocess, and generated-file
   state around the full local gate.
4. Test representative cleanup/failure mutations in disposable copies so the
   hygiene check itself is not vacuous.
5. Record repository-wide static baseline findings separately from changed-file
   S2 evidence.

Exit criteria:

- [ ] CT10 boundary table is complete;
- [ ] fail-closed/fail-open mismatches are prioritized;
- [ ] verification gate side effects are classified;
- [ ] no audit probe modified the active tree.

### Step S3.6 — Publish audit report and next-slice recommendation

Traces-to: S3-G1 through S3-G6, S3-CT1 through S3-CT6.

Depends-on: S3.5. Parallelizable-with: none.

Target liveness: report artifact L0→L3 for audit claim.

Create:

```text
worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md
```

The report must include:

1. source/baseline provenance;
2. executive result and confidence limits;
3. EventType two-sided table;
4. LogKind/mirror table;
5. producer/consumer checker comparison;
6. P1–P33 path matrix;
7. flag/failure matrix;
8. V1–V26 current disposition table;
9. CT10 failure-policy table;
10. verification-hygiene evidence;
11. prioritized gap register with owner slice;
12. selected first implementation slice and explicit non-goals;
13. exact commands/output summaries, never raw body contents.

Update only at close:

```text
parent main workplan S3 evidence/exit status
HANDOFF.md next bounded action
knowledge/llms.txt for the new S3 report and subplan artifacts
```

Kill-check:

- the audit report is invalid if a representative producer removal leaves its
  inventory, path status, and selected kill-check result unchanged.

## 6. Verification plan

### S3-CT1 Audit artifact

**Test class:** C0/source + C1 disposable mutation + manual report review.

**Oracle:** source snapshot identity, report section completeness, changed
inventory rows, and mutation delta.

**Producer/consumer:** audit commands/probes produce the report; S4/S5/S6
planning and human review consume it.

**Path coverage:** S3-P1 through S3-P9.

### S3-CT2 EventType

**Test class:** C0 AST/source, C1 producer mutation, C0 paired consumer review.

**Oracle ranking:** exact producer/consumer file:symbol:line → root/test
reference → checker comparison → free text.

**Kill-check:** representative `output.emit` removal changes inventory and
fails the producer test.

**Paths:** S3-P1 through S3-P5.

### S3-CT3 LogKind/mirror

**Test class:** C0 AST/source, C1 dynamic/literal mutation, C0 consumer mapping.

**Oracle:** exact `kind` values/assignments, branch-level dual-write table,
DB/mirror/console consumer mapping.

**Kill-check:** remove literal/dynamic producer; inventory and test status fail.

**Paths:** S3-P2 through S3-P5.

### S3-CT4 Path/matrix

**Test class:** C0/C1/C2 evidence audit; C2 where the real CLI root is needed.

**Oracle:** path row + command/test + structured event/DB/exit oracle.

**Kill-check:** representative root producer removal downgrades the path row.

**Paths:** P1–P33 and S3-P6–S3-P9.

### S3-CT5 Failure policy

**Test class:** C3 forced-failure probes and source review; no runtime fix.

**Oracle:** exact error code/exit, authority row state, mirror state, cleanup
state, operator diagnostic, and policy classification.

**Kill-check:** restore a hidden fallback or warning-only branch in a disposable
copy; the policy probe must fail.

**Paths:** F-authority, F-mirror, F-blackboard, F-pty, F-worktree, F-env and
parent P26/P28/P29.

### S3-CT6 Hygiene

**Test class:** C2 full-gate pre/post snapshot plus disposable negative fixture.

**Oracle:** status/mode/env/generated-file delta.

**Kill-check:** remove cleanup/isolation in the disposable fixture; post-gate
mutation assertion must fail.

**Paths:** P23, P24, P29, S3-P9.

### LIVE-PATH PROOF — audit claim

```text
root: current source audit + disposable composition-root mutation
matrix: S3-P1..S3-P9 and parent P1..P33
artifact: worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md
oracle: exact source rows + structured test/DB/exit evidence + mutation delta
kill-check: remove representative producer in disposable copy; report changes
producer: audited production producer site
consumer: S4/S5/S6 planning and human PR review
paths-covered: 9/9 audit paths; P1..P33 individually classified
contract-check: existing regex checks PASS, limitations explicitly recorded
pyramid: A
```

## 7. Risks, rollback, and open questions

### Risks

| ID | Risk | Mitigation | Detection |
|---|---|---|---|
| S3-R1 | Regex checker PASS hides dynamic producer gap | hybrid AST/source-context inventory | dynamic `kind` mutation |
| S3-R2 | Base/candidate/S2 statuses are mixed | B0/C0/S2 provenance table | snapshot/revision mismatch |
| S3-R3 | Path inventory marks a test file as production proof | require root/oracle/kill-check columns | consumer-only classification |
| S3-R4 | Audit grows into runtime cleanup | forbidden-file gate and stop rule | `git status` after each step |
| S3-R5 | Forced-failure probe mutates tracked fixture/mode | tmp copies and pre/post status | mode/content delta |
| S3-R6 | A report repeats stale V1–V26 prose | source-plus-probe disposition table | every row needs current evidence |
| S3-R7 | Audit produces sensitive artifacts | metadata/count-only protocol | artifact inventory and secret grep |

### Rollback

S3 produces plans, reports, and temporary probes only:

```text
remove the S3 plan/report artifacts and parent/HANDOFF index updates;
no runtime DB, source, or test behavior is changed.
```

The candidate patch remains external and unapproved.

### Open questions

#### Blocking

None at plan authoring time. S3 is an evidence slice and does not choose a new
runtime policy. Any new policy discovered during audit becomes Q12+ and stops
the dependent step.

#### Non-blocking defaults

- **S3-Q1 — checker replacement:** default is no repository checker edit in S3;
  record demonstrated false positive/negative and assign a later checker plan
  only if the current checker cannot support a required gate.
- **S3-Q2 — audit source views:** default is B0/C0/S2 triage; if C0 cannot be
  constructed, mark it unavailable rather than reconstructing it from prose.
- **S3-Q3 — dormant LogKinds/EventTypes:** default is classify as dormant/dead
  with owner and evidence; do not add producers to make counts look complete.
- **S3-Q4 — deployment claims:** default is `L2/PENDING` until S4/S7 direct
  container evidence exists.
- **S3-Q5 — report line numbers:** default is source revision + symbol + line
  range + content hash where line numbers can drift; no historical line number
  is trusted without the current source snapshot.

## 8. Research-note disposition

| ID | Note/input | Verdict | Reason | Anchor |
|---|---|---|---|---|
| S3-RN1 | Parent Step S3 audit outline | Accept with rewrite | Correct scope, but current S2 requires tri-snapshot provenance and residual-finding classification rather than repeating base claims. | S3.0–S3.6 |
| S3-RN2 | Existing regex producer/consumer checker | Accept as heuristic | Useful gate, not path-complete; hybrid AST/source context is required. | S3.1/S3-CT2 |
| S3-RN3 | Existing LogKind checker | Accept as heuristic | It reports soft orphan warnings and does not prove same-branch dual-write. | S3.1/S3-CT3 |
| S3-RN4 | S2 verification report | Accept | Provides verified current lifecycle/authority baseline and explicit deferred V1/V2/V15/V17/V24/V25 work. | S3.0/S3.4 |
| S3-RN5 | Tests-writing skill | Accept | C1/C2/C3, producer kill-check, path sensitivity, and ranked oracles are mandatory for audit claims. | S3-CT1–S3-CT6 |
| S3-RN6 | Old “all implemented”/“shipped” audit labels | Reject as authority | Current source and mutation evidence override past-tense labels. | S3-G2/S3-G4 |
| S3-RN7 | Direct-container evidence protocol | Defer to S4/S7 | S3 records deployment status but does not claim production liveness. | S3-Q4 |

## 9. Definition of Done

### State

Before S3:

```text
S2 local authority/session wiring is verified;
contract checkers are green but heuristic;
P1–P33 and V1–V26 statuses are partly stale or distributed;
failure-policy and two-sided liveness are not one current audit artifact.
```

After S3:

```text
source views are provenance-labelled;
EventType/LogKind/mirror producers and consumers have exact rows;
dynamic producers and checker limitations are explicit;
P1–P33 and flag/failure rows have status/evidence/owner;
V1–V26 have current dispositions;
CT10/CT11 matrix is recorded;
next implementation slice is selected without runtime edits.
```

### Artifacts

- this S3 implementation subplan;
- `worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md`;
- parent workplan S3 evidence update at close;
- `HANDOFF.md` update at close;
- `knowledge/llms.txt` index update for new artifacts;
- temporary probes outside the repository only.

### Contracts

- S3-CT1 through S3-CT6 are `PLANNED` before execution and `VERIFIED` only
  after the audit report and mutation evidence exist;
- no runtime claim is upgraded solely from a checker PASS;
- no deployment claim is upgraded above L2 without S4/S7 evidence;
- all remaining gaps have one owner slice or an explicit defer reason.

### Negative proof

The S3 audit is invalid if:

- removing a representative producer leaves the report/inventory unchanged;
- a consumer-only test is presented as producer proof;
- a base/candidate/S2 status is not source-labelled;
- a path is marked covered without a root/oracle/kill-check;
- a forced failure is classified only by a logger warning;
- the audit mutates the active repository or prints sensitive body files.

## 10. Review gate

The required review pass is complete:

- [x] every source/file/symbol reference is current or marked NEW;
- [x] all goals map to contracts, steps, artifacts, and kill-checkable evidence;
- [x] every signal contract is two-sided or explicitly deferred;
- [x] P1–P33 and S3-P1–S3-P9 have coverage or explicit defer reasons;
- [x] no step authorizes runtime/test changes;
- [x] B0/C0/S2 provenance cannot be silently mixed;
- [x] failure-policy and hygiene audits have C3/negative proof;
- [x] research-note dispositions are complete;
- [x] no blocking Q remains;
- [x] exact artifact inventory and rollback are present.

Review report:

```text
worklogs/implementation-plans/cli-trace-S3-plan-review-report.md
review verdict: PASS — READY FOR AUDIT EXECUTION
```

Runtime implementation remains forbidden in S3.

## 11. Artifacts inventory

| Artifact | Path | Action | Owner |
|---|---|---|---|
| S3 subplan | `worklogs/implementation-plans/PLAN-cli-trace-S3-liveness-contract-audit.md` | add | S3.0 |
| S3 plan-review report | `worklogs/implementation-plans/cli-trace-S3-plan-review-report.md` | add after review | review gate |
| S3 liveness audit | `worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md` | add during audit execution | S3.6 |
| Parent plan update | `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` | update at close only | S3.6 |
| Handoff update | `worklogs/HANDOFF.md` | update at close only | S3.6 |
| Knowledge index | `knowledge/llms.txt` | update for new S3 artifacts | S3.6 |
| Temporary probes | `/tmp/fa-s3-*` | create/delete | S3.0–S3.5 |

## 12. Handoff

S3 is ready for plan review, not audit execution. The review must produce
`cli-trace-S3-plan-review-report.md` and either mark this plan `READY FOR AUDIT
EXECUTION` or list exact blockers. Do not edit runtime/tests until a separate
approved implementation subplan is created for the next owner slice.
