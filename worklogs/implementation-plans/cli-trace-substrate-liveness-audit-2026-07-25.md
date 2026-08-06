# S3 Liveness and Contract Audit — CLI/Formal-Trace Substrate

Plan: `worklogs/implementation-plans/PLAN-cli-trace-S3-liveness-contract-audit.md`

Parent plan: `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`

Previous slice evidence: `worklogs/implementation-plans/cli-trace-S2-verification-report.md`

Status: **PASS — AUDIT COMPLETE, NO RUNTIME EDITS**

Execution date: 2026-07-27

Audit type: evidence-only slice. No file under `src/`, `tests/`, or `scripts/`
was modified. All mutation probes ran in disposable copies under `/tmp/fa-s3/`.

## 0. Executive result

The S2 session/authority wiring holds up under source-level and mutation
evidence: the authority read-fallback findings (V3, V4), the counter-ordering
finding (V2 for the durable path), the run-identity findings (V7, V26), and the
derived-read side effect (V5) are **confirmed fixed** by probe, not by prose.

The audit's primary negative result is about the **verification instruments**,
not the runtime. Both shipped contract checkers report `PASS` on a tree where a
real producer has been deleted, and one of them reports a "C1 tested" count that
is arithmetically impossible (20 tested out of 16 existing types). Concretely:

| # | Finding | Severity | Evidence |
|---|---|---|---:|
| S3-F1 | `check_log_kind_contract.py` output is **byte-identical** before and after deleting the real `subagent_spawn_done` producer. The checker's own kill-check is vacuous. | P0 (instrument) | §5.2 K2 |
| S3-F2 | `check_producer_consumer_contract.py` reports `C1 tested: 20` against 16 EventType literals; 5 entries are not EventTypes. **Re-verified: cosmetic only** — CHECK 3 iterates `event_types`, so pass/fail is unaffected. Superseded by S3-F14. | P2 (cosmetic) | §4.3, §12b |
| S3-F3 | CHECK 3 dual-write proves only file-level co-occurrence. **3 `run_stopped` producer sites in `loop.py` have no `emit()` on any path out of `run_session`**, yet the checker prints "All CONSOLE_MIRROR_KINDS have dual-write". A 4th flagged site (`state.py:515` `tool_call`) is paired across a call boundary and is NOT a defect — see §4.2. | P1 (instrument) | §4.2 |
| S3-F4 | `subagent_spawn_done` is reported "💤 NO producer found (may be planned/dead)" but has a **real, test-covered producer** at `spawn_subagent.py:72` via a resolvable local variable. The dormancy label is a false negative. | P1 | §4.2 |
| S3-F5 | `cost_alert` is the only genuinely dormant EventType: 0 producers, handler present at `output.py:396`. Correctly labelled. | P2 (confirmed dormant) | §4.1 |
| S3-F6 | V1 duplicate event IDs reproduce: two `EventLog` instances on one DB both allocate `ev-000001`; DB has no `UNIQUE(event_id)`. **Re-verified as LATENT** — the per-instance lock holds (8/8 unique single-instance); it needs a stale long-lived handle, and `cli.py:1742` constructs late. | P0 latent (runtime) | §6 V1, §12b |
| S3-F7 | V15 write-path asymmetry reproduces: `edit_file.py` has **no conflict check at all**, while `write_file.py` checks before write. | P0 (runtime) | §6 V15 |
| S3-F8 | V12 hygiene bug is failure-only **and escapes the checkout**: the test chmods `Path(install_mod.__file__)` — the pip-installed editable package — so a failure dirties the *installed* repo, not the tree under test. Restored by a trailing statement with no `try/finally`. | P1 → P0 blast radius | §7.2, §12b |
| S3-F9 | The `run_session` root emits **zero** console events on a hook-denial stop while writing a durable `run_stopped` row — proven at runtime with an attached bus (K4), not inferred from source. Operator sees a silent stop. | P1 (runtime) | §5.3 K4 |

Five further findings (S3-F10..S3-F14) came out of an adversarial
re-verification pass; three original findings were corrected, one downgraded.
See **§12b**. The most consequential additions: a single git commit silently
disables Blackboard conflict detection (S3-F10); an agent-facing observability
tool still reads the unauthoritative JSONL mirror (S3-F13); and CHECK 3 stays
green after every assertion in the C1 producer test is removed (S3-F14).

The full local gate is otherwise green and hygienic: **2014 passed, 15 skipped**,
zero tracked-file delta, zero untracked artifacts.

One structural suspicion was **retracted** during the audit rather than shipped:
the `tool_call` mirror site at `state.py:515` looked durable-only under
intra-function analysis but is correctly paired across a call boundary at the
`drive_session` root (§4.2, K1, K4). Reporting it as a defect would have sent S6
to “fix” working code.

**Selected next slice (S3-G6): S5 — authority correctness**, leading with V1
(atomic event-id allocation) and V15/V17 (mutation-path conflict symmetry). The
checker defects S3-F1..S3-F3 are recorded here and assigned to a separate
approved checker subplan per S3-Q1; they are **not** repaired in S3.

## 1. Source provenance

### 1.1 Source views

Per §1.1 of the subplan, three named views were required. Two were constructible.

```text
B0 — base
  origin/main = 3668e758c1522645a1bfb70787ebf53f7ef170a7

S2 — subject (this audit's only current-claim source)
  HEAD   = 811502ee884aed556e075986ca4a1a09347848b6  ("s1-s2+s3plan")
  branch = formal-substrate++ (fetched as local `fs`)
  status = clean at audit start and audit end

C0 — candidate comparator
  UNAVAILABLE — see §1.2
```

**Deviation from plan §1.1, recorded rather than smoothed over.** The subplan
describes S2 as an *uncommitted active worktree* on branch
`fa/20260725-session-authority-debug-wiring` with `HEAD == origin/main`. In the
audited source, S2 is **committed** as `811502e` on branch
`formal-substrate++`, and `HEAD != origin/main`. The audit therefore identifies
the subject by commit SHA rather than by working-tree diff. This is a stronger
provenance anchor, not a weaker one, but the plan's §1.1 text is now stale and
is flagged for correction at close.

### 1.2 C0 unavailability

The candidate patch named in HANDOFF is
`/home/user/backups/First-Agent-dev-20260725Tcandidate-diff-from-3668e758...patch`
(23987 bytes, SHA-256 `ad975712a055697b6089c32f4e72c5f3258d460e98a40a40dd4b4aefff5f9070`).
That path is host-local to the operator machine and is not reachable from this
audit environment. Per **S3-Q2**, C0 is recorded as **unavailable**; no candidate
status is reconstructed from prose, and no row in this report carries a
candidate-derived claim.

### 1.3 Audited source snapshot

Line counts and content hashes at audit time. Per **S3-Q5**, every line number
in this report is valid only against these hashes.

| File | Lines | SHA-256 (first 16) |
|---|---:|---|
| `src/fa/output.py` | 412 | `sha256:7cd8bcfc7b58258b` |
| `src/fa/inner_loop/state.py` | 620 | `sha256:079489b7d29506ff` |
| `src/fa/inner_loop/coder_loop.py` | 1651 | `sha256:8fb84b04483eccf4` |
| `src/fa/inner_loop/loop.py` | 531 | `sha256:36b1d232753c52f3` |
| `src/fa/inner_loop/tools/spawn_subagent.py` | 281 | `sha256:72896fb937f77552` |
| `src/fa/inner_loop/session_db.py` | 748 | `sha256:0ec2d6b72295f2de` |
| `src/fa/blackboard/blackboard.py` | 346 | `sha256:866c6ef007d17882` |
| `src/fa/cli.py` | 2872 | `sha256:4362aee8a87ddb1e` |
| `src/fa/stats.py` | 900 | `sha256:cb1ed194c8c29b33` |
| `src/fa/inner_loop/subagent_runner.py` | 344 | `sha256:f1a2e032c5f7a789` |
| `src/fa/inner_loop/tools/edit_file.py` | 234 | `sha256:8c4b15f484ace387` |
| `src/fa/workspace/worktree_manager.py` | 251 | `sha256:4b11dd9ea60a947b` |
| `scripts/fa-entrypoint.sh` | 307 | `sha256:29b4134146239a6e` |
| `scripts/check_producer_consumer_contract.py` | 221 | `sha256:fc64dd135858c781` |
| `scripts/check_log_kind_contract.py` | 260 | `sha256:6f01bd971a21e08c` |

### 1.4 Pre/post audit tree state

```text
pre-audit   git status --short : (empty)
post-audit  git status --short : (only this report, untracked)
env         HOME=/home/user  NO_COLOR=<unset>  FA_DEBUG_LLM_BODIES=<unset>
snapshot    /tmp/fa-s3/pre-audit-snapshot.txt
```

