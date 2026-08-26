> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN: S8 — workflow as a separate controller surface

Plan-ID: `PLAN-cli-trace-S8-workflow-controller-surface`
Status: **COMPLETE (2026-07-30)** — all 8 steps executed; gate green
(2252 passed, mypy 314 files clean, pylint 10.00/10, authoring-check 0,
mutation 7/7 + 49/49). Execution record in §11.
Previously: **READY** — all blocking questions resolved by the operator
(2026-07-30). **Q32** resolved: option (a) scoped to `quiet`. **Q34** resolved:
workflow is a SECOND deployment gate. Non-blocking **Q33**/**Q35** carry
recorded defaults.
Depth: **P2** — cross-module (CLI controller + artifacts + projection), changes
an operator-visible output contract, and touches a signal consumed by S9.
Revision: **v3** · Changed-since-last (**review pass, 2026-07-30**):
**(A)** **S8.3 redesigned** — v2's mechanism was *impossible*
(`_print_terminal_summary` is called from **inside** each mode, 7 sites, before
`_cmd_workflow` regains control) **and**, once corrected, would have been
*ceremony* (a "consumer" feeding only a printed string). Replaced with the
**real** consumer, discovered by the review: the `global_history` export
already needs terminal truth and currently fabricates it.
**(B)** **Production defect found and now owned by S8.7** — for the same run,
`flow_state.json` says `FAILED` while `global_history` says
`workflow_complete`. Measured, three-artifact disagreement.
**(C)** S8.6 gains the failure-path aggregate-row assertion.
**(D)** Q35 upgraded from "record the default" to a real fork (Q35a/Q35b),
because the review showed the exit code is *load-bearing* for the projection.
**(E)** `duration_ms > 0` flakiness risk assessed and closed.
· *v2 changes retained:* **(1)** re-audited the v1 "already
covered" claim and found it too aggressive — added **G5/CT6/S8.6** for terminal
`FAILED` states (7 producer call sites, 0 tests); **(2)** Q32 resolved →
`quiet`-scoped stdout contract, S8.4 mechanism revised and made strictly
smaller; **(3)** Q34 resolved (second gate); **(4)** Q35 raised (exit code on
BLOCKED verdict); **(5)** 3 file:line anchors corrected.
Upstream context: parent
[`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md)
§Step S8 (line 1753); predecessor
[`PLAN-cli-trace-S7-direct-run-vertical-slice.md`](./PLAN-cli-trace-S7-direct-run-vertical-slice.md)
(COMPLETE); container evidence
[`PLAN-cli-trace-S7-container-verification.md`](./PLAN-cli-trace-S7-container-verification.md)
§3; folded-in finding **I-38 / Q31** per operator instruction 2026-07-30.

> **Tests-writing authority.** Every test named in this plan MUST be written
> under [`knowledge/skills/tests-writing/SKILL.md`](../../knowledge/skills/tests-writing/SKILL.md)
> — class declared (C0/C0p/C1/C2/C3), ranked oracle, producer kill-check,
> honest types, existence pre-check, no `TEST-EDITS` weakening. This is a DoD
> item (§9), not a suggestion.

---

## Preflight log (§2 — mandatory, run 2026-07-30, not assumed)

**Roots checked**

| Root | File:line | Note |
|---|---|---|
| `fa workflow` argparse root | `cli.py:509–591` | 3 modes, `--max-repairs`, `--max-replans`, per-role `--task-*` |
| `_cmd_workflow` | `cli.py:1641` | controller entry; validates roles/mode/run-id, resolves lifecycle |
| `_run_linear` | `cli.py:1528` | fail-fast, no loop |
| `_run_repair` | `cli.py:1561` | bounded `coder→eval` |
| `_run_adaptive` | `cli.py:1388` | normalizes `coder→eval` / `planner→coder→eval` |
| `_run_stage` | `cli.py:~1195` | builds the stage `Namespace`, calls `_cmd_run` |
| workflow aggregate export | `cli.py:1760–1807` | single `global_history` row after all stages |
| artifacts module | `inner_loop/workflow_artifacts.py` | `FlowState`, `EvalReport`, `StepResult`, parse/load/write |

**Greps run → findings**

| Pattern | Finding |
|---|---|
| `_WORKFLOW_MODES` | `cli.py:1090` = `("linear","repair","adaptive")` — 3 modes, all reachable |
| `FlowStatus` / `_FLOW_STATUSES` | `workflow_artifacts.py:50`, `:71` — 11 states, dual declaration (Literal + frozenset) |
| `_ROUTE_DECISIONS` | `:69` = `complete`, `return_to_coder`, `return_to_planner`, `blocked` |
| `_EVAL_VERDICTS` | `:68` = `PASS`, `REPAIR_REQUIRED`, `REPLAN_REQUIRED`, `BLOCKED` |
| `load_flow_state\|load_eval_report` in `src/` | **ZERO production consumers** outside the defining module. 30 references, all in `tests/`. |
| `pr_draft` in `src/` | `cli.py:1969` (`PrDraftStore`), `intent_guard.py:87` — narrative only; **no controller reads it**. Already correct. |
| `output_mode` in `_run_stage` | `cli.py:1204` — **hardcoded `"console"`**; `fa workflow` has **no** `--output-mode` flag |
| `duration_ms` in workflow export | `cli.py:1802` — **hardcoded `0`** with comment "not tracked at workflow level yet" |
| `route` in `global_history.py` | **no such column** — schema `:91–111` has 19 columns, none is route/verdict |

**Gold patterns mirrored**

- `tests/test_cli_ergonomics.py:249` — `test_workflow_session_manager_uses_one_invocation_run_context`,
  labelled *"C2 producer proof"*; the canonical workflow C2 shape (real
  `_cmd_workflow`, `_ScriptedTransport`, assert on DB rows not prose).
- `tests/test_cli_ergonomics.py:338–571` — repair/adaptive loop tests; oracle is
  `transport.planner_calls/coder_calls/eval_calls` **plus** `load_flow_state`.
- `tests/test_s7_correlation.py` — S7's DB-join oracle style.
- `tests/test_global_history_export.py:387` — `..._via_drive_session`, the
  existing composition-root export proof.
- Fixtures to reuse, **do not re-invent**: `_workflow_args` (`:220`),
  `_repair_env`, `_RoleAwareTransport`, `_ScriptedTransport`, `_TEST_SECRETS`,
  `_FAKE_MODELS_YAML`.

**Conflicts / invariants found**

- Parent §Do-not (binding): no persisted resume semantics without a
  state-by-state transition contract; **no generic transition engine**; **no
  inspect/status CLI surface in this slice**. S8.3 is written to respect this —
  it adds a *consumer*, not a state machine.
- `QuietRenderer` docstring (`output.py:449`) states a contract the CLI
  violates — **I-38**. Folded in here per operator instruction.
- BACKLOG **I-36/I-37/I-39** are explicitly **deferred past the workplan** by
  operator decision — out of scope, must not be opportunistically fixed.
- S9 depends on S8 and consumes machine-parseable CLI output → I-38 must land
  here, before S9.

**As-is liveness (§4 scale)**

| Signal | Liveness | Evidence |
|---|---|---|
| `linear` / `repair` / `adaptive` mode dispatch | **L3** | 12 tests at `test_cli_ergonomics.py:279–577`, budget + route negatives present |
| `FlowState` written as controller truth | **L3** | `_write_terminal_state`; asserted by 8 tests |
| `EvalReport` verdict/route parsing | **L3** | 11 tests in `test_workflow_artifacts.py`, incl. fail-closed + contradictory-route |
| `pr_draft.md` excluded from controller truth | **L3** | zero controller reads (grep-verified) |
| **`FlowState`/`EvalReport` read back by a real consumer** | **L1** | import-reachable only; **0 production callers** |
| **workflow aggregate `global_history` row** | **L2** | producer at `cli.py:1794` runs, but **no test asserts it** |
| **workflow `duration_ms`** | **L0** | hardcoded `0` |
| **workflow stdout contract** | **L0 (violating)** | measured **102 bytes** on a 3-stage run |
| **terminal `FAILED` state (stage fail-fast + BLOCKED verdict)** | **L2** | `_write_stage_failure_state` has **7 call sites**; `status="FAILED"` written at 2 sites; **asserted by 0 tests** |

### Review-pass findings (v3, 2026-07-30) — read before executing

Four defects in **v2 itself**, each found by probing rather than re-reading.

**RV1 — S8.3's mechanism was impossible.** v2 said: call
`_read_back_terminal_state` in `_cmd_workflow` after mode dispatch, and have
`_print_terminal_summary` use it. But `_print_terminal_summary` is called from
**inside** the mode functions — 7 call sites (`cli.py:1415`, `:1429`, `:1473`,
`:1519`, `:1557`, `:1632`) — every one of which runs *before* `_cmd_workflow`
regains control at `:1758`. The summary is already printed by the time the
proposed consumer would run. **An executor following v2 would have hit this in
the first 10 minutes and improvised.**

**RV2 — worse, the corrected version would have been ceremony.** Suppose RV1 is
fixed by moving the read earlier. What would the consumer *do*? Feed a string
into a stderr line. Delete `flow_state.json` and the only casualty is printed
prose. That satisfies the letter of "artifacts are read back by their real
consumer" while missing its point. Per the plan-authoring central law — *a DoD
that would still pass with the feature deleted is decoration* — v2's S8.3 was a
**test-shaped consumer**, not a production one.

**RV3 — the real consumer already exists, and it is broken.** The
`global_history` aggregate export needs terminal truth *and fabricates it*:

```python
stop_reason = "workflow_complete" if result_code == 0 else "workflow_failed"  # cli.py:1782
```

It derives a semantic outcome from an **int**, while the authoritative terminal
outcome is `FlowState.status`, sitting on disk unread. That is the missing
read-back — not an invented one.

**RV4 — PRODUCTION DEFECT (not a plan defect). Three artifacts disagree about
one run.** Probed with a scripted `BLOCKED` eval verdict:

```text
eval_report.json : verdict='BLOCKED' route='blocked'
flow_state.json  : status='FAILED'
global_history   : stop_reason='workflow_complete'  exit_code=0
process exit     : 0
```

`_run_linear` returns `0` whenever the pipeline *ran to completion*
(`cli.py:1558`), regardless of verdict; `_run_repair`/`_run_adaptive` do the
same (`:1638`). So a rejected run is recorded in the cross-run projection as a
**completed** one. **S9 builds its dashboards on this table.** Every "success
rate" it computes would count BLOCKED runs as successes.

This is exactly what G1 was reaching for and did not name. **S8.7 now owns it.**

**RV5 — a bonus assertion v2 missed.** The aggregate export sits after the
single terminal `return` (`cli.py:1809`) and is therefore reached on the
**failure** path too. Probed: a stage failing with HTTP 500 still writes
`{'exit_code': 2, 'stop_reason': 'workflow_failed', 'duration_ms': 0}`. Good
news — but untested, so S8.6 now asserts it.

**RV6 — `duration_ms > 0` flakiness, assessed and closed.** The assertion could
in principle flake if a workflow completed in under 1 ms (`int()` truncation).
Measured: a 3-stage scripted run takes **~132 ms**. Three real `_cmd_run`
invocations with SQLite writes cannot complete in <1 ms. **Risk accepted, no
mitigation needed** — recorded so a future reader does not "fix" it into
`>= 0`, which would be the S7.C3 tautology all over again.

---

**Measured, not assumed** — two probes run this session against real
`_cmd_workflow` with `_ScriptedTransport`:

```text
# stdout pollution (I-38 in workflow)
exit: 0
STDOUT bytes: 102
STDOUT repr : 'OK: stopped_by_llm (turns=1)\ndone\n' × 3
STDERR bytes: 1337

# aggregate global_history row
{'run_id': 'wf-gh', 'role': 'planner→coder→eval', 'turns': 3,
 'duration_ms': 0, 'stop_reason': 'workflow_complete', 'exit_code': 0}
```

**The audit shrank the slice — but v1 shrank it too far.** Parent Do #1–#3 are
genuinely already L3, and re-testing them would add a second oracle for one
behaviour (the S6 matrix-E tautology). **Five** gaps are real: **G1** (artifact
read-back), **G2** (aggregate projection), **G3** (duration), **G4** (stdout),
**G5** (terminal `FAILED` state).

> **v2 correction — an audit finding reversed by re-auditing.** v1 of this plan
> dismissed parent Do #4 wholesale as "already L3". That was wrong. Do #4 names
> *"terminal states"*, and the terminal **failure** state is not covered at all:
>
> - `_write_stage_failure_state` (`cli.py:1242`) has **7 call sites** across all
>   three modes; **zero** tests reach any of them.
> - `status="FAILED"` is written by production at 2 sites; the string `"FAILED"`
>   is asserted **0 times** in the whole workflow test suite.
> - `BLOCKED` verdict → `FAILED` status (`cli.py:1081`) is tested only at the
>   **parser** level (`test_workflow_artifacts.py:200`, a C0 unit on
>   `parse_eval_report`) and never end-to-end. This is precisely the
>   *C0-consumer-only false-confidence trap* named in tests-writing skill §10:
>   a C0 test on the mapping proves the dict literal, not that the controller
>   ever applies it.
>
> Verified by probe, not by reading — a transport returning a persistent HTTP
> 500 (what `UrllibTransport` produces on upstream failure, `transport.py:117`):
>
> ```text
> exit: 2 | flow_state exists: True
>   status='FAILED' active_role='planner'
>   blocked_reason="stage 'planner' exited 2"
>   stderr: fa workflow: stage 'planner' exited 2 — pipeline stopped (fail-fast).
> ```
>
> The behaviour is **correct**; it is simply unverified. The five happy-path
> budget/route tests v1 cited (`:360`, `:380`, `:414`, `:523`, `:572`) all
> assert `code == 0` or a *pre-dispatch* validation `code == 2` — none drives a
> stage to a non-zero exit. **Lesson recorded: "already covered" must be
> verified per-branch, not per-feature.** A mode being L3 on its happy path
> says nothing about its failure path.

**Unresolved → promoted:** **Q32** (blocking, gates S8.3).

---

## 0. Executive intent (§3)

**IDEA.** Prove `fa workflow` is a *controller surface* distinct from
`fa run`: its truth lives in machine artifacts that something actually reads,
its projection into `global_history` is accurate, and its output stream is
parseable. Close the one operator-visible contract violation S7 found (I-38)
at the surface where it compounds.

**PROJECT MEANING.** In `src/fa/cli.py` the workflow controller is the only
component that runs `_cmd_run` N times over one session. That makes it the
place where per-run assumptions break: stdout is written N times, the
`global_history` row is an *aggregate* rather than a run, and artifacts are the
only cross-stage memory. S8 is where those three seams get proven.

**GOALS**

- **G1** — `FlowState` / `EvalReport` are read back by a **real production
  consumer**, not only by tests. (Parent exit criterion: *"artifacts are read
  back by their real consumer"*.)
- **G2** — the workflow aggregate `global_history` row is verified for
  accuracy: `role`, `turns`, `exit_code`, `stop_reason` from a real trace.
- **G3** — workflow `duration_ms` is real, not `0`.
- **G4** — `fa workflow` honours an explicit stdout contract; **I-38 / Q31**
  resolved for both `fa run` and `fa workflow`.
- **G6** — the three durable artifacts of one workflow run (`eval_report.json`,
  `flow_state.json`, `global_history.runs`) **agree**. Today they do not: a
  BLOCKED run is recorded in the cross-run projection as `workflow_complete`
  (RV4). *(New in v3 — a production defect, not a coverage gap.)*
- **G5** — the terminal **failure** states are verified: a stage exiting
  non-zero writes `FAILED` and stops fail-fast, and a `BLOCKED` eval verdict
  reaches `FAILED` through the controller (not just through the parser).
  (Parent Do #4 *"terminal states"*.)

**NON-GOALS.** See §1.

**INTENT.** Code should ensure that *controller truth is round-trippable and
machine-consumable* whenever a workflow completes — so a caller (and S9) can
read the outcome without parsing prose.

**MECHANISM SKETCH.** `_cmd_workflow` → mode dispatch → per-stage `_cmd_run`
→ `FlowState`/`EvalReport` written → **NEW: terminal summary re-reads the
persisted artifact** (G1) → aggregate export with **real elapsed ms** (G3) →
stdout carries only payload (G4), status to stderr.

**PROOF SKETCH.** Root `_cmd_workflow` observes `load_flow_state(...)` return
value + `global_history` row fields + captured stdout bytes; kill-checks remove
the re-read call, the duration computation, and the stream redirect.

**SIZE.** M.

---

## 1. Non-goals & minimal-mechanism check (§5)

**NON-GOALS** (scope firewall — parent §Do-not is binding):

1. No persisted **resume** semantics. G1 adds a read-back *within one
   invocation*; it does not restore a run from disk.
2. **No generic transition engine.** The consumer added in S8.3 is a single
   function that loads and validates; it does not become a state machine.
3. No `inspect` / `status` CLI surface.
4. No new `FlowStatus` values, no new route decisions.
5. No `route`/`verdict` column added to `global_history` — that is an S9
   schema question, deliberately deferred (see **Q33**, non-blocking).
6. **I-36, I-37, I-39 are NOT touched** — operator deferred them past the
   workplan.
7. No changes to `_run_repair` / `_run_adaptive` loop logic (already L3).

**Minimal-mechanism check (required at P2):**

- *G1*: could a smaller change satisfy it? A test-only read-back was
  considered and **rejected** — it would leave the production consumer absent,
  which is exactly the L1 condition the parent's exit criterion targets. The
  chosen mechanism is the smallest real consumer: the terminal summary already
  runs at the end of every mode, so it re-reads instead of using its in-memory
  copy. Zero new call sites.
- *G3*: reuse the existing `time.monotonic()` pattern from `_cmd_run`
  (`cli.py:2142`, `:2182`) rather than introducing a timing abstraction.
- *G4*: adding `--output-mode` to the workflow parser mirrors the existing
  `run` parser (`cli.py:490`) — no new concept.

---

## 2. Current state → Target state (§4)

**AS-IS** (verified, file:line)

| Dimension | Finding |
|---|---|
| Entry points | `_cmd_workflow` `cli.py:1641`; 3 modes `cli.py:1090` |
| Existing types | `FlowState`, `EvalReport`, `StepResult`, `EvalFinding` — `workflow_artifacts.py:126–290` |
| Producers | `write_flow_state` `:530`, `write_eval_report` `:522`, aggregate export `cli.py:1794` |
| Consumers | `load_flow_state` `:534`, `load_eval_report` `:526` — **ZERO production callers** |
| State stores | `~/.fa/session-log/<run_id>/{flow_state,eval_report}.json`; `session.db`; `global_history.db` |
| Flags/defaults | `--mode linear`, `--max-repairs`, `--max-replans`; **no `--output-mode`** |
| Tests today | 46 pass across the 3 workflow files; modes/budgets/routes L3; **no** aggregate-row, duration, or stdout test |
| Liveness | see preflight table |

**TO-BE** (machine-checkable)

- `_read_back_terminal_state(...)` **NEW** in `cli.py` — loads the just-written
  `flow_state.json`, validates identity (`run_id` match), returns `FlowState`.
- `_cmd_workflow` computes `_wf_start_mono = time.monotonic()` and passes real
  `duration_ms` to `export_session_to_global_history` (replaces literal `0`).
- `fa workflow --output-mode {console,quiet}` **NEW**, default `console`;
  forwarded into `_run_stage`'s `stage_kwargs` (replaces hardcoded `"console"`).
- **I-38 resolution (Q31 option a):** `_cmd_run`'s status line
  (`cli.py:2212`) moves to **stderr**; `final_text` (`:2214`) stays on stdout.
  Under `--output-mode quiet`, stdout is byte-identical to `final_text`.
- Target liveness: G1 L1→**L3**, G2 L2→**L3**, G3 L0→**L3**, G4 L0→**L3**.

**STATE transitions**

- `STATE: flow_state.json` — AS-IS: write-only artifact → TO-BE: written **and
  read back by production** before the terminal summary is printed.
- `STATE: global_history.runs.duration_ms` for workflow rows — AS-IS: always
  `0` → TO-BE: real elapsed ms `> 0`.
- `STATE: stdout of fa run / fa workflow` — AS-IS: status+payload → TO-BE:
  payload only; status on stderr.

---

## 3. Contracts (§6)

### CT1 — `_read_back_terminal_state` (function contract, §6.1) — NEW

- **PRE:** `flow_state.json` has just been written by `_write_terminal_state`.
- **POST:** returns a `FlowState` whose `run_id == ctx.run_id`.
- **IN:** `ctx: _WorkflowContext`. **OUT:** `FlowState | None`.
- **ERRORS:** on missing/corrupt/identity-mismatch → returns `None` and logs a
  warning; **never raises** (a projection read must not fail a completed run).
- **PURE?** no — filesystem read. **SIDE EFFECTS:** none beyond logging.

### CT2 — workflow artifact read-back (signal contract, §6.2) — TWO-SIDED

- **PRODUCER:** `_write_terminal_state` / `_write_stage_failure_state`
  (`cli.py`, existing) → `flow_state.json`.
- **CONSUMER:** `_read_back_terminal_state` (**TO ADD**), called from
  `_cmd_workflow` before the aggregate export; its `FlowState.status` is used
  in the terminal summary line.
- **DUAL-WRITE:** N/A — single channel (FS artifact). `session.db` is a
  separate, already-verified channel.
- **KILL-CHECK (PRIMARY, producer):** remove the `write_flow_state(...)` call
  → `test_s8_aggregate_stop_reason_comes_from_flow_state` fails (no artifact to
  load, so the read falls back to the integer rule).
- **KILL-CHECK (consumer):** remove the `_read_back_terminal_state(...)` call
  → the same test fails on the asserted return/summary value.
- **SHIP RULE:** producer proof before "shipped".

### CT3 — workflow aggregate projection (data contract, §6.3)

- Schema: `global_history.runs` (`global_history.py:91–111`), 19 columns,
  **additive-free** — S8 adds no column.
- For a workflow run: `role == "→".join(roles)`, `stop_reason ==
  "workflow_complete"|"workflow_failed"`, `turns` from telemetry (not
  `outcome.turns`, which is deliberately `0` — `cli.py:1783`), `duration_ms > 0`
  **(changed)**.
- **KILL-CHECK:** remove `export_session_to_global_history(...)` at
  `cli.py:1794` → `test_s8_workflow_aggregate_row_is_accurate` fails.

### CT4 — CLI stdout contract (signal contract, §6.2) — TWO-SIDED

- **PRODUCER:** `_cmd_run` `cli.py:2212` (status) and `:2214` (`final_text`).
- **CONSUMER:** any caller redirecting stdout; canonically
  `fa run --task ... > result.txt`, and S9's projections.
- **Contract (revised by Q32 — mode-scoped, not unconditional):**
  under `--output-mode quiet`, `stdout == outcome.final_text` byte-for-byte and
  the status line goes to stderr; under default `console`, stdout is
  **unchanged** (status + payload). In **both** modes the durable side effects
  — session.db rows, `flow_state.json`, `eval_report.json`, `global_history`
  row — are identical. `quiet` is a console-verbosity control, never a
  processing control.
- **KILL-CHECK:** revert the status line to `print(...)` on stdout →
  `test_s8_quiet_stdout_is_payload_only` fails.
- **Documentation coupling:** `QuietRenderer` docstring (`output.py:449`)
  becomes **true**; it is currently false. Docstring must be updated in the
  same commit as the behaviour (see S8.4 Do-not).

### CT6 — terminal failure state (signal contract, §6.2) — TWO-SIDED

- **PRODUCER:** `_write_stage_failure_state` (`cli.py:1242`, 7 call sites) and
  `_write_terminal_state`'s `_EVAL_VERDICT_TO_TERMINAL_STATUS["BLOCKED"] ->
  "FAILED"` branch (`cli.py:1081`, `:1282`).
- **CONSUMER:** the operator/caller reading `flow_state.json`, plus
  `_read_back_terminal_state` (CT1) which surfaces `status` in the summary.
- **Contract:** a non-zero stage exit ⇒ `FlowState.status == "FAILED"`,
  `active_role` = the failing role, `blocked_reason` names the role and code,
  pipeline stops (later stages do **not** run), and `_cmd_workflow` returns the
  stage's exit code. A `BLOCKED` verdict ⇒ `status == "FAILED"`,
  `last_route_decision == "blocked"`.
- **KILL-CHECK (PRIMARY, producer):** remove the
  `_write_stage_failure_state(...)` call in `_run_linear` (`cli.py:1542`) →
  `test_s8_stage_failure_writes_failed_state` fails (no `FAILED` artifact).
- **Second kill-check:** delete the `"BLOCKED": "FAILED"` entry at `cli.py:1081`
  → `test_s8_blocked_verdict_reaches_failed_status` fails.
- **Note:** this contract deliberately does **not** assert `exit_code != 0` for
  the BLOCKED case — see **Q35**.

### CT7 — aggregate `stop_reason` derives from terminal truth (data contract, §6.3) — NEW in v3

- **PRODUCER:** `_cmd_workflow`'s aggregate export (`cli.py:1780–1794`).
- **CONSUMER:** `global_history.runs` readers — `fa history`, and **S9's
  projections**.
- **Contract:** `stop_reason` is a function of `FlowState.status` (the semantic
  authority), not of `result_code` (a transport-level integer). Mapping table
  in S8.7. Unmapped status or unreadable artifact ⇒ fall back to the current
  `result_code` rule, never raise.
- **Invariant:** for any single run, `eval_report.verdict`,
  `flow_state.status`, and `global_history.stop_reason` are mutually
  consistent.
- **KILL-CHECK:** restore the `result_code` ternary at `cli.py:1782` →
  `test_s8_artifacts_agree_on_blocked_run` fails.
- **Note:** `exit_code` is deliberately **excluded** from this contract — see
  **Q35**. Conflating them would couple two operator-visible contracts.

### CT5 — invariant (§6.4)

> **CT5:** A completed `fa workflow` invocation leaves controller truth that
> can be reconstructed from disk alone, without parsing any human-readable
> prose. Enforced at `_cmd_workflow`; verified by C2
> `test_s8_aggregate_stop_reason_comes_from_flow_state` +
> `test_s8_controller_truth_is_machine_reconstructable`.

**Security contract (§6.5):** N/A — S8 adds no boundary. *(I-36, the one
security-adjacent finding in scope-adjacent code, is explicitly deferred.)*

---

## 4. Path & flag matrix (§7)

### 7.1 Path inventory

| P# | Trigger | File:line/symbol | Flag state | Covering S# |
|---|---|---|---|---|
| P1 | linear mode, all stages OK | `_run_linear` `cli.py:1528` | `--mode linear` | S8.2, S8.3 |
| P2 | linear, stage fails fast | `_run_linear` `cli.py:1542` → `_write_stage_failure_state` | `--mode linear` | **S8.6** (was wrongly marked covered in v1) |
| P3 | repair loop until PASS | `_run_repair` `cli.py:1561` | `--mode repair` | **covered L3** — `test_cli_ergonomics.py:338` |
| P4 | repair budget exhausted | `_run_repair` | `--max-repairs` | **covered L3** — `:360` |
| P5 | adaptive replan | `_run_adaptive` `cli.py:1388` | `--mode adaptive` | **covered L3** — `:500` |
| P6 | adaptive replan budget | `_run_adaptive` | `--max-replans` | **covered L3** — `:523` |
| P7 | aggregate export after any mode | `cli.py:1794` | always | S8.2 |
| P8 | workflow stdout, console | `_run_stage` → `_cmd_run:2212` | default | S8.4 |
| P9 | workflow stdout, quiet | `_run_stage` → `_cmd_run:2212` | `--output-mode quiet` **NEW** | S8.4 |
| P10 | `fa run` stdout, quiet | `_cmd_run:2212` | `--output-mode quiet` | S8.4 |
| P11 | repair/adaptive stage fails fast | `cli.py:1599`, `:1610`, `:1455`, `:1502` | any mode | S8.6 |
| P12 | eval returns `BLOCKED` verdict | `_write_terminal_state` `cli.py:1282` | any mode | S8.6 |

**Coverage gate:** P3–P6 are already L3 on their **happy paths** and are
explicitly **not re-tested** (rationale: §Preflight). P1, P2, P7–P12 each have a
covering step below. Note P2/P11/P12 were the v1 omission — P3–P6 being L3 is a
statement about the *loop* logic, not about what happens when a stage fails
inside it.

### 7.2 Flag matrix

| ID | Flags/env | Proves | Covering S# |
|---|---|---|---|
| A | `--mode linear`, defaults | operator-facing default path | S8.2, S8.3 |
| B | `--mode repair` + `--max-repairs` | loop + budget interaction | N/A — **already L3**, `:338`/`:360` |
| C | `--mode adaptive` + both budgets | compounding route normalization | N/A — **already L3**, `:500`/`:523`/`:543` |
| D | `--output-mode quiet` (workflow **and** run) | stdout contract on both surfaces | S8.4 |
| E | failing stage / BLOCKED verdict | terminal failure states across modes | S8.6 |
| P-x | provider family | N/A — workflow is provider-agnostic; stage-level provider behaviour is S7/ADR-9 territory | N/A |

---

## 5. Step-by-step implementation (§8)

> **Per-step protocol (operator-mandated).** Before editing: state
> source-verified behavior, contract + gap IDs, exact files allowed to change,
> stop on unresolved blockers. For each edit: idea / intent / current→target /
> mechanism / best practice / failure behavior / DoD + negative proof / test
> class / kill-check target. After each edit: targeted tests, static checks on
> changed files, `git diff` inspection, **report actual output**, never mark
> complete from "no exception". After a big chunk: targeted mutation testing.

### Step S8.0 — Re-verify preflight anchors (staleness rule)

Traces-to: all. Depends-on: none. Target liveness: n/a.

**Files allowed to change:** none (read-only).

Do:

1. `grep -n "_WORKFLOW_MODES\|output_mode\|duration_ms" src/fa/cli.py` — confirm
   `:1090`, `:1204`, `:1802` still resolve.
2. `grep -rn "load_flow_state\|load_eval_report" src/ --include=*.py | grep -v workflow_artifacts`
   — must still print **nothing** (the L1 finding).
3. Re-run the two probes recorded in the preflight log; confirm 102 stdout
   bytes and `duration_ms: 0`.

Exit criteria:

- [ ] all three anchors resolve at the recorded lines (or the plan is amended)
- [ ] zero-production-consumer finding reproduced
- [ ] probe outputs match the preflight log

---

### Step S8.1 — Record the Q32 decision (no longer a gate)

Traces-to: G4, CT4. Depends-on: none. Target liveness: n/a (decision record).

**RESOLVED 2026-07-30.** The operator defined `quiet` as a console-verbosity
control with identical processing. Adopted: **option (a), scoped to `quiet`** —
`console` output is unchanged; under `quiet` the status line goes to stderr and
stdout is byte-exactly `final_text`. Full reasoning and the adopted contract
table are in §7 Q32. S8.4 implements exactly that and nothing more.

Do:

1. Confirm §7 Q32's contract table matches S8.4's edit list before editing.
2. Update BACKLOG **I-38** to `RESOLVED — see S8.4` when S8.4 lands (not
   before; a backlog item closed ahead of its evidence is how status drifts).

---

### Step S8.2 — Real `duration_ms` + aggregate-row accuracy proof

Traces-to: G2, G3, CT3. Depends-on: S8.0.
**Parallelizable-with: S8.4, S8.6 — NOT S8.3/S8.7** (v3 correction: S8.2, S8.3
and S8.7 all edit the same aggregate-export block at `cli.py:1780–1794`;
running them concurrently guarantees a conflict). Sequence: **S8.2 → S8.3 → S8.7**.
Target liveness: G2 L2→L3, G3 L0→L3.

**Current source-verified behavior.** `cli.py:1802` passes `duration_ms=0` with
the comment *"not tracked at workflow level yet"*. Measured: the row lands with
`duration_ms: 0` while `turns: 3` and `role: 'planner→coder→eval'` are correct.
No test asserts any of it.

**Files allowed to change:** `src/fa/cli.py`, `tests/test_s8_workflow_controller.py` (NEW).

Edit:

- path: `src/fa/cli.py` · symbol: `_cmd_workflow` · change: capture
  `_wf_start_mono = time.monotonic()` immediately after mode validation; pass
  `duration_ms=int((time.monotonic() - _wf_start_mono) * 1000)` at `:1802`.

Do:

1. Add the monotonic anchor **before** `_resolve_workflow_lifecycle` so session
   setup is included in the measured wall time (it is part of the invocation).
2. Replace the literal `0`.
3. Delete the now-false `# not tracked at workflow level yet` comment.

Do-not:

- Do **not** add a `route`/`verdict` column to `global_history` (Q33, deferred).
- Do **not** use `time.time()` — monotonic is required; the existing `_cmd_run`
  pattern at `cli.py:2142`/`:2182` is the precedent.
- Do not "improve" `turns=0` at `:1783` — it is deliberate and documented.

**Idea now implemented:** a projection field that was a placeholder becomes
real. **Intent:** cross-run analytics (S9) must not read a constant.
**Mechanism:** monotonic delta, integer ms, same shape as `_cmd_run`.
**Best practice:** `time.monotonic()` is immune to wall-clock adjustment — the
standard choice for elapsed measurement. **Failure behavior:** unchanged — the
whole export stays inside the existing best-effort `try/except`, so a timing
bug cannot fail a completed workflow.

Exit criteria:

- [ ] `grep -n "duration_ms=0" src/fa/cli.py` → **no hit** in `_cmd_workflow`
- [ ] `mypy` + `ruff` clean on `cli.py`
- [ ] behavioral: aggregate row has `duration_ms > 0`
- [ ] behavioral: `role == "planner→coder→eval"`, `turns == 3`,
      `stop_reason == "workflow_complete"`, `exit_code == 0`

**Test class: C2** (CLI-only claim; root is `_cmd_workflow`).
**Oracle (ranked):** FS/DB effect — `global_history.runs` row fields.
**Kill-check target:** remove `export_session_to_global_history(...)`
(`cli.py:1794`) → `test_s8_workflow_aggregate_row_is_accurate` fails.
Second kill-check: restore `duration_ms=0` → the `> 0` assertion fails.

**Negative proof:** the test must fail if the export is deleted **and** if the
duration is re-hardcoded. Assert `duration_ms > 0` — never `>= 0`, which every
integer satisfies (the S7.C3 tautology lesson).

---

### Step S8.3 — Make the `global_history` export read terminal truth (the REAL consumer)

Traces-to: G1, CT1, CT2, CT5. Depends-on: S8.0. Parallelizable-with: S8.2 is
**FALSE** — both edit the same export block; do S8.2 first, then S8.3.
Target liveness: G1 L1→L3.

> **Redesigned in v3.** See §Preflight RV1–RV3. v2's mechanism could not run
> (the summary is printed inside the modes) and, once fixed, would have been a
> consumer whose only output was a string. This version wires the read-back
> into the consumer that **already needs it and currently guesses**.

**Current source-verified behavior.** `load_flow_state` (`workflow_artifacts.py:534`)
and `load_eval_report` (`:526`) are exported in `__all__`, referenced 30× in
`tests/`, and **0× in `src/`** outside their defining module. Meanwhile
`cli.py:1782` synthesises the aggregate row's semantic outcome from an integer:
`stop_reason = "workflow_complete" if result_code == 0 else "workflow_failed"`.
The authoritative terminal outcome — `FlowState.status`, one of 11 values — is
on disk, unread. Parent exit criterion *"artifacts are read back by their real
consumer"* is unmet, and the consumer that should be doing the reading is
producing **wrong data** (RV4).

**Files allowed to change:** `src/fa/cli.py`,
`tests/test_s8_workflow_controller.py` (NEW).

Edit:

- path: `src/fa/cli.py` · symbol: `_read_back_terminal_state` (**NEW**,
  module-level, placed next to `_write_terminal_state`) · change: load
  `artifact_paths.flow_state`, verify `state.run_id == run_id`, return
  `FlowState | None`.
- path: `src/fa/cli.py` · symbol: `_cmd_workflow` · change: call it **after**
  the mode dispatch (`:1758`) and **before** building `aggregate_outcome`
  (`:1780`); use the loaded status to derive `stop_reason` (see S8.7 for the
  exact mapping — S8.3 lands the *read*, S8.7 lands the *semantics*).

Do:

1. Implement `_read_back_terminal_state(artifact_paths, run_id)`. Take the two
   values it needs, **not** `ctx` — `_WorkflowContext` is not in scope at the
   export block, and a narrow signature is testable in isolation.
2. Call it once, storing `terminal_state`.
3. Guard: `except (OSError, ValueError, KeyError, TypeError)` →
   `logging.getLogger(__name__).warning("...", exc_info=True)`, return `None`.
4. When `None`, fall back to today's integer-derived `stop_reason` — the export
   must never become *less* reliable than it is now.

Do-not:

- **No generic transition engine** (parent §Do-not). Load + identity check only.
- Do not pass `ctx` — see Do #1.
- Do not let a failed read change the exit code or raise. The run is over; a
  projection read is not authority.
- Do **not** use bare `except Exception` — no new BLE001 waivers. Follow the
  `hooks/base.py` precedent (narrow tuple + `exc_info=True`).
- Do not also rewire `_print_terminal_summary` — that was v2's dead end (RV1).

**Idea now implemented:** the write-only artifact gains the consumer that was
already implicitly required. **Intent:** make CT5 true *and* stop the projection
from inventing outcomes. **Mechanism:** `load_flow_state(path)` + `run_id`
identity check, mirroring `SessionManager._read_manifest`'s
`manifest_identity_mismatch` (`manager.py:150`) — the identity check is what
makes it a verification rather than a decorative read. **Best practice:**
derive semantics from the semantic source, never from an exit code.
**Failure behavior:** fail-soft to today's behaviour; warn with traceback.

Exit criteria:

- [ ] `grep -rn "load_flow_state" src/ --include=*.py | grep -v workflow_artifacts`
      → **≥1 hit** (the L1→L3 flip, as a grep)
- [ ] `mypy` + `ruff` + `pylint src/fa` clean; **0 new `noqa`**
- [ ] behavioral: the aggregate row's `stop_reason` is derived from the
      persisted `FlowState`, proven by S8.7's assertions
- [ ] adversarial: corrupt `flow_state.json` → exit code **unchanged**, warning
      logged, export still writes a row
- [ ] adversarial: `flow_state.json` whose `run_id` belongs to another run →
      treated as unreadable, **not** trusted

**Test class: C2** (CLI root) + **C1** for the corrupt / foreign-identity paths.
**Oracle (ranked):** DB row field > return value. **Never** printed prose —
§9's ranking puts free text last and CT5 forbids prose as controller truth.
**Kill-check target (PRIMARY, producer):** remove the `write_flow_state(...)`
call in `_write_terminal_state` (`cli.py:1289`) → the read returns `None`,
`stop_reason` falls back, and
`test_s8_aggregate_stop_reason_comes_from_flow_state` fails.
**Consumer kill-check:** remove the `_read_back_terminal_state(...)` call → same
test fails.

**Negative proof:** the identity check is the difference between a read and a
*verification*. The foreign-`run_id` test is the one that proves it: a
consumer that loads any file it finds would pass every other assertion here.

---

### Step S8.7 — Fix the three-artifact disagreement (RV4)

Traces-to: G1, G6 (**NEW**), CT3, CT7 (**NEW**). Depends-on: **S8.3**.
Target liveness: G6 L0→L3.

> **This step fixes a real production defect found during the v3 review, not a
> gap in test coverage.** Per the plan's own stop rule the defect was *not*
> fixed inside the verification step that found it (S8.6); it is promoted to
> its own step with its own contract.

**Current source-verified behavior.** Measured on one run with a scripted
`BLOCKED` verdict:

| artifact | says |
|---|---|
| `eval_report.json` | `verdict='BLOCKED'`, `route='blocked'` |
| `flow_state.json` | `status='FAILED'` |
| `global_history.runs` | `stop_reason='workflow_complete'`, `exit_code=0` |
| process | `exit 0` |

Cause: `cli.py:1782` derives `stop_reason` from `result_code`, and every mode
returns `0` when the pipeline *ran to completion* regardless of verdict
(`:1558`, `:1638`). **S9's cross-run dashboards would count BLOCKED runs as
successes.**

**Files allowed to change:** `src/fa/cli.py`,
`tests/test_s8_workflow_controller.py`.

Edit:

- path: `src/fa/cli.py` · symbol: `_cmd_workflow` · change: derive
  `stop_reason` from `terminal_state.status` (from S8.3) instead of from
  `result_code`.

Mapping (explicit — the executor must not invent one):

| `FlowState.status` | `stop_reason` |
|---|---|
| `DONE` | `workflow_complete` |
| `FAILED` | `workflow_failed` |
| `REPAIR_REQUIRED` | `workflow_repair_required` |
| `REPLAN_REQUIRED` | `workflow_replan_required` |
| any other / read failed | fall back to today's `result_code` rule |

Do:

1. Add `_WORKFLOW_STATUS_TO_STOP_REASON: dict[str, str]` beside
   `_EVAL_VERDICT_TO_TERMINAL_STATUS` (`cli.py:1077`) — same shape, same file
   region, so the two mappings are read together.
2. Use `.get(status, <fallback>)` so an unmapped status degrades, never raises.
3. Leave `exit_code` **alone** — that is Q35, and it is a separate contract.

Do-not:

- Do not change any mode's return value. Exit-code semantics are Q35; touching
  them here would silently couple two operator-visible contracts in one diff.
- Do not add new `FlowStatus` values (§1 non-goal 4).
- Do not "fix" `eval_report.json` — it is already correct.

**Idea now implemented:** the projection tells the truth. **Intent:** S9 must be
able to compute an honest success rate. **Mechanism:** one dict lookup,
replacing a boolean-on-an-int. **Best practice:** a derived field should be
derived from the domain value, not from a transport-level status code — the
same reasoning that makes `EvalReport` the verdict authority rather than prose.
**Failure behavior:** unmapped status or failed read → today's behaviour.

Exit criteria:

- [ ] BLOCKED verdict run → `global_history.stop_reason == "workflow_failed"`
- [ ] PASS run → `stop_reason == "workflow_complete"` (**no regression**)
- [ ] repair-budget-exhausted run → `stop_reason == "workflow_repair_required"`
- [ ] all three artifacts **agree** for the same run
- [ ] `just check` green

**Test class: C2.**
**Oracle:** `global_history.runs.stop_reason` cross-checked against
`flow_state.json` and `eval_report.json` for the *same* run.
**Kill-check target:** revert to the `result_code` ternary at `cli.py:1782` →
`test_s8_artifacts_agree_on_blocked_run` fails.

**Negative proof:** asserting `stop_reason == "workflow_failed"` alone is weak —
it would also pass if the run genuinely crashed. The test must assert the
**agreement**: `eval_report.verdict == "BLOCKED"` **and**
`flow_state.status == "FAILED"` **and** `stop_reason == "workflow_failed"`
**and** `exit_code == 0` (documenting Q35's deliberate split). One artifact
proves nothing; three agreeing prove the wiring.

---

### Step S8.4 — I-38 / Q31: stdout carries payload only (both surfaces)

Traces-to: G4, CT4. Depends-on: **S8.1 (Q32 answered)**. Target liveness: L0→L3.

**Current source-verified behavior.** `_cmd_run` prints
`f"{status}: {outcome.stop_reason} (turns={outcome.turns})"` to **stdout**
(`cli.py:2212`), then `outcome.final_text` (`:2214`). Measured: `fa run
--output-mode quiet` emits **34 bytes** to stdout (29 + 5) while stderr is
**0**; `fa workflow` emits **102 bytes** (3 × 34) because every stage prints.
`QuietRenderer`'s docstring (`output.py:449`) promises *"nothing on stdout"* —
false today. Workflow's own summary lines already correctly use
`file=sys.stderr` (`cli.py:1318`, `:1332`, `:1533`).

**Files allowed to change:** `src/fa/cli.py`, `src/fa/output.py` (docstring
only), `tests/test_s8_workflow_controller.py`, `tests/test_s6_renderers.py`
(docstring-coupled assertion only).

Edit:

- path: `src/fa/cli.py` · symbol: `_cmd_run` · change: `cli.py:2212` status
  line becomes **mode-conditional** per resolved **Q32** —
  `print(..., file=sys.stderr if output_mode == "quiet" else sys.stdout)`.
  `output_mode` is already in scope at `cli.py:2127`. `:2214` `final_text`
  stays on stdout in **both** modes. Default `console` output is **unchanged**.
- path: `src/fa/cli.py` · symbol: `build_parser` workflow section · change: add
  `--output-mode {console,quiet}` default `console`, mirroring `cli.py:490`.
- path: `src/fa/cli.py` · symbol: `_run_stage` · change: `cli.py:1204`
  `"output_mode": "console"` → `getattr(ctx.args, "output_mode", "console")`.
- path: `src/fa/output.py` · symbol: `QuietRenderer` docstring · change: state
  the now-true contract and cite the resolution.

Do:

1. Make the status line's stream mode-conditional (NOT an unconditional move —
   Q32 resolved to scope this to `quiet` so `console` UX is untouched).
2. Add the workflow flag; forward it through `stage_kwargs`.
3. Update the `QuietRenderer` docstring **in the same commit** as the
   behaviour change.
4. Record the Q31/Q32 resolution inline in the S7 plan §9 Q31 entry.

Do-not:

- Do not suppress `final_text` — it **is** the payload.
- Do not add `--output-mode json` (Phase 2, `cli.py:2137` comment).
- Do not change `ConsoleRenderer` behaviour; it already writes to stderr.
- Do not leave the docstring stale — a docstring that describes a contract the
  code violates is how I-38 arose in the first place.

**Idea now implemented:** the documented contract becomes the actual one.
**Intent:** `fa run --task ... > result.txt` yields a parseable artifact; S9 can
consume workflow output without stripping an unversioned human line.
**Mechanism:** `file=sys.stderr` on one `print`; flag plumbed through the
existing `stage_kwargs` dict. **Best practice:** data on stdout, diagnostics on
stderr — POSIX convention; the same split `ConsoleRenderer` already honours.
**Failure behavior:** none introduced; a redirect cannot fail.

Exit criteria:

- [ ] `fa run --output-mode quiet` → captured stdout **byte-identical** to
      `final_text`
- [ ] `fa run` **default console** → stdout **unchanged** from today (status +
      payload). This is a regression guard on the scoping decision, not a
      formality.
- [ ] `fa workflow --output-mode quiet` → captured stdout is the concatenation
      of stage payloads only; **no `OK:` substring**
- [ ] `grep -n "OK: stopped_by_llm" ` in captured **stderr** → present (moved,
      not deleted)
- [ ] `QuietRenderer` docstring matches measured behaviour
- [ ] full suite green — this changes output every existing test may observe

**Test class: C2** (CLI-only claim), plus **C1** for the renderer docstring
coupling in `test_s6_renderers.py`.
**Oracle (ranked):** exit code + captured stream bytes. Byte-exact equality
with `final_text`, not a substring check.
**Kill-check target:** revert the conditional to an unconditional
`print(...)` on stdout at `cli.py:2212` → `test_s8_quiet_stdout_is_payload_only`
fails (stdout gains 29 bytes). Inverse kill-check: make it unconditionally
stderr → `test_s8_console_stdout_unchanged` fails. **Both directions must
fail** — that is what pins a conditional, as opposed to a constant.
Second: remove the `output_mode` forwarding at `:1204` →
`test_s8_workflow_quiet_stdout_is_payload_only` fails.

**Negative proof:** asserting `"OK:" not in stdout` alone is weak — it passes
if the command never ran. Pair it with a **positive control**: assert
`stdout == expected_payload` **and** `exit_code == 0` **and** the payload is
non-empty. *(Direct application of the S7.C4 lesson: an absence assertion
needs a liveness witness.)*

---

### Step S8.6 — Terminal failure states (the v1 audit omission)

Traces-to: G5, CT6. Depends-on: S8.0. Parallelizable-with: S8.2, S8.3.
Target liveness: G5 L2→L3.

**Current source-verified behavior.** `_write_stage_failure_state`
(`cli.py:1242`) writes `status="FAILED"`, `active_role=<failing role>`,
`blocked_reason="stage '<role>' exited <code>"`, prints a fail-fast line to
stderr, and the mode returns the stage's exit code. Verified by probe with a
persistent-500 transport: `exit=2`, `status='FAILED'`, `active_role='planner'`.
Separately, `_EVAL_VERDICT_TO_TERMINAL_STATUS` (`cli.py:1077–1082`) maps
`BLOCKED → FAILED`; probe confirms `status='FAILED'`, `route='blocked'`,
`exit=0`. **Neither path has any test.**

**Files allowed to change:** `tests/test_s8_workflow_controller.py` (NEW).
**No production change** — this step proves existing behaviour. If a defect is
found, STOP and promote it (do not fix inside a verification step).

Edit:

- path: `tests/test_s8_workflow_controller.py` · symbol: `_FailingTransport`
  (NEW test fixture) · change: a `Transport` returning a persistent HTTP 500,
  mirroring what `UrllibTransport` yields on upstream failure
  (`transport.py:117`) — **not** a raising mock, which would test an
  unreachable path.

Do:

1. `test_s8_stage_failure_writes_failed_state` — linear mode, planner stage
   fails; assert `exit == 2`, `FlowState.status == "FAILED"`,
   `active_role == "planner"`, `blocked_reason` contains the role and code.
2. Assert **fail-fast**: `transport.coder_calls == 0` and
   `eval_calls == 0` — later stages must not run. This is the assertion that
   makes it a *pipeline* test rather than a state-string test.
3. `test_s8_blocked_verdict_reaches_failed_status` — `_RoleAwareTransport`
   scripted `("BLOCKED","blocked")`; assert `status == "FAILED"`,
   `last_route_decision == "blocked"`, `blocked_reason` non-empty.
4. Assert `eval_report.json` and `flow_state.json` **agree** — verdict
   `BLOCKED` ↔ status `FAILED`. Cross-artifact consistency is the real claim.
5. **(v3, RV5)** Assert the failure path still writes a `global_history` row.
   The export sits after the single terminal `return` (`cli.py:1809`), so it is
   reached even when a stage fails — probed: `{'exit_code': 2, 'stop_reason':
   'workflow_failed', 'turns': 0}`. This is *good* behaviour that nothing
   currently protects; a future early-`return` in the failure branch would
   silently drop failed runs out of the projection, biasing every S9 metric
   toward success. Assert `exit_code == 2` and a row exists.

Do-not:

- Do not use a transport that raises `OSError`. Probed: it propagates as an
  unhandled traceback out of `_cmd_workflow`, because the real transport
  catches `URLError`/`TimeoutError`/`ConnectionError` and converts them to
  `status=0` responses. Testing a raising transport would assert behaviour the
  production stack cannot produce — a fixture-honesty violation
  (tests-writing skill: honest types at wiring boundaries).
- Do not assert on the stderr prose beyond a substring; free text is the
  lowest-ranked oracle.
- Do not change the exit-code semantics — see **Q35**.

**Idea now implemented:** the failure half of the controller gets the same
evidence standard as the success half. **Intent:** parent Do #4's "terminal
states" means *all* terminal states. **Mechanism:** drive the real
`_cmd_workflow` with a realistic failing transport; oracle is the persisted
artifact plus per-role call counts. **Best practice:** failure paths are where
controllers rot — they are exercised rarely in production and never by
happy-path tests. **Failure behavior:** n/a (verification-only step).

Exit criteria:

- [ ] `grep -c '"FAILED"' tests/test_s8_workflow_controller.py` ≥ 2
- [ ] fail-fast proven by `coder_calls == 0`, not by absence of output
- [ ] `BLOCKED` proven end-to-end through `_cmd_workflow`, not via
      `parse_eval_report` alone
- [ ] both new tests fail when their producer is removed (executed, not assumed)

**Test class: C2** (CLI root, `_cmd_workflow`).
**Oracle (ranked):** exit code + persisted `FlowState` fields + transport
call-count trajectory. Prose last, and never alone.
**Kill-check target (PRIMARY, producer):** remove
`_write_stage_failure_state(...)` at `cli.py:1542` → test 1 fails.
Second: delete `"BLOCKED": "FAILED"` at `cli.py:1081` → test 3 fails.

**Negative proof:** asserting only `status == "FAILED"` is weak — a test that
never ran the pipeline cannot distinguish "failed correctly" from "never
started". The `coder_calls == 0` **plus** `planner_calls == 1` pair is the
liveness witness: the pipeline demonstrably started and demonstrably stopped.
*(Direct reuse of the S7.C4 positive-control lesson.)*

---

### Step S8.8 — Projection path resolved at call time (operator-approved scope addition)

Traces-to: G2, CT3, **CT8 (NEW)**. Depends-on: S8.7. Target liveness: L0→L3.

> **Added mid-execution, 2026-07-30, with explicit operator approval.** The
> S8.2/S8.7 tests failed in-suite while passing alone. Investigating rather
> than relaxing them surfaced a **second production bug** outside the plan's
> allowed-files list. Per the stop rule the work paused and the operator
> authorised adding `src/fa/inner_loop/global_history.py`.

**Current source-verified behavior.** `global_history.py:34` binds
`DEFAULT_GLOBAL_HISTORY_PATH = Path.home() / ".fa" / "global_history.db"` at
**import time**. Measured with `FA_STATE_ROOT=/tmp/custom-root`:

```text
READER (fa stats --global-history, cli.py) -> /tmp/custom-root/global_history.db
WRITER (import-time constant)              -> /home/user/.fa/global_history.db
SAME FILE? False
```

**INTENT.** One path, resolved once, honoured by both sides. An operator who
sets `FA_STATE_ROOT` must not get an empty `fa stats` while rows accumulate in
a directory nobody reads.

**Why it is a real defect, not test friction:**

1. **Split brain in production.** The reader already resolved at call time; only
   the writer did not. `fa-entrypoint.sh:214` honours `FA_STATE_ROOT`, so a
   container operator setting it silently loses their history view.
2. **It violates a documented invariant.** `fa_state_root()`'s own docstring
   promises resolution *"on every call ... so a caller that reconfigures its
   environment (an embedder, a test, the container entrypoint) is honoured
   rather than silently ignored."*
3. **Known defect class, never swept.** `state.py:57` `default_state_root` is
   the V10 fix for exactly this, and its docstring records how an import-time
   constant made ten tests share one directory. S8.8 is the second instance.

**Production-grade shape (best practice applied):**

- **Call-time resolver, not a mutable global.** A module-level constant that
  callers reassign is a hidden singleton; a function is explicit, thread-safe,
  and trivially testable.
- **Mirror existing prior art exactly.** Same name shape (`default_*_path`),
  same "constant retained for compatibility" decision as `default_state_root`.
  A codebase with two idioms for one problem is worse than either idiom.
- **Single source of truth.** The reader (`cli.py`) now calls the same helper
  instead of recomputing `fa_state_root() / "global_history.db"` itself.
  Duplicated derivation is how the two sides drifted apart.
- **Backward compatible.** `DEFAULT_GLOBAL_HISTORY_PATH` stays exported as a
  deprecated alias; explicit `db_path=` injection still wins, so every existing
  caller is untouched.
- **No behaviour change by default** — byte-identical when `FA_STATE_ROOT` is
  unset, so no migration is implied.

**Failure behavior:** none introduced. Path resolution cannot fail; a bad
`FA_STATE_ROOT` is already validated by `fa_state_root` (absolute-path check).

Exit criteria:

- [x] `default_global_history_path()` honours `FA_STATE_ROOT`
- [x] writer and reader resolve to the **same** file
- [x] unset ⇒ byte-identical to the legacy constant
- [x] explicit `db_path=` still overrides
- [x] `authoring-check` 0 diagnostics (new public symbol in `__all__`)

**Test class: C0** ×3 (pure path policy), **paired** with the C2 tests above
which exercise the same resolution through the shipped `_cmd_workflow` — per
tests-writing skill §10 a C0 must never stand alone.
**Kill-check target:** revert `GlobalHistoryStore.__init__` to the import-time
constant → **9 of 16 tests fail**, including the dedicated
`test_s8_global_history_path_honours_state_root`. *Executed and observed.*

**Negative proof:** the regression test asserts the resolved path **equals the
override root**, not merely that it is non-empty — a resolver returning any
path at all would pass a weaker assertion.

---

### Step S8.5 — Targeted mutation testing (after the big chunk)

Traces-to: G1–G4. Depends-on: S8.2, S8.3, S8.4.

Do:

1. Add `src/fa/inner_loop/workflow_artifacts.py` to `[tool.pytest-gremlins]
   paths` and `[tool.mutmut] source_paths` (pyproject `:342`, `:245`) — it is
   pure parse/serialise logic, the ideal mutation target, and is **not**
   currently covered by either tool.
2. Run gremlins over `workflow_artifacts.py`.
3. Run `scripts/mutation_sweep.py` (statement deletion) over the changed
   `cli.py` regions — the two tools are complementary; gremlins ships no
   statement-deletion operator.
4. **Confirm the `N passed` line before believing any kill percentage** — a
   collection failure still prints 100%.

Exit criteria:

- [ ] gremlins: 0 survivors on `workflow_artifacts.py`, with `N passed` confirmed
- [ ] sweep: every survivor either killed by a new assertion or recorded with a
      written justification

---

## 6. Verification plan (§9)

All tests land in **`tests/test_s8_workflow_controller.py`** (NEW) unless
stated. **Authored strictly under the tests-writing skill.**

| CT# | Test | Class | Oracle (ranked) | Kill-check target (PRODUCER) | Paths |
|---|---|---|---|---|---|
| CT2 | `test_s8_aggregate_stop_reason_comes_from_flow_state` | C2 | `global_history.stop_reason` traced to the persisted status | `write_flow_state(...)` `cli.py:1289` | P1 |
| CT2 | `test_s8_read_back_survives_corrupt_artifact` | C1 | exit code unchanged + row still written + warning logged | `_read_back_terminal_state` except-branch | P2 |
| CT2 | `test_s8_read_back_rejects_foreign_run_id` | C1 | returns `None`; foreign state **not** trusted | the `run_id` identity check | P1 |
| CT7 | `test_s8_artifacts_agree_on_blocked_run` | C2 | 3-way agreement: verdict ↔ status ↔ `stop_reason` | `result_code` ternary `cli.py:1782` | P12 |
| CT7 | `test_s8_pass_run_stop_reason_unchanged` | C2 | `workflow_complete` on PASS (**regression guard**) | same | P1 |
| CT3 | `test_s8_failure_path_still_exports_row` | C2 | row exists with `exit_code=2` after a failing stage | export block `cli.py:1794` | P2, P11 |
| CT3 | `test_s8_workflow_aggregate_row_is_accurate` | C2 | `global_history.runs` row fields | `export_session_to_global_history` `cli.py:1794` | P7 |
| CT3 | `test_s8_workflow_duration_is_real` | C2 | `duration_ms > 0` | the monotonic delta at `cli.py:1802` | P7 |
| CT4 | `test_s8_quiet_stdout_is_payload_only` | C2 | captured stdout bytes, byte-exact | `file=sys.stderr` at `cli.py:2212` | P10 |
| CT4 | `test_s8_workflow_quiet_stdout_is_payload_only` | C2 | captured stdout bytes | `output_mode` forwarding at `cli.py:1204` | P9 |
| CT4 | `test_s8_status_line_moved_to_stderr` | C2 | captured stderr contains `OK:` | same as above | P8 |
| CT4 | `test_s8_console_stdout_unchanged` | C2 | captured stdout still has status + payload | inverse kill-check (see S8.4) | P8 |
| CT4 | `test_s8_quiet_changes_console_not_durable_state` | C2 | DB row count + artifact set equal across modes | `QuietRenderer` wiring `cli.py:2135` | P9, P10 |
| CT5 | `test_s8_controller_truth_is_machine_reconstructable` | C2 | `FlowState` + `EvalReport` loaded from disk only | both write calls | P1 |
| CT6 | `test_s8_stage_failure_writes_failed_state` | C2 | exit code + `FlowState.status` + `coder_calls == 0` | `_write_stage_failure_state` `cli.py:1542` | P2, P11 |
| CT6 | `test_s8_blocked_verdict_reaches_failed_status` | C2 | `FlowState.status` + cross-artifact agreement with `eval_report.json` | `"BLOCKED": "FAILED"` `cli.py:1081` | P12 |

**LIVE-PATH PROOF**

```text
root:        _cmd_workflow (src/fa/cli.py:1641)
matrix:      A (linear defaults) + D (quiet)
test:        tests/test_s8_workflow_controller.py::test_s8_controller_truth_is_machine_reconstructable
oracle:      FS artifact fields + global_history row (never prose)
kill-check:  removing write_flow_state / export_session_to_global_history fails it
producer:    cli.py:1794 (export), _write_terminal_state (artifact)
consumer:    _read_back_terminal_state (NEW, cli.py)
paths-covered: 8/12 by new tests; 4/12 (P3–P6) already L3 on happy paths — see §4.1
artifact-agreement: 3-way (eval_report ↔ flow_state ↔ global_history) — CT7
contract-check: PASS required (`just check`)
efficiency:  transport call_count asserted per stage (existing _RoleAwareTransport)
pyramid:     A
```

**CI authority:** `just check` — `lock-check`, `dependency-contract-check`,
`lint` (ruff + deptry + `pylint src/fa`), `typecheck` (bare `python -m mypy`),
`authoring-check`, `contract-check`, `log-kind-check`, `no-mocked-dataclasses`,
`test` (`pytest --cov`, `fail_under = 80`). **Not** the Makefile.

---

## 7. Risks, rollback, open questions (§10)

### Risks

| RK# | Risk | Mitigation | How detected |
|---|---|---|---|
| RK1 | Moving the status line to stderr breaks an existing test that asserts on stdout | Full-suite run is an exit criterion of S8.4, not an afterthought | `pytest` full run |
| RK2 | A downstream script parses `OK:` from stdout today | Behaviour change is the *point* (I-38); call it out in the PR note and HANDOFF | Operator review |
| RK3 | `_read_back_terminal_state` masks a real write failure by failing soft | Identity check + `exc_info=True` warning; the write path keeps its own errors | `test_s8_read_back_survives_corrupt_artifact` |
| RK4 | Adding `workflow_artifacts.py` to mutation scope lengthens the sweep | Module is small and pure; measured cost recorded in S8.5 | Sweep runtime |
| RK5 | Scope creep into a transition engine (parent §Do-not) | S8.3 Do-not is explicit; reviewer checks the diff is a load + identity check | `git diff` review |
| RK6 | **S8.2/S8.3/S8.7 all edit `cli.py:1780–1794`** — concurrent execution conflicts | Declared strictly sequential (S8.2 → S8.3 → S8.7); §4 dependency lines corrected in v3 | `git diff` / merge conflict |
| RK7 | S8.7 changes `stop_reason` values that a dashboard or query may already match on | Two new values (`workflow_repair_required`, `workflow_replan_required`) are **additive**; `workflow_complete`/`workflow_failed` keep their spelling. Regression guard: `test_s8_pass_run_stop_reason_unchanged` | C2 test + PR note |
| RK8 | Fixing `stop_reason` but not `exit_code` leaves a *partial* truth — a reader trusting `$?` is still misled | Deliberate and documented (Q35a). S8.7's test asserts `exit_code == 0` **on purpose**, so the split is visible in the test, not hidden | `test_s8_artifacts_agree_on_blocked_run` |

### Rollback (required at P2)

- No feature flag needed: S8.2/S8.3 are additive; S8.4 is a one-line stream
  change plus a new flag defaulting to today's behaviour (`console`).
- Revert path: `git revert` of the S8.4 commit restores the old stdout exactly;
  S8.2/S8.3 are independently revertible.
- No data migration — `global_history` schema is unchanged (`duration_ms`
  already exists and already defaults to `0`).

### Open questions

### Q32 — **RESOLVED (operator, 2026-07-30): option (a), scoped to `quiet`**

*I-38 fold-in: which stdout contract does `fa run` / `fa workflow` adopt?*

**Operator answer, verbatim context:** *"quiet mode outputs to cli less info per
turn, all info is processed as usual — db writes, artifact creation/update,
etc."*

**Interpretation and resolution.** The operator defines `quiet` as a **console
verbosity** control that must not alter processing — the durable side of the
system (session.db rows, `flow_state.json`, `eval_report.json`,
`global_history` row) is identical in every mode. S7.C5 already proved that
half holds today: stderr went to 0 bytes while the DB still took all 7 rows.

That framing settles the sub-question v1 flagged. If `quiet` is a *verbosity*
knob, then **the status line moves to stderr only under `--output-mode quiet`**,
not unconditionally:

- Default `console` UX is unchanged — no surprise for existing users, and the
  status line remains where a human reading the terminal expects it.
- `quiet` becomes what its docstring always claimed: stdout is the payload, so
  `fa run --task ... > result.txt` is parseable.
- "Less info on the console, identical processing" is exactly what a
  mode-scoped rule expresses. An unconditional move would be a change to
  `console` too — which the operator did **not** ask for.

**Adopted contract (CT4, revised):**

| mode | stdout | stderr | durable side effects |
|---|---|---|---|
| `console` (default) | status line + `final_text` — **unchanged** | live renderer | full |
| `quiet` | **`final_text` only**, byte-exact | status line + faults | **identical to console** |

**Consequence for S8.4:** the edit is no longer a bare `file=sys.stderr` on
`cli.py:2212`. It becomes a mode-conditional stream selection, e.g.
`status_stream = sys.stderr if output_mode == "quiet" else sys.stdout`, with
the mode already in scope at `cli.py:2127`. This is *more* conservative than
v1's assumption and strictly smaller in blast radius: no existing
`console`-mode test can break.

**Third required assertion (new):** because the operator's definition is
"identical processing", S8.4 must also prove the **durable equivalence** —
running the same task in `console` and in `quiet` yields the same DB row count
and the same artifact set. Without it, "quiet only changes the console" is an
unproven claim. Added to §6 as `test_s8_quiet_changes_console_not_durable_state`.

**Q35 — NON-BLOCKING, but upgraded in v3 to a real fork. Default recorded.**

*Should a `BLOCKED` verdict / exhausted budget make `fa workflow` exit non-zero?*

Measured: `BLOCKED` yields `flow_state.status='FAILED'` but **`exit=0`**; an
exhausted repair budget also returns 0 (`test_cli_ergonomics.py:369` pins this
deliberately: *"linear/repair baseline does not fail the process"*). A stage
*crash* exits 2; a controller-level *rejection* exits 0.

**v3 raises the stakes.** v2 treated this as cosmetic. The review showed the
exit code is **load-bearing**: it is the sole input to the aggregate row's
`stop_reason` (`cli.py:1782`), which is why a BLOCKED run is projected as
`workflow_complete` (RV4). S8.7 severs that coupling — `stop_reason` will come
from `FlowState` — which makes the exit code a *pure* CLI concern again and
therefore safe to decide independently. **S8.7 is a prerequisite for ever
answering Q35 cleanly**, and that is an argument for doing S8.7 now.

- **Q35a** — keep `exit 0` for rejections. Rationale: the tool ran correctly;
  the *code under review* was rejected. Exit code describes the tool.
  Consequence: `fa workflow && deploy` proceeds on a BLOCKED verdict; CI must
  read `flow_state.json`, not `$?`.
- **Q35b** — exit non-zero (e.g. `1`) on a non-`DONE` terminal status.
  Consequence: CI gates work naturally; **breaks** `test_cli_ergonomics.py:369`
  and any operator script that treats 0 as "ran".

**Default for S8: Q35a — keep current behaviour, assert it explicitly, do not
change it.** Changing exit-code semantics is an operator-visible contract change
that belongs with S9/S10 (the consumers). S8.6 and S8.7 pin today's behaviour so
that any future change is a deliberate, visible diff rather than silent drift.
**Recommendation for S9: revisit as Q35b** — once `stop_reason` is honest, the
exit code is the only remaining lie, and CI gating is the main reason anyone
runs `fa workflow` unattended. Flag in handoff.

**Q33 — NON-BLOCKING. Default recorded.**
*Should `global_history` gain `route_decision` / `verdict` columns so workflow
outcomes are queryable without opening `eval_report.json`?*
**Default: NO for S8** — it is a schema change to a projection consumed by S9,
and S9 owns that surface. Executor proceeds without it and flags in handoff.

**Q34 — RESOLVED (operator, 2026-07-30): SECOND gate.**
*Is workflow part of the first production deployment gate, or a second gate
after direct `fa run`?* (Parent Do #6.)
**Operator answer:** *"workflow is a SECOND gate. we will test it in detail
after we finish with this main workplan through all slices."*
This matches the plan's recorded default and the evidence: `fa run` has
container proof (S7.C0–C7); workflow has none. Promoting workflow into the
first gate would claim L3 on a surface never exercised in a container — the
error the parent's §Do-not forbids. **Parent Do #6 is hereby answered.** A
container workflow verification sheet (the S7-container analogue) is deferred
to after the final slice; noted in HANDOFF so it is not lost.

---

## 8. Research-note disposition (§11a)

| RN# | Note item (source) | Verdict | Why | Anchor |
|---|---|---|---|---|
| RN1 | Parent Do #1 "verify linear, repair, adaptive independently" | **Reject (already L3)** | 12 tests at `test_cli_ergonomics.py:279–577` cover all three modes with budget + route negatives. Re-testing adds a second oracle for one behaviour — the S6 matrix-E tautology. | §4.1 P3–P6 |
| RN2 | Parent Do #2 "FlowState owns controller truth, EvalReport owns verdict/route" | **Rewrite** | Truth is *written* but never *read* in production. The real gap is the missing consumer, not the ownership split. | S8.3 / CT2 |
| RN3 | Parent Do #3 "pr_draft.md remains narrative, not controller truth" | **Reject (already true)** | Grep-verified: zero controller reads. `PrDraftStore` is IntentGuard's seam only. | Preflight |
| RN4 | Parent Do #4 "verify budgets, preconditions, terminal states, artifact persistence" | **PARTIAL — v1 said Reject, v2 corrects to Accept-in-part** | Budgets and role preconditions **are** L3 (`test_cli_ergonomics.py` `:360`, `:380`, `:414`, `:523`, `:572`); persistence rejection **is** L3 (`test_workflow_artifacts.py` `:224`/`:245`). But **"terminal states" is NOT** — the terminal *failure* state has 7 producer call sites and 0 tests. v1 rejected the whole row on the strength of the covered two-thirds. | **S8.6** / CT6 / G5 |
| RN4b | *(meta)* v1's own audit method | **Rewrite** | "Already covered" was evaluated per-*feature* ("repair mode is tested") rather than per-*branch* ("repair mode's failure path is tested"). The corrected rule is recorded in §Preflight and should carry to S9–S11. | §Preflight |
| RN5 | Parent Do #5 "verify aggregate global-history fields — turns, role, duration, route" | **Accept** | Measured: `role`/`turns` correct but **untested**; `duration_ms` hardcoded `0`; **no route column exists**. | S8.2 / CT3 / Q33 |
| RN6 | Parent Do #6 "decide first or second deployment gate" | **Accept as decision** | Answered with a default and a reason. | Q34 |
| RN7 | Operator: "fold I-38/Q31 into slice 8" | **Accept** | Workflow is where it compounds (102 B vs 34 B, measured), and S9 consumes this output. | S8.4 / CT4 / Q32 |
| RN8 | BACKLOG I-36, I-37, I-39 | **Defer** | Operator decision: after the main workplan. Not S8 blockers. | §1 non-goal 6 |
| RN9 | Parent Do-not "no generic transition engine" | **Accept as constraint** | Encoded as S8.3 Do-not + RK5. | S8.3 |
| RN10 | *(v3 self-review)* v2's S8.3 mechanism | **Reject — impossible** | `_print_terminal_summary` runs inside the modes (7 sites) before `_cmd_workflow` resumes. The step could not have been executed as written. | RV1 / S8.3 |
| RN11 | *(v3 self-review)* "add a consumer to satisfy the exit criterion" | **Rewrite** | A consumer whose only effect is a printed string is decoration. Found the consumer that already needed the data and was fabricating it. | RV2–RV3 / S8.3 |
| RN12 | *(v3 self-review)* three-artifact disagreement | **Accept — production defect** | Not a coverage gap. BLOCKED run projected as `workflow_complete`; S9 would compute a false success rate. | RV4 / S8.7 / G6 |
| RN13 | *(v3 self-review)* `duration_ms > 0` flake risk | **Accept risk, no change** | Measured ~132 ms for 3 scripted stages; sub-1 ms is unreachable. Recorded so nobody "fixes" it to `>= 0` (tautology). | RV6 / S8.2 |

---

## 9. Definition of Done (§11.3)

**STATE — before → after, and how to observe**

| | Before | After | Observed by |
|---|---|---|---|
| `flow_state.json` | written, never read in prod | written **and** read back with identity check | `grep load_flow_state src/` → ≥1 hit; C2 test |
| workflow `duration_ms` | `0` | `> 0`, real elapsed | `global_history.runs` row |
| aggregate row accuracy | untested | asserted (role/turns/exit/stop_reason) | C2 test |
| `fa run` stdout (quiet) | 34 bytes | byte-identical to `final_text` | captured stream |
| `fa workflow` stdout (quiet) | 102 bytes | payload only, no `OK:` | captured stream |
| `QuietRenderer` docstring | **false** | true (mode-scoped wording) | code review + C1 test |
| terminal `FAILED` state | 7 producer sites, 0 tests | asserted end-to-end, fail-fast proven | C2 tests (S8.6) |
| `BLOCKED` verdict → `FAILED` | parser-level C0 only | proven through the controller | C2 test (S8.6) |
| durable state across modes | unproven | asserted identical | C2 test (S8.4) |
| `global_history.stop_reason` | derived from an **int**; BLOCKED run recorded as `workflow_complete` | derived from `FlowState.status`; artifacts agree | C2 tests (S8.7) |
| failure-path projection row | works, untested | asserted | C2 test (S8.6) |

**ARTIFACTS**

- Created: `tests/test_s8_workflow_controller.py`.
- Modified: `src/fa/cli.py`, `src/fa/output.py` (docstring),
  `tests/test_s6_renderers.py` (docstring-coupled assertion), `pyproject.toml`
  (mutation scope), this plan, `worklogs/HANDOFF.md`, `knowledge/BACKLOG.md`
  (I-38 → resolved).
- **No other file may change.** Anything else is scope creep (RK5).

**CONTRACTS**

| CT# | Status target |
|---|---|
| CT1 `_read_back_terminal_state` | PLANNED → IMPLEMENTED → **VERIFIED** |
| CT2 artifact read-back | PLANNED → **VERIFIED** (producer kill-check) |
| CT3 aggregate projection | PLANNED → **VERIFIED** |
| CT4 stdout contract | **BLOCKED on Q32** → VERIFIED |
| CT5 machine-reconstructable truth | PLANNED → **VERIFIED** |

**S8 is DONE only when:**

- [ ] G1–**G6** all reach **L3** (producer kill-check holds for each).
- [ ] **Every test was written under `knowledge/skills/tests-writing/SKILL.md`**:
      class declared in the docstring (C0/C0p/C1/C2/C3), ranked oracle named,
      producer kill-check target named, existence pre-check present, honest
      types (no loosened mocks at wiring boundaries), no `TEST-EDITS`
      weakening of an existing assertion.
- [ ] Every C0-consumer test is paired with a C1/C2 producer test (skill §10 —
      unpaired consumer tests are theater).
- [ ] `just check` green — including bare `python -m mypy` and `pylint src/fa`
      at 10.00/10.
- [ ] Coverage ≥ `fail_under = 80`.
- [ ] Mutation: 0 survivors on `workflow_artifacts.py`, with the `N passed`
      line confirmed (a collection failure still prints 100%).
- [ ] **No `noqa` waivers added.** Broad catches use narrow exception tuples
      with `exc_info=True`, per the `hooks/base.py` precedent.
- [ ] Non-goals respected — no transition engine, no inspect CLI, no resume, no
      I-36/I-37/I-39 work.
- [ ] All RN# dispositioned (§8), all Q# resolved or defaulted (§7).
- [ ] **Negative proof recorded per step** — for each claim, the specific
      deletion that makes the test fail was *executed*, not asserted.

**Negative proof (plan-level).** This plan is invalid if any G# is marked done
on "the suite is green" without the corresponding producer deletion having been
run and observed to fail. Three checks in this workstream have already been
caught passing vacuously (S7.C3's contradictory predicate, S7.C4's
control-free absence, S7.C7's silent `find`); the same failure mode is assumed
present here until each kill-check is executed.

---

## 10. Anti-theater + READY gate (§11.2, §11.4)

### 11.2 Anti-theater checklist

- [x] Every referenced symbol verified via preflight (file:line) or marked NEW
- [x] Every G# maps to ≥1 CT#, ≥1 S#, ≥1 verification — G1→CT1/CT2/S8.3, G2→CT3/S8.2, G3→CT3/S8.2, G4→CT4/S8.4
- [x] Every signal CT# has producer **and** consumer (CT2 consumer is the NEW function; CT4 consumer is the redirecting caller)
- [x] Every kill-check targets the PRODUCER
- [x] Path inventory has no uncovered path without explicit non-goal (P3–P6 waived with recorded reason)
- [x] Matrix rows each have a covering step or explicit "N/A — why"
- [x] Dual-write: N/A stated for CT2 (single FS channel)
- [x] Fixtures are honest — reuse `_RoleAwareTransport`/`_ScriptedTransport`, real `_cmd_workflow`, no loosened mocks
- [x] No vague verbs without a mechanism
- [x] Assumptions labeled (Q32 assumption stated explicitly in §7 and §5 S8.1)
- [x] Security contracts: N/A declared with reason
- [x] All IDs resolve — G1–G4, CT1–CT5, S8.0–S8.5, P1–P10, Q32–Q34, RN1–RN9, RK1–RK5

### 11.4 READY gate

- [x] Preflight log present and non-trivial (measured probes, not "skipped")
- [x] Depth P2 declared, matches scope
- [x] Executive intent, non-goals, current/target state concrete
- [x] Contract subtypes present or explicitly N/A
- [x] Path + matrix gates satisfied
- [x] Every step file:symbol specific with exit criteria
- [x] Verification plan + LIVE-PATH PROOF present
- [x] Anti-theater checklist holds
- [x] Research notes fully dispositioned (RN1–RN9)
- [x] **BLOCKING open-question set is EMPTY** — Q32 and Q34 resolved by the
      operator 2026-07-30; Q33/Q35 are non-blocking with recorded defaults
- [x] All IDs resolve

**→ Status: READY (v3).** Eight steps. **Execution order is now
load-bearing** — S8.2, S8.3 and S8.7 edit the same block (RK6):

```text
S8.0  re-verify anchors                     (read-only)
S8.1  record the Q32 decision               (no-op)
  ├─ S8.2  real duration_ms                 ─┐ same code block:
  ├─ S8.3  read-back consumer               ─┤ STRICTLY SEQUENTIAL
  └─ S8.7  fix stop_reason (RV4 defect)     ─┘
S8.6  terminal FAILED states                (parallel-safe: tests only)
S8.4  stdout contract                       (largest blast radius — full suite)
S8.5  targeted mutation                     (after the big chunk)
```

**S8.7 is the highest-ROI step in the plan** — it is the only one that fixes a
*wrong value in production data*, and it is a prerequisite for S9 computing an
honest success rate. If time is short, S8.3+S8.7 outrank S8.4.


---

## 11. Execution record — 2026-07-30

| Step | Verdict | Evidence |
|---|---|---|
| S8.0 | PASS | 11 anchors resolved; zero-production-consumer finding reproduced; probes matched (102 stdout bytes, `duration_ms: 0`) |
| S8.1 | PASS | Q32 decision recorded; I-38 closed by S8.4 |
| S8.2 | PASS | `duration_ms` measured 116–150 ms (was literal `0`) |
| S8.3 | PASS | `_read_back_terminal_state` added; `load_flow_state` gains its first production caller |
| S8.7 | PASS | **RV4 defect fixed** — BLOCKED run now records `workflow_failed`; all 4 status mappings verified |
| S8.8 | PASS | *(added mid-execution, operator-approved)* call-time projection path; split brain closed |
| S8.6 | PASS | 5 of 6 `_write_stage_failure_state` sites covered across linear/repair/adaptive |
| S8.4 | PASS | quiet-scoped stdout contract; console byte-identical |
| S8.5 | PASS | sweep 7/7 caught, 0 survived; gremlins 49/49 zapped, `70 passed` confirmed |

**Kill-checks — all executed and observed to bite, never assumed:**

| Kill-check | Effect |
|---|---|
| Revert `stop_reason` ternary | BLOCKED run reports `workflow_complete` again — the exact defect returns |
| Delete `write_flow_state` | Read-back returns `None`; status reads stale `EVALUATING` |
| Foreign `run_id` | Rejected, with a positive control proving the loader still works |
| Revert to import-time path constant | **9 of 16** tests fail |
| Neuter all 6 failure-state sites | 5 tests fail |
| Force status line to stdout | 2 quiet tests fail |
| Force status line to stderr | 2 **console** tests fail (inverse — pins the conditional) |
| Drop `output_mode` forwarding | Workflow quiet test fails |

**One pre-existing test intentionally revised.** `test_s7_cli_run_paths.py`
matrix-D asserted `stderr == ""` under quiet. S8.4 moves the status line there
by design, so the assertion was updated to pin what quiet actually guarantees:
a clean **stdout**, and no live renderer (`"[turn " not in stderr`). The durable
trace assertion is untouched. This is RK1 materialising exactly as predicted.

**Method note — a probe that lied.** During S8.6 a `trace`-based coverage probe
reported 1/6 failure sites hit, contradicting the artifacts. The probe was
wrong (module-attribute patching plus a reused workspace across runs); a
direct call-site spy with a fresh workspace per run showed 5/6. *A measurement
tool needs its own positive control before its output is trusted* — the same
lesson as S7.C3/C4, arrived at from a new direction.

### Deferred (unchanged by this slice)

`Q33` (no `route` column — S9 owns that schema), `Q35a` (exit code on
rejection stays `0`; **revisit as Q35b in S9** now that `stop_reason` is
honest), BACKLOG `I-36`/`I-37`/`I-39`.