Note: `git status` showed four `100755 → 100644` mode changes on
`src/fa/hygiene/hooks/*` **at clone time**, before any audit command ran. These
were restored with `git checkout --` before the snapshot. Root cause is
characterised in §7.2 (V12) — it is a checkout/umask artifact of the sandbox, and
independently a latent test bug.

### 1.5 Audit instruments (disposable, not added to the repo)

Per §NON-GOALS, no checker was added to the repository. Four probes were written
under `/tmp/fa-s3/` and are reproduced in §11.

| Probe | Purpose |
|---|---|
| `/tmp/fa-s3/inventory.py` | AST inventory of definitions, emit sites, append sites, handlers, with local-variable resolution |
| `/tmp/fa-s3/dualwrite.py` | Branch-level dual-write correspondence for `CONSOLE_MIRROR_KINDS` |
| `/tmp/fa-s3/c1_audit.py` | Classifies each EventType's test evidence as C1-rooted vs consumer-constructed |
| `/tmp/fa-s3/logkind_table.py` | Joins all 33 LogKinds to producers, derived consumers (AST dispatch-arm match), mirror status, tests |
| `/tmp/fa-s3/k4_probe.py` | Behavioural `run_session` probe: durable vs console channel on hook-denial stop |
| `/tmp/fa-s3/probe_v.py` | Forced-failure probes for residual V-findings |

**Instrument self-correction (recorded for honesty).** The first version of
`inventory.py` matched only `emit(OutputEvent(...))` and reported 29 emit sites.
That shape is itself a false-negative generator: it missed `emit(event)` at
`state.py:309` (queued-warning flush) and the `_emit_subagent_event` helper
indirection. The probe was corrected to record *every* `.emit(<arg>)` plus
emit-helper calls before any finding in this report was drawn. An audit
instrument with the same blind spot as the tool it audits proves nothing.

## 2. Checker readiness — reproduced results

Both shipped checkers were run unmodified against the S2 subject.

```text
python scripts/check_producer_consumer_contract.py     → exit 0, PASS
  EventType literals: 16
  ConsoleRenderer handlers: 16
  Producer emit() calls: 31 across 15 types
  C1 tested: 20 types
  cost_alert: DORMANT

python scripts/check_log_kind_contract.py              → exit 0, PASS
  LogKind members: 33
  CONSOLE_MIRROR_KINDS members: 15
  log.append producers: 30 distinct kinds
  soft orphans: service_unavailable, subagent_spawn_done, timeout
```

These reproduce the subplan §1.2 numbers **exactly**. The subplan's warning that
they are "not sufficient proof" is upheld and now demonstrated, not asserted —
see §4.2, §4.3, and the kill-checks in §5.2.

## 3. Hybrid AST inventory (S3.1)

### 3.1 Definitions

| Symbol | File:line | AST form | Members |
|---|---|---|---:|
| `EventType` | `output.py:49–65` | `Assign` (Literal[...]) | 16 |
| `LogKind` | `output.py:75–115` | `Assign` (Literal[...]) | 33 |
| `CONSOLE_MIRROR_KINDS` | `output.py:126–142` | **`AnnAssign`** (frozenset) | 15 |

Both `Assign` and `AnnAssign` forms were handled as the plan requires;
`CONSOLE_MIRROR_KINDS` is the `AnnAssign` case a naive `Assign`-only walker
would drop entirely.

### 3.2 Producer-site totals — AST vs checker

| Measure | Shipped checker | AST inventory | Agreement |
|---|---:|---:|---|
| EventType emit sites | 31 | 31 | numerically equal, **compositionally different** (§4.3) |
| EventType producing types | 15 | 15 | equal |
| `log.append(kind=)` sites | not counted | 50 | — |
| Distinct literal LogKinds produced | 30 | 30 | equal |
| Dynamic/indirect emit sites | not modelled | 5 | checker blind spot |

### 3.3 Non-literal producer sites (the part regex cannot see)

| File:line | Function | Shape | Resolution |
|---|---|---|---|
| `state.py:309` | `attach_output_bus` | `output_bus.emit(event)` | **indirect-arg** — flushes queued bootstrap `OutputEvent`s; type not visible at the call |
| `spawn_subagent.py:65` | `_emit_subagent_event` | `output_bus.emit(OutputEvent(type=event_type))` | **dynamic-param** — type is a function parameter |
| `spawn_subagent.py:84` | `_record_subagent_completion` | `_emit_subagent_event(session, "subagent_end", …)` | resolved via helper call |
| `spawn_subagent.py:118` | `_handle_subagent_runner_error` | `_emit_subagent_event(session, "subagent_end", …)` | resolved via helper call |
| `spawn_subagent.py:192` | `_handle_spawn_subagent` | `_emit_subagent_event(session, "subagent_start", …)` | resolved via helper call |
| `spawn_subagent.py:72` | `_record_subagent_completion` | `session.log.append(kind=kind)` where `kind` is a local `if/else` | **resolved-local** → `{subagent_spawn_done, subagent_spawn_fail}` |

The last row is the source of **S3-F4**. The shipped checker cannot resolve it
and therefore mislabels a live producer as dormant.

## 4. Two-sided tables (S3.2)

### 4.1 EventType — definition → producer → consumer → proof

Consumer column is `ConsoleRenderer._handle_<type>` in `output.py`.
C1 verdict from `/tmp/fa-s3/c1_audit.py`; L-level per parent §2.3 conventions.

| EventType | Producer sites (`src/fa/`) | # | Consumer | C1 evidence | Status |
|---|---|---:|---|---|---|
| `session_start` | `coder_loop.py:507` | 1 | `:240` | `test_event_type_c1_producers.py` asserted | **L3** |
| `turn_start` | `coder_loop.py:589` | 1 | `:244` | `test_event_type_c1_producers.py` asserted | **L3** |
| `llm_response` | `coder_loop.py:1240` | 1 | `:249` | `test_event_type_c1_producers.py` asserted | **L3** |
| `tool_call` | `coder_loop.py:1557` | 1 | `:269` | `test_event_type_c1_producers.py`; kill-check K1 **verified** | **L3** |
| `hook_deny` | `coder_loop.py:612`, `:1406` | 2 | `:305` | `test_event_type_c1_producers.py` asserted | **L3 (1 of 2 paths)** |
| `api_retry` | `coder_loop.py:1178`, `:1313`, `:1337`, `:1367` | 4 | `:309` | `test_observability_fix_p4.py` asserted | **L2/L3 — 4 paths, 1 proven** |
| `session_end` | `coder_loop.py:549` (in `finish`) | 1 | `:316` | `test_observability_fix_p4.py` asserted | **L3** |
| `context_warn` | `coder_loop.py:692`, `:747`, `:764`, `:993`, `:1085` | 5 | `:342` | `test_observability_edge_cases.py`, `_fix_p4` | **L2/L3 — 5 paths, partial** |
| `compaction_warning` | `coder_loop.py:727` | 1 | `:351` | `test_compaction_c1_wiring.py` asserted | **L3** |
| `config_warning` | `state.py:320` direct + `state.py:309` queue flush | 2 | `:360` | `test_config_warning_c1.py` — `SessionState` root, not `drive_session` | **L2 — C1-STATE-ROOT-ONLY** |
| `compaction_start` | `coder_loop.py:799`, `:876` | 2 | `:366` | `test_compaction_c1_wiring.py` asserted | **L3 (1 of 2 paths)** |
| `compaction_end` | `coder_loop.py:827`, `:858`, `:933`, `:975`, `:1065` | 5 | `:371` | `test_observability_edge_cases.py` asserted | **L2/L3 — 5 paths, partial** |
| `subagent_start` | `spawn_subagent.py:192` (via helper `:65`) | 1 | `:382` | `test_event_type_c1_producers.py` asserted | **L3** |
| `subagent_end` | `spawn_subagent.py:84`, `:118` (via helper `:65`) | 2 | `:387` | `test_event_type_c1_producers.py` asserted | **L3 (1 of 2 paths)** |
| `cost_alert` | **none** | 0 | `:396` | none | **DORMANT — consumer-only, confirmed** |
| `loop_warn` | `cli.py:2013`, `coder_loop.py:1011`, `:1480` | 3 | `:400` | `test_observability_fix_p4.py`, `test_s23_circuit_breaker_loop_warn.py` | **L3 (2 of 3 paths)** |

**Path-sensitivity result.** 31 producer sites exist across 15 types; named C1
assertions reach **at most one site per type**. Per the tests-writing skill's
path-sensitivity law, the 16 unproven sibling sites (`api_retry` ×3,
`context_warn` ×4, `compaction_end` ×4, `hook_deny` ×1, `compaction_start` ×1,
`subagent_end` ×1, `loop_warn` ×1, and others) are **PARTIAL**, not covered.
Owner: **S6**.

`cost_alert` disposition per **S3-Q3**: classify as dormant with owner; do
**not** add a producer to improve the count. Producer would be
`observability/cost_guardian.py`, which currently writes only the
`cost_observation` LogKind. Owner: S6, or explicit deletion of the handler.

### 4.2 LogKind — full 33-member inventory

Plan §2 TO-BE requires one row per LogKind. Producer sites from the AST
inventory; derived consumers matched by AST comparison-arm extraction over
`stats.py` and `global_history.py` (not grep — a `kind == "X"` dispatch arm is
the actual consumer contract). "Test files" counts files under `tests/`
containing the kind literal; it is a breadth signal, not producer proof.

| LogKind | Producer site(s) in `src/fa/` | # | Mirror | Derived consumer | Tests | Status |
|---|---|---:|:---:|---|---:|---|
| `run_started` | `coder_loop.py:494` | 1 | — | `stats.py:366` | 9 | LIVE |
| `run_stopped` | `coder_loop.py:602, 776, 1035, 1097, 1257, 1329, 1360, 1395, 1488, 1580`; `loop.py:288, 420, 481` | 13 | ✅ | `stats.py:539` | 11 | **DURABLE-ONLY GAP (3 sites)** |
| `session_summary` | `coder_loop.py:541` | 1 | — | `stats.py:532` | 7 | LIVE |
| `user_msg` | `coder_loop.py:493` | 1 | — | `stats.py:529` | 4 | LIVE |
| `model_msg` | `coder_loop.py:1436` | 1 | — | `stats.py:526` | 6 | LIVE |
| `usage` | `coder_loop.py:530` | 1 | — | `stats.py:381`, `global_history.py:224` | 16 | LIVE |
| `provider_attempt` | `coder_loop.py:1145, 1195, 1278` | 3 | — | `stats.py:393` | 3 | LIVE |
| `llm_call` | `coder_loop.py:1213` | 1 | — | none | 1 | LIVE (audit-only) |
| `tool_call` | `state.py:515` | 1 | ✅ | `stats.py:369`, `global_history.py:231` | 16 | LIVE — paired cross-function (see note) |
| `tool_result` | `state.py:605` | 1 | — | `stats.py:415` | 16 | LIVE |
| `hook_decision` | `loop.py:71` | 1 | — | `stats.py:403` | 2 | LIVE |
| `loop_guard_warn` | `cli.py:884, 2003` | 2 | — | `stats.py:411` | 4 | LIVE |
| `audit` | `hooks/builtin.py:185` | 1 | — | none | 2 | LIVE (audit-only) |
| `context_budget_warn` | `coder_loop.py:689, 744` | 2 | ✅ | `stats.py:472` | 6 | LIVE |
| `context_budget_hard_stop` | `coder_loop.py:761, 1025, 1079` | 3 | ✅ | `stats.py:480` | 8 | LIVE |
| `config_warning` | `state.py:315` | 1 | ✅ | none | 2 | LIVE |
| `compaction_warning` | `coder_loop.py:721` | 1 | ✅ | `stats.py:490` | 5 | LIVE |
| `compaction_circuit_breaker` | `coder_loop.py:965` | 1 | ✅ | `stats.py:500` | 5 | LIVE |
| `compaction_stage2_start` | `coder_loop.py:792` | 1 | ✅ | `stats.py:507` | 3 | LIVE |
| `compaction_stage2_done` | `coder_loop.py:820` | 1 | ✅ | `stats.py:430` | 5 | LIVE |
| `compaction_stage2_error` | `coder_loop.py:851` | 1 | ✅ | `stats.py:439` | 3 | LIVE |
| `compaction_stage3_start` | `coder_loop.py:869` | 1 | ✅ | `stats.py:516` | 3 | LIVE |
| `compaction_stage3_done` | `coder_loop.py:922` | 1 | ✅ | `stats.py:447`, `global_history.py:233` | 5 | LIVE |
| `compaction_stage3_error` | `coder_loop.py:1058` | 1 | ✅ | `stats.py:456` | 2 | LIVE |
| `subagent_spawn_start` | `spawn_subagent.py:174` | 1 | — | none | 3 | LIVE (audit-only) |
| `subagent_spawn_done` | `spawn_subagent.py:72` **(dynamic)** | 1 | ✅ | `stats.py:466` | 7 | LIVE — checker false negative |
| `subagent_spawn_fail` | `spawn_subagent.py:72` **(dynamic)**, `:109` | 2 | ✅ | `stats.py:468` | 5 | LIVE |
| `recovery_action` | `hooks/recovery_observers.py:77` | 1 | — | none | 2 | LIVE (audit-only) |
| `verification` | `hooks/builtin.py:253` | 1 | — | none | 1 | LIVE (audit-only) |
| `cost_observation` | `observability/cost_guardian.py:250` | 1 | — | none | 1 | LIVE (audit-only) |
| `telemetry` | `coder_loop.py:427`, `state.py:589` | 2 | — | none | 4 | LIVE (audit-only) |
| `service_unavailable` | **none** | 0 | — | none | 4 | **DORMANT** |
| `timeout` | **none** | 0 | — | none | 2 | **DORMANT** |

Totals: 33 members · 31 with producers · 50 append sites · 2 dormant ·
7 intentional audit-only kinds (no derived consumer, no console mirror — per
S3.2 these are recorded as intentional, **not** forced into console output) ·
2 durable-only mirror gaps.

**Producer-file breadth.** Append sites span 8 files: `coder_loop.py` (33),
`loop.py` (4), `state.py` (4), `spawn_subagent.py` (3), `cli.py` (2),
`hooks/builtin.py` (2), `hooks/recovery_observers.py` (1),
`cost_guardian.py` (1). The EventType checker's hard-coded producer list covers
only 5 files and omits `loop.py`, `hooks/builtin.py`, and
`recovery_observers.py` entirely.

**Members with no literal producer** (checker's soft orphans):

| LogKind | Verdict | Evidence |
|---|---|---|
| `service_unavailable` | **CONFIRMED DORMANT** | no producer, literal or dynamic |
| `timeout` | **CONFIRMED DORMANT** | no producer, literal or dynamic |
| `subagent_spawn_done` | **FALSE NEGATIVE — live producer** | `spawn_subagent.py:72`, dynamic `kind` resolved to `{subagent_spawn_done, subagent_spawn_fail}`; asserted by `test_subagent_termination_wiring.py:293`, `test_inner_loop_tools.py:272`, `test_slice5_6_7_wiring.py:397` |

**Branch-level dual-write for the 15 mirror kinds** (30 mirror-kind append
sites analysed). The shipped CHECK 3 asks "does an emit of the mapped EventType
exist anywhere in the same *file*". This audit asks the stronger question the
plan mandates: "is there an emit on the same *control-flow branch*".

| Verdict | Sites | Meaning |
|---|---:|---|
| `SAME-BLOCK` | 22 | append and emit in the same statement block — genuine dual-write |
| `ANCESTOR-BLOCK+1/+2` | 4 | emit exists in an enclosing block; correct but conditional-dependent |
| **`NO-EMIT-IN-FUNCTION`** | **4** | no emit in the enclosing function — **3 confirmed gaps + 1 cleared on call-graph review** |

Per-member breakdown (plan §2 TO-BE: one row per `CONSOLE_MIRROR_KINDS` member):

| Mirror kind | Mapped EventType | Producer sites | Branch verdicts | Status |
|---|---|---:|---|---|
| `compaction_circuit_breaker` | `compaction_end` | 1 | SAME×1 | OK |
| `compaction_stage2_start` | `compaction_start` | 1 | SAME×1 | OK |
| `compaction_stage2_done` | `compaction_end` | 1 | SAME×1 | OK |
| `compaction_stage2_error` | `compaction_end` | 1 | SAME×1 | OK |
| `compaction_stage3_start` | `compaction_start` | 1 | SAME×1 | OK |
| `compaction_stage3_done` | `compaction_end` | 1 | SAME×1 | OK |
| `compaction_stage3_error` | `compaction_end` | 1 | SAME×1 | OK |
| `compaction_warning` | `compaction_warning` | 1 | SAME×1 | OK |
| `context_budget_warn` | `context_warn` | 2 | SAME×2 | OK |
| `context_budget_hard_stop` | `context_warn` | 3 | SAME×3 | OK |
| `config_warning` | `config_warning` | 1 | ANCESTOR×1 | OK — emit at `state.py:320`, or queued to `:309` when no bus is attached yet |
| `subagent_spawn_done` | `subagent_end` | 1 | ANCESTOR×1 | OK — emit via helper at `spawn_subagent.py:84` |
| `subagent_spawn_fail` | `subagent_end` | 2 | ANCESTOR×2 | OK — emits at `:84` / `:118` |
| **`run_stopped`** | `session_end` | 13 | SAME×9 · ANCESTOR×1 · **NO-EMIT×3** | **GAP — `loop.py:288, 420, 481`** |
| `tool_call` | `tool_call` | 1 | NO-EMIT×1 *(intra-function)* | OK — paired at composition root; see note below |

**Cross-function note on `tool_call` — corrected during audit.** This row is the
subtlest in the slice and an intra-function analysis alone gets it wrong. The
mechanics, traced through the real call graph:

```text
drive_session (coder_loop.py)
  └─ run_session (called at coder_loop.py:1507)
        └─ _execute_one_sequential  → state.record_tool_call  (loop.py:257)
        └─ _execute_batch_parallel  → state.record_tool_call  (loop.py:323)
                                        └─ log.append(kind="tool_call")  (state.py:515)
  └─ then, per returned result:      output.emit(type="tool_call")  (coder_loop.py:1557)
```

So the durable row and the console event **are** paired for every executed tool
call on the shipped path — but the pairing is realised *across a call boundary*
(`loop.py` appends, `coder_loop.py` emits after `run_session` returns), not
within one function. `coder_loop.py:1551` is a separate, narrower path: the
synthetic-padding branch for calls skipped by the iteration cap.

Therefore `tool_call` is **NOT a genuine dual-write gap** — my probe's
`NO-EMIT-IN-FUNCTION` verdict for `state.py:515` is a **true positive for the
question asked** (intra-function) and a **false alarm for the contract**
(cross-function pairing at the composition root). It is recorded here as an
instrument limitation, not a runtime defect. Kill-check K1 (§5.1) independently
confirms the pairing is real and test-enforced.

The three `run_stopped` sites in `loop.py` are **not** rescued by the same
argument: they occur on hook-denial branches that `break`/`return` *inside*
`run_session`, and no emit follows them on the way out. That gap stands.

Method note this exposes: branch-level analysis is strictly stronger than the
shipped file-level check, but still weaker than call-graph analysis. Both
weaker forms must be reported with their limits stated rather than as verdicts.

The four flagged sites, after call-graph review:

| Kind | Site | Function | Consequence |
|---|---|---|---|
| `run_stopped` | `loop.py:288` | `_execute_one_sequential` | AFTER_TOOL_EXEC hook denial stops the run; operator console shows nothing |
| `run_stopped` | `loop.py:420` | `_execute_batch_parallel` | same, parallel batch path |
| `run_stopped` | `loop.py:481` | `run_session` | same, BETWEEN_ROUNDS gate |
| `tool_call` | `state.py:515` | `record_tool_call` | **NOT A GAP** — emit follows at `coder_loop.py:1557` once `run_session` returns |

`src/fa/inner_loop/loop.py` contains **zero** `emit` calls and has no
`output_bus` reference at all — the deterministic `run_session` root has no live
channel whatsoever. CHECK 3 passes anyway because `run_stopped` maps to
`session_end`, and `session_end` is emitted in a *different file*
(`coder_loop.py:549`).

This is **S3-F3**. Whether `loop.py` *should* have a live channel is a product
policy question — `run_session` is the deterministic non-LLM root (P19) and may
be intentionally console-silent. Per the **STOP RULE**, S3 does not decide this.
Recorded as an open question **Q12** in §9 and assigned to S6.

### 4.3 Producer/consumer checker comparison

| Checker claim | Audit finding | Classification |
|---|---|---|
| `Producer emit() calls: 31` | AST also finds 31 — but the checker counts `config_warning` twice in `state.py` (lines 316 and 320, where 316 constructs and 320 emits) and reaches `subagent_start`/`subagent_end` through a hard-coded special case, not analysis. AST counts 1 config_warning emit + 3 resolved helper calls. | **Right total, wrong composition — coincidental agreement** |
| `C1 tested: 20 types` | Only 16 EventTypes exist. The set includes `plan`, `note`, `verifier`, `researcher`, `file_version` — none is an EventType. Cause: the regex `type="([a-z_]+)"` harvests any `type=` kwarg in any test file that mentions `drive_session(` or `SessionState(`. | **False positive — S3-F2** |
| `CHECK 3: all dual-write ✅` | 3 `run_stopped` sites in `loop.py` have no emit on any exit path. (A 4th intra-function hit, `state.py:515`, is paired cross-function and cleared.) | **False positive — S3-F3** |
| `subagent_spawn_done` dormant | Live, dynamically-produced, test-covered. | **False negative — S3-F4** |
| `cost_alert` dormant | Correct. | **True positive** |
| Producer file list is hard-coded (5 files) | Any producer added outside those 5 files is invisible. `loop.py`, `hooks/builtin.py`, `recovery_observers.py` all produce LogKinds and are absent from the EventType producer list. | **Structural limitation** |

Per **S3-Q1** the default holds: **no checker edit in S3**. These are recorded
as demonstrated defects and assigned to a separate approved checker subplan.

## 5. Kill-checks (mandated negative proof)

### 5.1 K1 — literal producer removal

Disposable copy `/tmp/fa-s3/kc/k1`. Removed the `tool_call` emit block at
`coder_loop.py:1557–1570`, replaced with `pass`, syntax verified.

```text
AST inventory        tool_call sites: 1 → 0            CHANGED ✅
check_producer_consumer_contract.py
                     "Producer emit() calls: 31 across 15 types"
                     → "30 across 14 types"
                     → ❌ tool_call CONSUMER ONLY
                     → exit 1, FAIL                    DETECTED ✅
pytest test_event_type_c1_producers.py -k tool_call
                     → FAILED test_tool_call_emitted   NON-VACUOUS ✅
```

**K1 verdict: PASS.** Inventory changed, checker flipped to FAIL, C1 test failed.
The `tool_call` C1 claim is genuine, kill-checked product proof.

**Sub-finding.** An earlier K1 attempt commented the block out with a `#KILLED`
prefix, producing a file that no longer parsed. The regex checker still printed
`PASS` on that unparseable source. A checker that cannot distinguish live code
from commented-out or syntactically broken code is not an AST-grade instrument.
Filed under S3-F1/S3-F2 as the same root cause.

### 5.2 K2 — dynamic producer removal

Disposable copy `/tmp/fa-s3/kc/k2`. Removed the `session.log.append(kind=kind)`
block at `spawn_subagent.py:72–83`, syntax verified.

```text
AST inventory        lost kind: subagent_spawn_done    CHANGED ✅
check_log_kind_contract.py
                     diff(before, after) = EMPTY
                     still prints "💤 subagent_spawn_done — NO producer found"
                     still exits 0, PASS               NOT DETECTED ❌
pytest test_subagent_termination_wiring.py
                     → FAILED
                       test_subagent_spawn_and_cleanup_via_drive_session
                       "Expected subagent_spawn_done event"  NON-VACUOUS ✅
```

**K2 verdict: audit instrument PASS, shipped checker FAIL.** This is the
sharpest result in the slice: the checker's output is *byte-identical* across
producer deletion, which is precisely the S3-CT3 invalidity condition applied to
the checker itself. The C1 test layer catches what the checker cannot — the
tests are the real gate, and the checker's green is decorative for this kind.

### 5.3 K4 — behavioural proof of the `run_stopped` console gap (S3-CT4)

S3-CT4 requires a representative kill-check per audited signal family. The
`run_stopped` gap in §4.2 was found structurally (no emit on any exit path out
of `run_session`); a structural finding must be confirmed behaviourally before
it enters the gap register, or it is just an assertion about the AST.

Probe `/tmp/fa-s3/k4_probe.py` boots the **real** `run_session` root with a real
`ToolRegistry`, a real `HookRegistry`, a real `SessionDatabase`/`EventLog`, and
an `EventBus` with a recording listener attached via
`state.attach_output_bus(bus)`. A `GuardMiddleware` denies at
`AFTER_TOOL_EXEC`, which is exactly the branch at `loop.py:288`.

```text
bus attached   : True
DURABLE_KINDS  : ['tool_call', 'hook_decision', 'run_stopped', 'telemetry', 'tool_result']
CONSOLE_EVENTS : []
VERDICT        : GAP-CONFIRMED (durable run_stopped, zero console events)
```

**K4 verdict: gap is real at runtime, not merely structural.** The bus is
attached and functional, the durable `run_stopped` row is written, and the
operator console receives **nothing** — not just "no `session_end`", but zero
events of any type from this root. An operator watching stderr sees a session
stop with no explanation.

This also sharpens the §4.2 `tool_call` clearance: the durable `tool_call` row
appears in `DURABLE_KINDS` above with no console counterpart, because this probe
calls `run_session` **directly**. Under the shipped `drive_session` root the
emit follows at `coder_loop.py:1557`. Both statements are now evidenced rather
than argued: the pairing exists at the composition root and is absent from the
bare loop root.

### 5.4 K3 — audit-report kill-check (S3-CT1)

Required: the report must not be invariant under producer removal. Satisfied by
construction — §4.1, §4.2, and §3.3 rows are generated from the AST inventory,
which changed under both K1 and K2 (§5.1, §5.2). A report regenerated against
either killed tree loses the corresponding row.

## 6. Residual V1–V26 disposition (S3.4)

Method: source read plus forced-failure probe in temp dirs
(`/tmp/fa-s3/probe_v.py`, raw output at `/tmp/fa-s3/probe-v-output.txt`). No
tracked file was mutated. No fix was implemented.

| ID | Disposition | Current evidence | Owner |
|---|---|---|---|
| **V1** duplicate event IDs | **CONFIRMED — unchanged** | Probe: two `EventLog`s on one `SessionDatabase`, both returned `ev-000001`; DB holds 2 rows with duplicate `event_id`. Allocation is `_initial_next_id()` seeded per instance (`state.py:130,133`), not DB-atomic; no `UNIQUE(event_id)` constraint. | **S5 — P0, selected** |
| **V2** counter before write | **FIXED (durable path)** | `state.py:173–190` now writes the authoritative row *then* increments `_next_id`. Probe with forced `append_event_row` failure: `_next_id` stayed `1`, no DB row. **Residual:** `kind_counts` is still incremented *before* the write (`state.py:170`), so the probe left `{'tool_call': 1}` for an event that never committed. Narrower than the original finding but not closed. | **S5 — P1 residual** |
| **V3** EventLog mirror fallback | **FIXED** | `state.py:221–228`: injected DB is authority; empty DB returns empty (probe V3a: `FAIL-CLOSED`), read exception re-raises (probe V3b: `DatabaseError` propagated). Legacy non-injected path still falls back (probe V3c) — that is the documented legacy surface, not the production path. | closed for production path |
| **V4** Blackboard mirror fallback | **FIXED** | `blackboard.py:243–244` and `:286` re-raise when `_injected_session_db`. Symmetric with V3. | closed |
| **V5** derived read creates DB | **FIXED** | Probe: legacy JSONL-only session dir, before `['events.jsonl']`, after `['events.jsonl']` — no DB created. CLI now routes through `_discover_stats_sources` (`cli.py:2443`) + `parse_session_db` (`cli.py:2618`) with a non-creating read. | closed |
| **V6** `INSERT OR REPLACE` | **CONFIRMED** | 3 occurrences: `session_db.py:470, 495, 672`. Append-only language vs overwrite semantics unresolved. | S5/S6 |
| **V7** no run-identity binding | **FIXED** | Probe: two `EventLog`s with `run_id` `rA`/`rB` on one DB — A sees only `rA`, B only `rB`. `read_event_rows(run_id=...)` scopes reads; `append_event_row` raises `session_db_identity_mismatch` on session mismatch (`session_db.py:314–320`). | closed |
| **V8** fail-open init matrix | **CONFIRMED** | `state.py:322` `__post_init__` retains the broad catch matrix (Blackboard, telemetry, worktree, PTY, transaction, artifact store) with per-subsystem degradation and no single auditable policy. See §7.1. | S5 |
| **V9** workflow duration zero | **CONFIRMED** | `cli.py:1773` — `duration_ms=0,  # not tracked at workflow level yet`. | S8 |
| **V10** import-time `HOME` | **CONFIRMED** | `state.py:52`; probe resolved `DEFAULT_STATE_ROOT=/home/user/.fa/session-log` at import. | S5 (low) |
| **V11** `NO_COLOR` global mutation | **CONFIRMED** | `cli.py:1802` `os.environ["NO_COLOR"] = "1"`, never restored. | S7 (low) |
| **V12** suite dirties tracked modes | **CONFIRMED — failure-only** | See §7.2. Green suite leaves zero delta; a failure between `chmod` and the trailing restore leaks `100755 → 100644`. Reproduced deterministically. | S5/S7 — P1 |
| **V13** entrypoint clone failure continues | **FIXED (differently)** | `fa-entrypoint.sh` now routes failures to `_fail_to_standby` (lines 157, 221, 254, 257) rather than logging and continuing. | closed |
| **V14** debug-body schema incomplete | **NOT RE-PROBED — deferred** | Requires live provider path; S3 has no L3 deployment evidence. Per S3-Q4 remains `L2/PENDING`. | S4/S7 |
| **V15** `edit_file` no conflict check | **CONFIRMED — worse than described** | Probe: `edit_file.py` → `NO-CONFLICT-CHECK` (no `detect_conflict`/`_check_conflict` at all); `write_file.py` → `CHECK-BEFORE-WRITE`. The asymmetry is total, not merely ordering. | **S5 — P0, selected** |
| **V16** mismatched `session_db` accepted | **FIXED** | S2 added identity assertion; corroborated by `test_session_db_authority.py` and the `session_db_identity_mismatch` error class. | closed |
| **V17** wrong-root → continue mutation | **CONFIRMED** | `write_file._check_conflict()` still returns/continues on root mismatch or Blackboard error. | **S5 — P0, with V15** |
| **V18** subagent workspace fallback | **CONFIRMED** | `state.py:488–490` — on manager failure logs a warning and `return self.workspace_root`. Permission boundary changes on a failure path. | S5 |
| **V19** `isolated` silently downgraded | **CONFIRMED** | `worktree_manager.py:234–237` — `mode == "isolated"` prints a warning and returns `SharedDir`. Configuration truth gap. | S5 |
| **V20** cleanup failure swallowed | **CONFIRMED** | `state.py:492–497` — logs and returns; caller proceeds to success. | S6 |
| **V21** spawn-limit counter best-effort | **CONFIRMED** | `subagent_runner.py:109–116` — `increment_subagent_spawns()` failure is caught, logged, and the guard returns success. | S5 |
| **V22** check/increment not atomic | **CONFIRMED** | `subagent_runner.py:101–116` — read, compare, then separate increment. | S5 |
| **V23** live payload not redacted | **DEFERRED (operator decision)** | Unchanged; `coder_loop.py` passes `response.text` / `dict(call.params)` into `OutputEvent`. Not re-opened. | deferred |
| **V24** spawn_subagent shell breadth | **CONFIRMED** | Unchanged; `run_stateless()` uses `subprocess.run(..., shell=True)` with `permission="workspace"`. | S5/S6 |
| **V25** SandboxHook parent-root eval | **CONFIRMED** | Unchanged; gate and executor still disagree on the write root. | S5/S6 |
| **V26** entrypoint conflates identity | **FIXED** | `fa-entrypoint.sh` now separates `FA_SESSION_ID` (lines 156–162) from `FA_RUN_ID` (252–262), passing `--session-id` / `--run-id` to the CLI; `FA_RESUME` without `FA_SESSION_ID` fails to standby (257). | closed |

**Tally:** fixed 8 (V3, V4, V5, V7, V13, V16, V26, and V2 on the durable path);
confirmed-open 15; deferred 2 (V14, V23); partial 1 (V2 residual).

No S2-resolved finding was re-opened without source evidence, per exit criteria.

## 7. Failure-policy (CT10) and hygiene (CT11)

### 7.1 CT10 boundary matrix

| Boundary | Required policy | Current behavior | Matches? | Owner |
|---|---|---|:---:|---|
| `session.db` init/read/write | fail closed, structured | Injected DB re-raises on read failure; `append_event_row` raises `SessionDatabaseError` on identity mismatch; `event_count` raises `event_log_count_failed` | **YES** | — |
| JSONL mirror write | best effort, warning, never authority | `state.py:192–198` catches, logs warning, continues; DB row already committed | **YES** | — |
| Legacy JSONL / old DB | explicit unsupported diagnostic, no DB creation | `StatsSourceError("legacy_unsupported", …)` at `cli.py:2483`; probe confirmed no DB created | **YES** | — |
| Blackboard authority | same as EventLog, no mirror substitution | re-raises when injected (`blackboard.py:243, 286`) | **YES** | — |
| EventBus / renderer failure | preserve durable state, surface warning | `EventBus.emit` catches per-listener, `logger.error` with traceback, loop continues; durable write is independent | **YES** | — |
| telemetry / artifact analytics | derived best effort + warning | caught in `__post_init__` degradation matrix | **PARTIAL** — warning is a logger call, not a structured operator surface | S5 |
| PTY unavailable | fallback only if contract explicit and tested | `runtime/pty_pool.py:520` `tmux binary not found, falling back to pexpect` (observed live in the suite run); fallback is tested | **PARTIAL** — fallback works, contract not stated as policy | S5 |
| worktree isolation unavailable | **fail closed**, no silent downgrade | `isolated` → warning → `SharedDir` (V19); subagent workspace failure → main workspace (V18) | **NO — MISMATCH** | **S5 P0** |
| feature flag load | per-flag safety matrix | single broad catch in `__post_init__` (V8) | **NO — MISMATCH** | S5 |
| subagent spawn limit | deterministic admission | counter failure permits spawn (V21); check/increment non-atomic (V22) | **NO — MISMATCH** | S5 |

Three hard mismatches, all safety-relevant, all in the worktree/subagent family.
They cluster into one coherent S5 scope with V15/V17.

### 7.2 CT11 verification hygiene

Full gate in a disposable copy `/tmp/fa-s3/kc/gate`:

```text
python -m pytest tests/ -q -p no:cacheprovider
  → 2014 passed, 15 skipped, 1 warning in 108.49s

pre/post delta:
  git status --short          : empty → empty
  tracked file modes          : identical
  untracked artifacts created : 0
  only difference             : src/fa/hygiene/hooks/__pycache__ (gitignored)
```

**Green-path verdict: CLEAN.** V12 does not reproduce on a passing suite.

**Negative-fixture kill-check (required — a hygiene check that only ever sees a
green run is vacuous).** In a disposable copy, an `AssertionError` was injected
into `test_install_one_copy_fallback_target_is_executable` immediately after its
`source.chmod(...)`:

```text
PROBE-MODE-AFTER-CHMOD 0o644 src/fa/hygiene/hooks/pre-commit
post-test: 644 src/fa/hygiene/hooks/pre-commit
git diff --summary: mode change 100755 => 100644 src/fa/hygiene/hooks/pre-commit
```

**Root cause, exactly.** `tests/test_hygiene_hooks_install.py:229` chmods the
**tracked source** `src/fa/hygiene/hooks/pre-commit`, and restores it at line 243
as a plain trailing statement. There is no `try/finally` and no fixture teardown.
Any failure, error, or `-x` interruption between those lines leaks a tracked-mode
change into the working tree. The same shape appears at line 339 (operating on an
installed copy under `tmp_path`, which is safe).

This exactly explains the four dirty hook modes observed at clone time in §1.4.
The correct fix is a `monkeypatch`/fixture-scoped restore or a `tmp_path` copy of
the source — **not implemented in S3** (tests are a NON-GOAL). Owner: S5/S7.

## 8. Path matrix P1–P33 (S3.3)

Status vocabulary is exactly `VERIFIED | PARTIAL | UNVERIFIED | DEFERRED | N/A`.
No row is `VERIFIED` on local-only evidence where the parent assigns deployment
proof to S4/S7/S11 — those are capped at `PARTIAL` per **S3-Q4**.

| P# | Surface | Root | Test / probe | Oracle | Producer kill-check | Status | Owner |
|---|---|---|---|---|---|---|---|
| P1 | fresh single-role run | `_cmd_run` | `test_cli.py` (`_cmd_run`) | exit code + DB rows | not run for CLI root | **PARTIAL** (local only) | S7 |
| P2 | resume same run-id | `_cmd_run`, `EventLog` | `test_session_lifecycle.py:65` attach-reuse | manifest + authority reuse | none | **PARTIAL** | S5/S7 |
| P3 | no explicit run-id | `_cmd_run` / entrypoint | `test_session_lifecycle.py:38` | manifest + fresh run rows | none | **PARTIAL** | S7 |
| P4 | debug disabled | `_cmd_run` | `test_cli.py` matrix | no body file | none | **PARTIAL** | S4/S7 |
| P5 | debug enabled | `_cmd_run` | `test_debug_bodies.py` | counts only (no raw bodies) | none | **PARTIAL** — deployment pending | S4/S7 |
| P6 | provider success | `ProviderChain.request` | `test_providers_chain.py` | response + attempts | none | **PARTIAL** | S7 |
| P7 | transient fallback | `ProviderChain.request` | `test_providers_chain.py` | attempts/cooldown | none | **PARTIAL** | S7 |
| P8 | auth failure | `ProviderChain.request` | `test_providers_chain.py` | chain behavior | none | **PARTIAL** | S7 |
| P9 | request-shape fast-fail | `ProviderChain.request` | `test_providers_chain.py` | no sibling retry | none | **PARTIAL** | S7 |
| P10 | max-turn stop | `drive_session` | `test_coder_loop.py`, `test_cli.py` | stop reason + `run_stopped` | none | **PARTIAL** | S6 |
| P11 | hook deny before mutation | `_cmd_run` + hooks | `test_event_type_c1_producers.py:216` | `hook_deny` emit + DB | **K1-class proven for `tool_call`, not for `hook_deny`** | **PARTIAL** | S6 |
| P12 | budget, no compaction | `drive_session` | `test_s1_context_limit_fix.py` | `context_warn` | none | **PARTIAL** — 5 emit paths, 1 asserted | S6 |
| P13 | budget, with compaction | `drive_session` | `test_compaction_c1_wiring.py`, `test_s14_compaction_ssot.py` | `compaction_*` events | none | **PARTIAL** — 5 `compaction_end` paths, 1 asserted | S6 |
| P14 | console output | `EventBus` + `ConsoleRenderer` | `test_output.py` (consumer), C1 producer files | rendered stderr | K1 verified for `tool_call` | **PARTIAL** | S6 |
| P15 | quiet output | `QuietRenderer` | `test_cli.py` | stdout/stderr contract | none | **PARTIAL** | S7 |
| P16 | workflow linear | `_cmd_workflow` | `test_cli_ergonomics.py`, `test_workflow_artifacts.py` | artifact + exit | none | **PARTIAL** | S8 |
| P17 | workflow repair | `_run_repair` | `test_workflow_paths.py` | budget/route matrix | none | **PARTIAL** | S8 |
| P18 | workflow adaptive | `_run_adaptive` | `test_workflow_paths.py` | planner re-entry | none | **PARTIAL** | S8 |
| P19 | deterministic smoke | `_cmd_inner_loop_smoke` | `test_cli.py`, `test_inner_loop_runtime.py` | canonical artifact path | **K4 (§5.3)** | **PARTIAL** — §4.2/K4: this root emits zero console events | S6 |
| P20 | stats current run | `_cmd_stats` / `parse_session_db` | `test_stats.py`, `test_s19_stats_parsers.py` | DB-only read; probe V5 no-create | none | **VERIFIED (local)** | — |
| P21 | global-history projection | `_cmd_stats` / exporter | `test_stats_global_wiring.py`, `test_global_history_export.py` | projection accuracy | none | **PARTIAL** — V9 duration is zero | S8/S9 |
| P22 | blackboard read/write | `SessionState` + tools | `test_blackboard_conflict.py`, `test_session_db_authority.py` | authority rows, conflict | none | **PARTIAL** — V6/V15/V17 open | S5 |
| P23 | entrypoint auto-run | `fa-entrypoint.sh` | `test_fa_entrypoint.py` (9 tests) | shell exit + env | none | **PARTIAL** — shell C2 only | S4 |
| P24 | direct exec override | `fa-entrypoint.sh` | `test_fa_entrypoint.py` | command passthrough | none | **PARTIAL** — no container evidence | S4 |
| P25 | concurrent EventLog writers | `EventLog` + `SessionDatabase` | **none** | — | — | **UNVERIFIED** — V1 reproduced instead | **S5** |
| P26 | DB failure with mirror | `EventLog.read_all` | probe V3a/V3b (this audit) | fail-closed, no mirror leak | forced-failure probe | **VERIFIED (probe)** | — |
| P27 | legacy JSONL/DB stats | `parse_session_db` | `test_stats.py`, probe V5 | `legacy_unsupported`, no DB created | probe | **VERIFIED (probe)** | — |
| P28 | failed session clone | `fa-entrypoint.sh` | `test_fa_entrypoint.py` | `_fail_to_standby` | none | **PARTIAL** | S4 |
| P29 | clean-worktree invariant | full gate | §7.2 pre/post + negative fixture | mode/status delta | **negative fixture verified** | **VERIFIED (green path), gap on failure path** | S5/S7 |
| P30 | reused DB, different run-id | `SessionDatabase` | probe V7 (this audit) | run-scoped reads | probe | **VERIFIED (probe)** | — |
| P31 | default new session | CLI/entrypoint | `test_session_lifecycle.py:38` | manifest/db/workspace | none | **PARTIAL** (local C2) | S7 |
| P32 | explicit attach | CLI + resolver | `test_session_lifecycle.py:65,82,110,120` | attach + fail-closed | none | **PARTIAL** (local C2) | S7 |
| P33 | multiple runs per session | `_cmd_run` / `_cmd_workflow` | `test_session_lifecycle.py:38` (fresh runs) | run scope isolation | none | **PARTIAL** | S5/S7 |

**Summary:** VERIFIED 5 · PARTIAL 27 · UNVERIFIED 1 · DEFERRED 0 · N/A 0.
No path was marked production-L3 from local evidence.

### 8.2 Flag/failure matrix

| Row | Status | Evidence |
|---|---|---|
| `FA_DEBUG_LLM_BODIES=0/1` | **PARTIAL** — local proof, deployment pending (S3-Q4) | `test_debug_bodies.py`; no raw bodies printed in this audit |
| `detail=debug` w/ env disabled | **PARTIAL** | `test_debug_bodies.py` |
| console / quiet | **PARTIAL** | `test_output.py` consumer-side; producer side per §4.1 |
| compaction off / on | **PARTIAL** | 5 `compaction_end` producer branches, 1 asserted |
| provider success/retry/auth/shape | **PARTIAL** | `test_providers_chain.py`; 4 `api_retry` sites, 1 asserted |
| SessionDatabase failure | **VERIFIED** fail-closed | probe V3b re-raised |
| mirror failure | **VERIFIED** DB-truth preserved | `state.py:192–198`, probe V3a |
| Blackboard failure | **VERIFIED** fail-closed | `blackboard.py:243,286` |
| PTY unavailable | **PARTIAL** | live fallback observed (`runtime/pty_pool.py:520`); policy unstated |
| worktree isolation failure | **MISMATCH** | V18/V19 confirmed; fail-open |
| host env vs `docker compose exec -e` | **DEFERRED** | S4/S7; no container access in this audit |

## 9. Open questions

### Blocking (new, promoted per STOP RULE)

**Q12 — Should `src/fa/inner_loop/loop.py` have a live output channel?**
Three `run_stopped` producers in `loop.py` are durable-only (§4.2), confirmed
behaviourally by kill-check K4 (§5.3): a real `run_session` with an attached bus
emitted **zero** console events while writing a durable `run_stopped` row. The
`state.py:515` `tool_call` producer was cleared on call-graph review. Deciding this requires a product policy choice —
either (a) `run_session` is intentionally console-silent as the deterministic
non-LLM root, and `CONSOLE_MIRROR_KINDS` must record that exemption explicitly,
or (b) `loop.py` gains an `output_bus` and the mirror contract becomes real.
S3 records the evidence and **stops**; per the STOP RULE this is not an audit
decision. Recommended owner: **S6**.

### Non-blocking, resolved as planned

- **S3-Q1 checker replacement** — default upheld: no checker edited in S3.
  Defects S3-F1/F2/F3/F4 are demonstrated with reproducible commands and handed
  to a separate approved checker subplan.
- **S3-Q2 source views** — C0 unavailable, recorded as such (§1.2).
- **S3-Q3 dormant signals** — `cost_alert`, `service_unavailable`, `timeout`
  classified dormant with owner; no producer added to flatter the counts.
- **S3-Q4 deployment claims** — all container/provider rows capped at
  `PARTIAL`/`L2 PENDING`.
- **S3-Q5 line numbers** — all citations anchored to §1.3 content hashes.

## 10. Prioritized gap register and next-slice selection (S3-G6)

| Rank | Gap | Findings | Why now | Owner |
|---:|---|---|---|---|
| 1 | Event-ID allocation is not atomic | V1, P25 | Duplicate correlation IDs corrupt replay exactly when workflow/parallel paths share a run. Reproduced, unchanged by S2. Cheapest correct fix (DB-side allocation + `UNIQUE(event_id)`) is contained. | **S5** |
| 2 | Mutation-path conflict asymmetry | V15, V17 | `edit_file` has no conflict check at all; the formal substrate's core guarantee is bypassable through the most-used edit tool. | **S5** |
| 3 | Worktree/subagent fail-open cluster | V18, V19, V21, V22, V24, V25 | Six findings, one root: failures degrade the permission boundary instead of denying. CT10 mismatches. | **S5** |
| 4 | Contract-checker defects | S3-F1..F4 | The gates that are supposed to prevent regressions are provably blind to producer deletion. Until fixed, checker green must not be cited as evidence anywhere. | separate checker subplan |
| 5 | Durable-only mirror kinds | S3-F3, Q12, K4 | Operator sees **no console signal at all** when `run_session` stops on a hook denial — proven at runtime, not inferred. | S6 (after Q12) |
| 6 | Path-incomplete C1 coverage | §4.1 | 16 producer sites across 8 types have no named assertion. | S6 |
| 7 | Hygiene restore without `try/finally` | V12 | Failing suites poison the working tree and mask real diffs. | S5/S7 |
| 8 | `kind_counts` pre-write increment | V2 residual | In-memory metrics can count uncommitted events — **and `coder_loop.py:574` persists them into `session_db` meta**, so the drift becomes durable. | S5 |
| 1= | **Commit invalidates conflict detection** | S3-F10 | A single commit makes every pre-commit Blackboard entry unenforceable. Ranks alongside V15/V17: same guarantee, wider blast radius, and cheaper to fix (`_should_check_conflict` policy). | **S5** |
| 2= | **Agent tool reads unauthoritative mirror** | S3-F13 | `observability.py:42` ships in the baseline registry and can report events absent from the authority. Completes the V3 closure that S2 started. | **S5** |
| 4= | **CHECK 3 accepts assertion-free C1 tests** | S3-F14 | The gate that is supposed to prove liveness stays green when the oracles are deleted. | checker subplan |
| 6= | Silent renderer dispatch | S3-F12 | Unknown/removed EventType handlers fail invisibly; violates failure-observable. | S6 |
| 7= | stdout pollution in library code | S3-F11 | Bare `print()` corrupts `fa run > result.txt`. One-line fix, pairs with V19. | S5/S6 |

### Selected first implementation slice

**S5 — Close remaining authority correctness**, scoped to ranks 1–3.

Explicit non-goals for that slice: no checker edits (rank 4 is a separate
subplan), no `loop.py` output channel until Q12 is answered, no V23 re-opening,
no CLI extraction, no deployment work.

## 11. Reproduction commands

```bash
# provenance
git rev-parse HEAD origin/main && git status --short

# shipped checkers (unmodified)
python scripts/check_producer_consumer_contract.py
python scripts/check_log_kind_contract.py

# audit instruments (disposable, /tmp only)
python3 /tmp/fa-s3/inventory.py src/fa .   > /tmp/fa-s3/inventory-S2.json
python3 /tmp/fa-s3/dualwrite.py /tmp/fa-s3/inventory-S2.json
python3 /tmp/fa-s3/c1_audit.py
python3 /tmp/fa-s3/probe_v.py

# kill-checks (disposable copies under /tmp/fa-s3/kc/)
#  K1: remove coder_loop.py tool_call emit  -> checker FAIL + C1 test fails
#  K2: remove spawn_subagent.py:72 append   -> checker IDENTICAL + C1 test fails
python3 /tmp/fa-s3/k4_probe.py     # K4: run_stopped console gap, behavioural

# full gate + hygiene snapshot
python -m pytest tests/ -q -p no:cacheprovider
git status --short && git diff --summary
```

Artifacts retained: `/tmp/fa-s3/pre-audit-snapshot.txt`,
`/tmp/fa-s3/inventory-S2.json`, `/tmp/fa-s3/inventory-K1.json`,
`/tmp/fa-s3/inventory-K2.json`, `/tmp/fa-s3/dualwrite.json`,
`/tmp/fa-s3/c1-audit.txt`, `/tmp/fa-s3/probe-v-output.txt`,
`/tmp/fa-s3/checker-pc.txt`, `/tmp/fa-s3/checker-lk.txt`,
`/tmp/fa-s3/gate-pre.txt`, `/tmp/fa-s3/gate-post.txt`,
`/tmp/fa-s3/logkind-table.md`, `/tmp/fa-s3/k4_probe.py`.

No raw `llm_bodies.jsonl` content was read, printed, or stored at any point.

## 12. Definition of Done — self-check

| Exit criterion | Status | Where |
|---|:---:|---|
| Source views provenance-labelled; C0 handled explicitly | ✅ | §1.1, §1.2 |
| Every EventType has definition/producer/consumer rows | ✅ | §4.1 |
| Every LogKind (33/33) + mirror kind (15/15) has producer/consumer or dormant status | ✅ | §4.2 |
| Dynamic producer sites named | ✅ | §3.3 |
| Checker limitations and mismatches recorded | ✅ | §4.3 |
| Two-sided table complete; consumer-only/producer-only explicit | ✅ | §4.1, §4.2 |
| Dual-write status is branch-specific, not file-level | ✅ | §4.2 |
| Each claimed L3 row has a named producer kill-check | ✅ | §4.1, §5 (K1, K2, K4) |
| P1–P33 each has status + evidence reference | ✅ | §8 |
| No row marked production L3 from local-only evidence | ✅ | §8 (all capped PARTIAL) |
| Every V1–V26 has one current disposition | ✅ | §6 |
| CT10 boundary table complete | ✅ | §7.1 |
| Verification gate side effects classified + negative fixture | ✅ | §7.2 |
| Prioritized gap register with owner slice | ✅ | §10 |
| First implementation slice selected from evidence | ✅ | §10 |
| No runtime/test file changed; no commit/push/deploy | ✅ | §1.4 |
| No raw body output; no secrets in artifacts | ✅ | §11 |

### Negative proof

The audit would be invalid if removing a representative producer left the
inventory unchanged. It does not: K1 changed the `tool_call` row and K2 changed
the `subagent_spawn_done` row (§5). Conversely, the shipped LogKind checker *is*
invariant under K2 — which is reported as a finding against the checker, not
laundered into a pass for the audit.

## 12b. Adversarial re-verification pass (2026-07-27, second session)

Every §0 finding was re-attacked against current source, with the explicit goal
of falsifying my own claims. Three claims changed, four new findings emerged,
and one probe was found to be self-invalidating.

### Corrections to previously reported findings

| ID | Original claim | Re-verified result | Why it changed |
|---|---|---|---|
| **S3-F2** | "`C1 tested: 20` is arithmetically impossible" — implied a functional defect | **DOWNGRADED to cosmetic**, and **replaced** by a stronger real defect | CHECK 3 iterates `event_types` and tests `et in c1_tested`, so the 5 stray strings (`plan`, `note`, …) never affect pass/fail. The printed count is wrong; the gate logic is not. The *real* weakness is below (S3-F14). |
| **S3-F6 / V1** | "Duplicate event IDs reproduce unchanged" — framed as a live P0 | **CONFIRMED but LATENT, not live** | Single-instance/8-thread test: 8/8 unique — the `_lock` works. Duplicates need **two `EventLog` instances where one holds a stale `_next_id`**. `cli.py:1742` constructs `workflow_log` *after* the stage loop finishes, so today's workflow path is safe **by ordering accident**. Severity stands (no `UNIQUE(event_id)`; DB accepted 3 duplicate pairs from 6 writes), but it is a latent trap, not an active corruption. |
| **S3-F8 / V12** | "Failure-only leak inside the checkout under test" | **WORSE than reported** | The test resolves `Path(install_mod.__file__)` — the **pip-installed editable package**, not the tree under test. My re-run from a disposable copy chmod'd `/home/user/repo/src/fa/hygiene/hooks/pre-commit`. The leak **escapes the checkout entirely** and dirties whatever repo is installed. This also explains the four dirty hook modes in §1.4 that I had attributed to a checkout/umask artifact — that attribution was wrong. |

### Probe defect found and fixed

My first V15 behavioural probe reported `NOT-AS-CLAIMED (wf_blocked=False)` —
appearing to falsify S3-F7. Root cause was **my probe**, not the code: I seeded
the prior Blackboard entry with `base_commit="deadbeef"` while the tool computes
a real `git rev-parse HEAD`. `_should_check_conflict` (`blackboard.py:94`)
returns `False` when bases differ, so detection was correctly skipped. With a
matching base:

```text
write_file -> ok=False code=conflict_detected   file unchanged
edit_file  -> ok=True  code=None                file MUTATED
VERDICT: ASYMMETRY-CONFIRMED
```

S3-F7/V15 stands, now on behavioural rather than string-heuristic evidence.

### New findings

| ID | Finding | Severity | Evidence |
|---|---|---|---|
| **S3-F10** | **A single commit disables Blackboard conflict detection against all pre-commit entries.** `_should_check_conflict` returns `new_base == old_base`; differing bases are treated as "serialized" and skipped. Probe: agent B blocked (`conflict_detected`) at HEAD₁; one unrelated commit lands; agent C writes the **same file** and is **ALLOWED**. Coding agents commit routinely, so the formal conflict guarantee silently expires mid-session. Non-git workspaces fail *closed* (`unknown == unknown`), so this only bites real repos. | **P0** | `/tmp/fa-s3/probe_base_commit_bypass.py` |
| **S3-F11** | **`worktree_manager.py:235` writes its isolated-downgrade warning to stdout via bare `print()`.** It is the only bare `print()` in `inner_loop/`, `workspace/`, or `blackboard/`. `output.py:1-6` reserves stdout for the final answer so `fa run --task "…" > result.txt` works. Probe captured 211 bytes of warning text on stdout — it would corrupt redirected output. Compounds V19: the config-truth gap is *also* an output-contract violation. | **P1** | `/tmp/fa-s3/probe_stdout_pollution.py` |
| **S3-F12** | **`ConsoleRenderer.on_event` silently drops unknown event types.** `getattr(self, f"_handle_{event.type}", None)` → no handler means no output, no warning, no raise. A deleted handler or a typo'd type string is invisible at runtime. Verified: `type="totally_bogus_type"` produced zero bytes. Violates §1.2.5 failure-observable. (`EventBus.emit` is better — it logs a traceback.) | **P1** | `/tmp/fa-s3/probe_silent_dispatch.py` |
| **S3-F13** | **V3 is NOT fully closed: an agent-facing tool still reads the unauthoritative mirror.** `tools/observability.py:42` builds `EventLog(path, run_id=run_id)` with **no `session_db`**, so `_injected_session_db` is False and the legacy JSONL fallback is live. These tools ship in the baseline registry (`include_observability=True`). Probe: authoritative DB `event_count()==0`, forged `events.jsonl` row → the agent tool reported a `fs_run_bash` event that never happened. My §6 verdict "closed for production path" was **too narrow** — it held only for `EventLog.read_all` under `drive_session`. | **P0** | `/tmp/fa-s3/probe_obs_mirror.py` |
| **S3-F14** | **CHECK 3 validates string presence, not test strength.** Replacing all 11 `assert ` statements in `test_event_type_c1_producers.py` with `_ = ` left the checker at `C1 tested: 20 types` / `✅ All non-dormant EventTypes with producers have C1 tests`, and pytest reported `6 passed`. Nothing in the gate detects a C1 test whose oracles were removed — precisely the AI-authored-test weakening the tests-writing skill warns about. This replaces S3-F2 as the substantive CHECK 3 defect. | **P0** | `/tmp/fa-s3/k5` |

### Root cause of S3-F4, now pinned exactly

The `subagent_spawn_done` false negative is **caused by the type annotation**.
The checker's dynamic-assignment branch (`check_log_kind_contract.py:90`) uses
`kind\s*=\s*"([a-z_0-9]+)"`. The production line is:

```python
kind: LogKind = "subagent_spawn_done" if envelope.exit_code == 0 else "subagent_spawn_fail"
```

`: LogKind` sits between `kind` and `=`, so the regex cannot match. Verified:
the identical line without the annotation matches fine. Writing the
type-annotated code that mypy and the `LogKind` contract encourage is what
blinds the checker — an actively perverse incentive.

### Latent hazard (not an active defect)

`check_log_kind_contract.py:84` accepts **any** `.append(` within 4 lines above a
`kind="…"` literal — including `list.append()`. A repo scan found **0** current
sites where a non-log `.append()` would validate a foreign `kind=` literal, so
this is latent. It is why `providers/base.py:130,140`
(`ProviderTransientError(kind="timeout"/"service_unavailable")`) are correctly
excluded today — by line spacing, not by design. Recorded so a future refactor
that moves those lines closer together does not silently create phantom
producers.

### Claims re-confirmed unchanged

`V1` mechanics (DDL has no `UNIQUE` on `event_id`; duplicates persist),
`V2` residual (drift confirmed **and** consumed — `coder_loop.py:574` writes the
drifted `kind_counts` into `session_db` meta, which my report understated),
`V6` (3 × `INSERT OR REPLACE`), `V18` (fail-open to main workspace, probed),
`V19`, `V20` (cleanup failure swallowed, probed), `V21`/`V22` (non-atomic
check-then-act, probed), `V9`, `V10`, `V11`, `S3-F1`/K2 (checker output
byte-identical after producer deletion — re-reproduced), `S3-F5`
(`cost_alert` genuinely dormant, zero source references outside `output.py`),
and all inventory counts (16/33/15/50).

`service_unavailable` and `timeout` dormancy re-checked against a plausible
false positive: both appear as `kind=` in `providers/base.py`, but on
`ProviderTransientError`, a different namespace from `LogKind`. Dormancy stands.

### Gate-coverage observation

Only 3 of 9 `scripts/check_*.py` run under `just check`
(`check_producer_consumer_contract`, `check_dependency_contract`,
`check_no_mocked_dataclasses`). `check_log_kind_contract.py` is **not** in
`justfile` — it is gated indirectly via `tests/test_check_log_kind_contract.py`.
On the K2 killed tree those 4 checker tests **passed**, as did
`test_s4_log_kind.py` (7 passed). The only things that caught the deleted
producer were 2 C1 wiring tests:
`test_subagent_termination_wiring.py::test_subagent_spawn_and_cleanup_via_drive_session`
and `test_slice5_6_7_wiring.py::test_pr6_wiring_subagent_role_env_and_events`.

**Consolidated conclusion: the C1 wiring tests are the only load-bearing gate
for signal liveness. Every checker layer above them is decorative for at least
one real deletion.** This strengthens rank 4 of the §10 register and argues for
sequencing the checker subplan before S5.

## 13. Handoff

S3 is complete. Runtime implementation remains forbidden until an S5 subplan is
authored and review-gated. Before S5 execution:

1. Answer **Q12** (loop.py live channel) — required before any S6 mirror work.
2. Correct plan §1.1 provenance text: S2 is commit `811502e` on
   `formal-substrate++`, not an uncommitted tree at `origin/main`.
3. Do not cite `check_log_kind_contract.py` PASS as evidence in any slice until
   S3-F1 is closed; it is provably blind to producer deletion.
