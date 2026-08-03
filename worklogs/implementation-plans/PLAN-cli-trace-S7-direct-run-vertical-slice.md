# PLAN — S7: close the direct `fa run` vertical slice

- **Status:** **COMPLETE** (2026-07-30). S7.0–S7.6 implemented and verified
  locally (§11); the **container half S7.C0–S7.C7 was executed by the operator
  on deployment `6262e7d`** — all steps MATCH except S7.C5, whose *trace*
  contract matched while its *stdout* contract did not (→ Q31 / I-38). The
  parent's §Do-not ("do not mark the slice L3 based on local fake transport
  alone") is therefore satisfied with real-deployment evidence. Evidence:
  [`PLAN-cli-trace-S7-container-verification.md`](./PLAN-cli-trace-S7-container-verification.md) §3.
  Q27 resolved (operator runs the container half); Q28 resolved (option b).
  **Q29 and Q31 raised, both non-blocking and deferred by operator decision to
  after the main workplan.** Container findings: **I-36, I-37, I-38, I-39** —
  recorded, zero fixes applied, per the sheet's stop rule.
- **Date:** 2026-07-29
- **Parent:** [`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md) §Step S7 (line 1703)
- **Depends-on:** S5 (`57f574a`) and S6 (`6bdd85f`) — both complete
- **Traces-to:** G4, G5, CT1, CT2, CT3, CT5, CT7, CT8
- **Predecessors:** [`PLAN-cli-trace-S6-observability-contracts.md`](./PLAN-cli-trace-S6-observability-contracts.md), [`PLAN-cli-trace-S6.6-mutation-gap-closure.md`](./PLAN-cli-trace-S6.6-mutation-gap-closure.md)

---

## 1. PREFLIGHT LOG (mandatory, plan-authoring §2)

**Roots checked**

* `src/fa/cli.py:1784` `_cmd_run` — the CLI composition root S7 targets.
* `src/fa/cli.py:2865` `main` — argv dispatch.
* `src/fa/inner_loop/coder_loop.py:341` `drive_session` — session root.
* `src/fa/cli.py:867` `_cmd_inner_loop_smoke` — the S4-F1 site.

**Greps run → findings**

| Pattern | Finding |
|---|---|
| `def _cmd_run` | `cli.py:1784`, carries `# noqa: C901` — verified, not new |
| `--session-id` / `--run-id` / `--detail` | `cli.py:466,478,496` (run); `:541,546` (workflow); `:717,723` (stats) |
| `output_mode` / `detail` / `no_color` defaults | `cli.py:1176-1178` (`console`, `standard`, `False`) |
| `FA_DEBUG_LLM_BODIES` | **only** `providers/debug_bodies.py:58,101`; **no hit in `cli.py`** — the env gate is provider-side, not CLI-side |
| `logical_call_id` | `providers/chain.py:302,306`; `coder_loop.py:1154,1204,1217,1287` — join key exists |
| `tool_call_id` | `state.py:109,149,245,266` — on `TraceEvent`; join key exists |
| `os.environ[` / `setdefault` / `basicConfig` in `cli.py` | **no hits** — no process-global env mutation on the run path |
| `set_current_session` | `coder_loop.py:363` with `reset_current_session` in a `finally` at `:384` |
| `inner-loop-smoke` | `cli.py:391-415` parser, `:867` handler, `:874` `EventLog(log_path)` |

**Gold patterns mirrored**

* `tests/test_cli.py` (30 tests) — `_cmd_run` invocation style, `capsys`, tmp HOME.
* `tests/test_session_manifest_guards.py` — the S6.6a C3 shape and the
  forcing-function guard.
* `tests/fixtures/session_wiring.py` — `make_session_state(..., redactor=)`,
  `make_mock_chain`, `mock_tool_call_response`.

**Conflicts / invariants found**

* **ADR-12** — body capture and redaction; S7 must assert *counts and
  metadata*, never raw body contents.
* **Q12 (S5)** — `loop.py` must hold no `EventBus`; S7 must not "fix" P15 by
  wiring one.
* **Parent §Do-not** — do not call the wrapper (`scripts/fa`) to claim core CLI
  proof; do not inspect only stdout; do not mark L3 on fake transport alone.

**As-is liveness** (from S3 audit lines 618-622, re-read this session)

| Path | S3 verdict |
|---|---|
| P1 fresh run | PARTIAL (local only) |
| P2 resume | PARTIAL |
| P3 generated run-id | PARTIAL |
| P4 debug disabled | PARTIAL |
| P5 debug enabled | PARTIAL — deployment pending |

**Unresolved → promoted to Q#:** Q27 (container half), Q28 (S4-F1 fix shape).

---

## 2. Fold-in verdicts (operator instruction: "fold S4-F1 and S4-F3 into S7")

Per the central law *notes are inputs, not authority*, both were re-verified
against the tree rather than copied in.

### S4-F1 — **ACCEPT**, folded in as S7.5

Reproduced this session, unchanged:

```text
second session.db created: True
injected session_db?     : False
session_id on the DB     : ''
```

`cli.py:874` calls `EventLog(log_path)` with no `session_db=`, so
`state.py.__post_init__` constructs `SessionDatabase(<workspace>/.fa/session.db)`
with an **empty `session_id`** — a second authority, disconnected from
`~/.fa/sessions/<sid>/session.db`, on the non-injected mirror-fallback path.
Real, live, and in scope. **Fix shape is a policy choice → Q28.**

### S4-F3 — **REJECT: already fixed; the report is stale**

The report says the 12 scripts are `100644` in the index, so every
`fa-update.sh:872` run produces a permanent mode diff. **Measured now:**

```text
scripts/backup-fa.sh    index=100755 worktree=755
... all 12 ...          index=100755 worktree=755
```

`git show --stat 57f574a -- scripts/` confirms **exactly those 12 files,
mode-only, 0 insertions** — S5 landed `git update-index --chmod=+x`, which is
precisely the fix S4-F3 proposed. `git status` is clean.

The recurring dirt I kept clearing this session was **sandbox filesystem
drift** (a fresh container re-materialising modes), not this bug — a different
cause with the same symptom, which is exactly why the report needed
re-verification instead of trust.

**Action:** no code change. S7 marks S4-F3 CLOSED in the S4 report with the
evidence above (doc-only). Folding a fixed bug in as work would be theater.

---

## 3. EXECUTIVE INTENT

Raise the direct `fa run` vertical slice from L2 to L3 across paths P1–P15, so
that the shipped CLI — not a library-level harness — is proven to produce the
durable and observable state the substrate promises.

S5 gave the slice a trustworthy authority; S6 gave it trustworthy signals.
Neither proved the **operator-facing command** composes them correctly. S3
still records P1–P5 as PARTIAL, and the reason is uniform: coverage exists at
the library seam, and `_cmd_run`'s own composition is asserted mostly by exit
code.

S7 closes that at the CLI root, adds the flag matrix rows the parent deferred
here (A–D, P-openai), pins the correlation joins that make a trace reconstructible,
proves command-local state does not leak between invocations in one process,
and folds in S4-F1 so no run leaves a stray session-less authority on disk.

**Non-goals.** No CLI extraction (that is S10). No workflow surface (S8). No
stats projections (S9). No new EventTypes. No wiring a bus into `loop.py`.

---

## 4. Contracts and gap IDs

| ID | Contract | Source |
|---|---|---|
| CT1 | CLI is the source of truth for run composition | parent §Step S7 |
| CT2 | session/run identity is stable and correlatable | parent |
| CT3 | observable signals are two-sided | parent, S6 |
| CT5 | body capture is opt-in and redacted | ADR-12 |
| CT7 | run provenance/trace-health is recordable without exposing bodies | parent |
| CT8 | deployment evidence matches source | parent |
| S4-F1 | `inner-loop-smoke` creates a session-less second `session.db` | S4 report §S4-F1 |
| S7-F1 (new) | S4-F3 is closed; the report is stale | this plan §2 |

---

## 5. Path matrix (P1–P15 + flag matrix)

Every row names the test class, the ranked oracle, and the kill-check target.
`NEW` marks a test that does not exist yet.

| P# | Path | Root | Class | Oracle | Kill-check target |
|---|---|---|---|---|---|
| P1 | fresh single-role run | `_cmd_run` | C2 | DB rows + exit code | `cli.py` EventLog wiring |
| P2 | resume w/ explicit run-id | `_cmd_run` | C2 | manifest + authority reuse | `manager.begin_run` |
| P3 | generated run-id | `_cmd_run` | C2 | run dir + id pattern | run-id generator |
| P4 | debug disabled | `_cmd_run` | C2 | **absence** of body file | `debug_bodies:101` gate |
| P5 | debug enabled | `_cmd_run` | C3 | body count only, never content | `debug_bodies` writer |
| P6 | provider success | `ProviderChain.request` | C1 | response + `call_count` | chain dispatch |
| P7 | transient fallback | `ProviderChain.request` | C1 | attempts + cooldown | fallback branch |
| P8 | auth failure | `ProviderChain.request` | C1 | chain behaviour + exit | auth branch |
| P9 | request-shape fast-fail | `ProviderChain.request` | C1 | **no** sibling retry | fast-fail branch |
| P10 | max-turn stop | `drive_session` | C1/C2 | stop reason | turn cap |
| P11 | hook deny before mutation | `_cmd_run` + hooks | C2 | DB row **and** stderr | `coder_loop` `hook_deny` emit |
| P12 | budget, no compaction | `drive_session` | C1 | `context_warn` row+event | budget gate |
| P13 | budget with compaction | `drive_session` | C1 | `compaction_*` | compaction gate |
| P14 | console output | `EventBus`+`ConsoleRenderer` | C1+C0 | rendered event set | producer emit |
| P15 | quiet output | `QuietRenderer` | C2 | stdout/stderr contract | renderer selection |

Flag matrix (parent §4.2, deferred to S7): **A** `FA_DEBUG_LLM_BODIES=0`+console+success ·
**B** `=1`+success · **C** `detail=debug` with env **disabled** (proves debug
rendering is not the body gate) · **D** `--output-mode quiet` · **P-openai**.

**Cell C is the sharp one.** Preflight found `FA_DEBUG_LLM_BODIES` has **zero
hits in `cli.py`** — the gate lives only at `providers/debug_bodies.py:58,101`.
So "debug rendering" and "body capture" are already independent in source; C
must prove that independence behaviourally, and it is the cell most likely to
regress if someone later "helpfully" couples `--detail debug` to body capture.

---

## 6. Steps

### S7.0 — Preflight audit of P1–P15 (no edits)

Measure, per path, what today's tests actually assert versus what the row
claims. S6 taught that a matrix row can be satisfied by a tautology, so each
row gets a recorded verdict: COVERED / PARTIAL / ABSENT / **THEATER**.

**Files:** none (report into §11 of this plan).
**Exit:** every P# has a verdict with file:line evidence.

### S7.1 — CLI composition: P1, P2, P3

**Current (source-verified).** `test_cli.py` has 30 tests;
`test_fa_run_session_manager_creates_and_attaches_with_fresh_run_ids:950` and
`test_fa_run_writes_events_jsonl:564` cover parts of P1/P3.
**Target.** Fresh run, explicit-run-id resume, and generated run-id each assert
the durable row count **and** the manifest/authority binding at the CLI root.
**Class:** C2. **Kill-check:** remove the `EventLog(...)` wiring in `_cmd_run`
→ the P1 test must fail.
**Files:** `tests/test_s7_cli_run_paths.py` (NEW).

### S7.2 — Flag matrix A–D and the debug/body independence proof

**Current.** `test_fa_run_debug_body_capture_follows_exact_env_gate:423` covers
the env gate; `detail`/`output_mode` are covered at 21/7 files but not as a
matrix on the run root.
**Target.** One test per cell, ids `A`/`B`/`C`/`D`.
**Failure behaviour.** Cell B asserts **counts and file existence only** — never
body content (ADR-12, CT5).
**Class:** C2 (A, C, D), C3 (B). **Kill-check:** invert the `debug_bodies:101`
gate → A and B must both fail.
**Files:** `tests/test_s7_cli_run_paths.py`.

### S7.3 — Correlation joins (parent Do #8)

**Current.** `run_id`, `event_id`, `tool_call_id`, `logical_call_id` all exist
in source (preflight). No test joins them end-to-end.
**Target.** From one run, join trace → tool call → provider attempt on those
keys; document any intentional non-join.
**Class:** C1. **Oracle:** event `kind`+fields (top of the ranked list).
**Files:** `tests/test_s7_correlation.py` (NEW).

### S7.4 — Invocation isolation (parent Do #9)

**Current.** `drive_session` resets its contextvar in a `finally`
(`coder_loop.py:363,384`). Preflight found **no** `os.environ` writes in
`cli.py`. But the S6.5 session measured real cross-test contamination via the
ambient contextvar, so absence-of-writes is not proof.
**Target.** Two `_cmd_run` invocations in one process, differing in
`--no-color` and HOME, with no state carried over.
**Class:** C2. **Negative proof:** delete the `reset_current_session` in the
`finally` → the second invocation must observe the first's session.
**Files:** `tests/test_s7_cli_run_paths.py`.

### S7.5 — S4-F1: the smoke command gets a labelled authority (Q28 = b)

**Idea implemented.** Make the smoke command's identity *symmetric and
self-labelled*, so its authority is guarded by construction instead of by an
empty-string sentinel that turns the guards off.

**Current behaviour (source-verified, reproduced).** `cli.py:875`
`EventLog(log_path)` → `state.py:176` builds
`SessionDatabase(<workspace>/.fa/session.db)` with `session_id == ""`.
`SessionState(run_id="cli-smoke")` at `:969` back-fills the run id but **not**
the session id, so events persist as `run_id='cli-smoke', session_id=''`, and
the DB accepts rows stamped for any other session (measured, §9 Q28).

**Target behaviour.** One clearly-named smoke authority at
`<workspace>/.fa/smoke/session.db` with `session_id="cli-smoke"`; no
`session.db` at `<workspace>/.fa/`; identity guards live.

**Exact mechanism.** In `_cmd_inner_loop_smoke`, construct the DB explicitly
and inject it, rather than letting `EventLog` default one into existence:

```python
smoke_root = workspace / ".fa" / "smoke"
session_db = SessionDatabase(smoke_root / "session.db", session_id=_SMOKE_SESSION_ID)
log = EventLog(
    smoke_root / "smoke-events.jsonl", run_id=_SMOKE_SESSION_ID, session_db=session_db, session_id=_SMOKE_SESSION_ID
)
```

`_SMOKE_SESSION_ID = "cli-smoke"` as a module constant so the id has one
definition, matching the existing `run_id` literal at `:970`.

**Production best practice.** Mirrors the composition root: `cli.py:1979`
already builds `EventLog(..., run_id=..., session_db=..., session_id=...)`
explicitly. The smoke path is the outlier, not the pattern.

**Failure behaviour.** An identity mismatch now raises at construction
(`state.py:178`) instead of silently writing unscoped rows — fail-closed, and
the failure is observable at the entry point rather than in the artifact.

**Tests-writing class:** C2 (the shipped command via argv) + C3 (the adversarial
foreign-row write).

**DoD / negative proof.**
1. after `fa inner-loop-smoke`, `<workspace>/.fa/session.db` does **not** exist;
2. `<workspace>/.fa/smoke/session.db` exists with `session_id == "cli-smoke"`;
3. persisted events carry a **non-empty** `session_id` equal to the run id;
4. the previously-accepted foreign-session row is now **rejected**.

**Producer kill-check target.** Remove `session_id=_SMOKE_SESSION_ID` from the
`SessionDatabase(...)` call → tests 2, 3 and 4 must fail. Removing only the
`session_db=` injection → test 1 must fail.

**Files:** `src/fa/cli.py`, `tests/test_s7_cli_run_paths.py`.
**Do-not:** do not make the smoke command require session provisioning (Q28a,
rejected); do not add a global constructor guard (Q29, separate slice).

### S7.6 — Mutation pass on the S7 blast radius

Per the operator's standing instruction, after the implementation chunk run a
**targeted mutation sweep** over `cli.py`'s run path plus any file S7 touched,
using both tools, because they cover different classes:

* `scripts/mutation_sweep.py` — statement deletion (guards);
* `pytest --gremlins --gremlin-targets=src/fa/cli.py` — expressions.

`cli.py` is the largest module in the repo at **475 gremlin mutants**
(`scripts/count_mutants.py`) and has **never** been mutation tested. Survivors
are triaged, not force-killed.

### S7.7 — Container half (parent Do #10) — operator-executed

Delivered as [`PLAN-cli-trace-S7-container-verification.md`](./PLAN-cli-trace-S7-container-verification.md)
(Q27 = a). Run it after deploying the S7 branch; return the §2 evidence blocks
and I will fold the verdicts into §11 of this plan.

Sequencing note: **S7.C6 must run after S7.5 is deployed**, since it is the
regression check for that fix. The other steps are order-independent after
S7.C0.

### S7.8 — Close S4-F3 in the S4 report (doc-only)

Record the §2 evidence: fixed by `57f574a`, index and worktree both `755`.

---

## 7. Definition of Done

Each item names the command that proves it. "No exception raised" is not proof.

- [x] every P1–P15 row has a named test and a verdict (S7.0)
- [x] flag matrix A–D each have a test id; cell C proves debug rendering is
      **not** the body gate
- [x] cell B asserts body **counts/metadata only** — a test that reads body
      content fails review even if green
- [x] correlation join reconstructs one run across all four keys
- [x] two in-process invocations do not leak; the negative proof bites
- [x] S4-F1 closed per Q28, with a kill-check
- [x] mutation sweep run over the S7 blast radius; survivors triaged in writing
- [x] `just check` green: pytest+cov ≥ 80, bare `mypy`, `pyrefly`, `ruff`,
      `pylint src/fa` 10.00/10, `deptry`, 9 contract scripts
- [x] patch verified by `git am` onto clean `57f574a` with the import root printed
- [ ] container sheet S7.C0–S7.C7 executed by the operator and its §2 evidence
      folded into §11; **S7 stays "complete-local / deployment-pending" until
      then** (parent §Do-not: no L3 claim on fake transport alone)

---

## 8. Risks

| # | Risk | Mitigation |
|---|---|---|
| S7-R1 | Testing the CLI by calling library functions, then claiming CLI proof | Every P-row test enters through `_cmd_run`/argv, never `drive_session` directly |
| S7-R2 | Cell B leaks secrets into the repo by asserting on body content | DoD forbids content assertions; assert counts + existence |
| S7-R3 | A matrix row satisfied by a tautology (the S6 D1 defect) | Every row carries a kill-check target; S7.6 mutation-verifies |
| S7-R4 | `_cmd_run` is `C901`-complex; tests may pin incidental behaviour | Oracles ranked: event kind+fields and exit codes, never stdout prose |
| S7-R5 | Fixing S4-F1 moves the smoke artifact path; an operator script may reference `<workspace>/.fa/session.db` | Q28(b) keeps the command provider-free and standalone; the move is announced in the PR note, and S7.C6 verifies both the old path's absence and the new path's presence on the live box |
| S7-R6 | Q28(b) re-arms identity guards that were dormant, so a previously-tolerated write now raises | That is the intent (fail-closed by construction), but it is a *behaviour* change on a debug command: S7.5's DoD includes the happy path, not only the rejection, so over-tightening is caught |

---

## 9. OPEN QUESTIONS — both block their steps

### Q27 — RESOLVED (operator, 2026-07-29): option (a) — operator runs the protocol

The operator will deploy the S7 branch to the server and execute the container
half. My part is delivered as a standalone execution sheet:
[`PLAN-cli-trace-S7-container-verification.md`](./PLAN-cli-trace-S7-container-verification.md),
mirroring the S4 subplan's format (preconditions → numbered steps with exact
commands and EXPECT lines → evidence template → DoD → rollback).

Eight steps, S7.C0–S7.C7, covering: deployment identity/drift, matrix cells
A/B/C/D on the real path, DB↔mirror count agreement, correlation joins on real
rows, the S4-F1 regression check, and post-run hygiene.

Two properties worth noting, both enforced by construction in the sheet:

* **No body content is ever printed** — only counts, byte sizes and identifiers
  (ADR-12, and the parent's §Do-not). Every probe was dry-run locally against a
  real `session.db` before shipping, so the SQL and column names are verified,
  not guessed.
* **S7.C6 discriminates.** Run against today's code it reports
  `PRESENT / ABSENT / session_id=('',)` — i.e. it *fails* before S7.5 lands and
  passes after. A regression check that cannot fail is theater; this one was
  checked against the unfixed tree.

S7 is still marked **complete-local / deployment-pending** until the sheet's
output comes back, per the parent's *"do not mark L3 on fake transport alone."*

### Q28 — RESOLVED (2026-07-29, after re-reading the module's purpose)

The operator asked for the fix to follow **what the module is for**, not the
symptom. Re-reading it changed the answer, and raised the severity.

**What the module is for** (`cli_help.py:268-270`): *"Exercise the M-1 registry
+ HookRegistry runtime **without an LLM provider**."* It is an offline,
provider-free smoke check, hidden from `--help` (`cli.py:1-7`). It is
**deliberately session-less** — and already labels its own run:
`SessionState(run_id="cli-smoke", ...)` at `cli.py:969-973`.

So option (a) — join the real session model — is **wrong for this module**. It
would make a provider-free smoke check depend on session provisioning and
defeat the command's purpose. Rejected on grounds of the module's contract, not
cost.

**The real defect, measured.** The asymmetry is the bug: `run_id` is labelled,
`session_id` is empty at every layer.

```text
after SessionState -> log.run_id      : 'cli-smoke'
after SessionState -> log.session_id  : ''
after SessionState -> db.session_id   : ''
event.run_id    : 'cli-smoke'
event.session_id: ''
```

And empty `session_id` is **not inert** — it is a sentinel that *disables*
identity enforcement. Every guard is written `if self.session_id and ...`
(`state.py:178,418,420`; `session_db.py:395,499`), and `event_count()`
(`session_db.py:357`) drops its `WHERE session_id = ?` scoping. Proven at
runtime:

```text
db.session_id: ''
foreign-session row ACCEPTED, event_id = ev-000001  <-- guard bypassed
```

A session-less DB accepts rows stamped for **any** session. So S4-F1 is not
merely "a stray file with a confusing name" — the artifact it creates is an
authority with its identity checks switched off. That is squarely against
**project-overview §1.2's "compliance-by-construction, failure-observable"**:
the safe state should be structural, not dependent on a caller remembering.

**Chosen: (b) — give the smoke command an explicit, self-labelled authority.**
Set a real `session_id` (`cli-smoke`) and put the DB under a clearly-named
`<workspace>/.fa/smoke/` directory. This:

* keeps the module provider-free and standalone — its stated purpose;
* makes `run_id`/`session_id` **symmetric**, which is what the substrate
  everywhere else assumes;
* re-arms the identity guards **by construction** — with a non-empty
  `session_id`, the `if self.session_id and ...` conditions become live, so the
  foreign-row write above starts being rejected without adding any new check;
* removes the misleading `<workspace>/.fa/session.db`, which an operator today
  cannot distinguish from the real authority.

**Rejected, with reasons rather than preference:**

* **(a) inject the real session authority** — contradicts the module's
  provider-free, session-less contract.
* **(c) global guard: refuse to build a `SessionDatabase` without a
  `session_id`** — this is the true class fix and is *tempting*, but the
  measured blast radius is three other session-less construction sites
  (`blackboard.py:207`, `state.py:176`, `observability.py:72`). Changing the
  meaning of the empty sentinel repo-wide is its own slice with its own
  mutation sweep, not a rider on S7. **Promoted to Q29** so it is tracked
  rather than lost.
* **(d) document and leave** — S4 already documented it; the artifact is an
  unguarded authority, not a cosmetic file.

### Q29 — should an empty `session_id` remain a legal "unscoped" mode? *(new, not blocking S7)*

Surfaced by the Q28 measurement. Today an empty `session_id` silently disables
write-identity enforcement and un-scopes `event_count()`. Three production
sites still construct DBs that way. Options: forbid it at construction; keep it
but make it explicit (`session_id="__unscoped__"`); or leave and document.
Needs its own slice — the change alters a repo-wide sentinel's meaning.

### Q31 — what does `--output-mode quiet` guarantee on stdout? *(new, raised by S7.C5, not blocking S7)*

S7.C5 measured **stdout 34 bytes** under `--output-mode quiet`, while
`QuietRenderer`'s docstring (`output.py:449`) says the mode guarantees
*"nothing on stdout — so `fa run --task ... > result.txt` stays parseable,
which is the reason the mode exists."*

The renderer is innocent: `on_event` is a `pass` and
`tests/test_s6_renderers.py:149` proves it for every `EventType`. The 34 bytes
come from two `print()` calls in `_cmd_run` that bypass the `EventBus`
entirely — `cli.py:2212` (status line, 29 B) and `cli.py:2214` (`final_text`,
5 B). No renderer-level test can observe them, which is why the local suite
passed while the live contract is violated.

This is a **policy fork, not a defect with an obvious fix** — per the stop
rule, promoted rather than decided. Options and recommendation are recorded in
**BACKLOG I-38**; the recommendation is (a) *quiet emits only `final_text` on
stdout, status line to stderr*, since it is the only option that makes the
existing docstring true. Resolve before S9 (stats/projections), which is the
next consumer of machine-parseable CLI output.

---

## 10. Self-check (plan-authoring §11)

- Every symbol cited carries file:line from preflight, or is marked NEW.
- Every P-row has class + oracle + kill-check target.
- No step marked done from "no exception".
- Two policy forks promoted to Q27/Q28 rather than silently decided.
- One instructed fold-in (S4-F3) **rejected with evidence** rather than
  performed as busywork.
- Non-goals stated; S8/S9/S10 scope explicitly excluded.

## 11. S7.0 audit results and execution record — 2026-07-29

### 11.1 S7.0 audit — measured, not assumed

Every row checked against the tree with file:line evidence before any edit.
**The audit shrank the slice**: most paths were already covered at the CLI root,
and duplicating them would have added a second oracle for one behaviour — the
reasoning that produced the S6 matrix-E tautology.

| Rows | Verdict | Evidence |
|---|---|---|
| P1, P2, P3 | **COVERED** | `test_cli.py:950` — manifest + run dirs + per-run DB rows through real `_cmd_run`; covers fresh, explicit attach, and generated run-id |
| P4, P5 / cells A, B | **COVERED** | `test_cli.py:423`, parametrised on `FA_DEBUG_LLM_BODIES`; asserts row counts and redaction, never raw body content |
| **cell C** | **COVERED** | same test — it already runs `detail="debug"` in *both* env states, so "debug rendering is not the body gate" is proven |
| P6–P9 | COVERED | `test_providers_chain.py`, `test_providers_errors.py` |
| P10, P11 | COVERED | `test_cli.py:587`, `:650` |
| P12, P13, P14 | COVERED | `test_compaction_c1_wiring.py`, S6 path-completeness + renderer suites |
| **P15 / cell D** | **ABSENT** | no test set `output_mode` at the CLI root |
| **Do #8** | **ABSENT** | no test joined `run_id`+`event_id`+`tool_call_id`+`logical_call_id` |
| **Do #9** | **ABSENT** | no test ran `_cmd_run` twice in one process |

Four items implemented; eleven correctly left alone.

### 11.2 What shipped

`tests/test_s7_cli_run_paths.py` (7) and `tests/test_s7_correlation.py` (5).
Production: **`src/fa/cli.py` only, 31 insertions** — the S7.5 fix.

* **P15 / D** — parametrised console-vs-quiet. Both cells assert the durable
  rows; only the stderr expectation differs. The risk is not "quiet prints too
  much" but a future implementation of quiet that stops *emitting* — console
  silence must never mean trace silence.
* **Do #8** — the join chain was measured on a real run before being asserted:
  `run_id` → rows → `content["logical_call_id"]` (identical on
  `provider_attempt` and `llm_call`) → `llm_bodies.jsonl`. The two documented
  non-joins are pinned as characterisation tests rather than prose.
* **Do #9** — two invocations in one process, differing in `--no-color`.
* **S7.5** — Q28(b) as specified.

### 11.3 Negative proof — six kill-checks, all bite

| # | Mutation | Result |
|---|---|---|
| KC1 | drop `session_db=` from the smoke `EventLog` | CAUGHT (1) |
| KC2 | drop `session_id=` from the smoke `SessionDatabase` | CAUGHT (1) |
| KC3 | quiet mode adds a `ConsoleRenderer` | CAUGHT (2) |
| KC4 | drop `logical_call_id` from `provider_attempt` | CAUGHT (3) |
| KC5 | blank `run_id` on `TraceEvent` | CAUGHT (11) |
| KC6 | re-introduce the contextvar leak (see 11.4) | CAUGHT (1) |

### 11.4 The Do #9 test found a real defect — in another test

`test_two_runs_in_one_process_do_not_leak_session_state` passed alone and
**failed in the full suite**. The leak was not in `_cmd_run`:
`test_event_type_c1_producers.py:291` called `set_current_session(state)` with
**no reset**, leaking an ambient `SessionState` into every subsequent test in
the process.

Fixed at the source — `token = set_current_session(...)` with
`reset_current_session(token)` in a `finally` — rather than by weakening the
S7 assertion. KC6 proves the leak cannot silently return.

This is the third time in this workstream that a contextvar leak has produced
an order-dependent result, and the second time it was found only because a new
test happened to run after the offender. Worth noting for S8: **a test that
passes alone and fails in the suite is evidence about the suite, not a reason
to relax the test.**

One judgement call: the first draft asserted that two `_cmd_run` calls create
two *sessions*. That failed with `workspace_already_owned` — S5's
reverse-ownership guard (`manager.py:196`) forbidding two sessions per
workspace. The test was wrong, not the product; rewritten to attach to the same
session, which is both the realistic repeat-invocation shape and the stronger
oracle (both runs land in one authority, so misattributed rows would show).

### 11.5 S7.6 mutation pass

`pytest --gremlins --gremlin-targets=src/fa/cli.py` → **479 gremlins, 479
zapped, 0 survived**, verified against `2227 passed`. `cli.py` is the largest
module in the repo and had **never** been mutation tested before this slice.

Complementary sweep (`scripts/mutation_sweep.py`, statement deletion) is the
six kill-checks in §11.3 — gremlins has no statement-deletion operator, so
neither result substitutes for the other.

### 11.6 Gate

pytest **2227 passed** / 14 skipped / 1 xfailed (baseline 2215 — **+12, zero
regressions**) · coverage **81.30 %** ≥ 80 · bare `mypy` clean (313 files) ·
`pyrefly` 0 errors · `ruff check`/`format` clean · `pylint src/fa` **10.00/10** ·
`deptry` clean · 9/9 contract scripts.

Ruff flagged `RUF002` (en-dash in a docstring range) — fixed by writing
`P1-P15`, not waived.

### 11.6a Scope deviation — three files beyond the declared `Files:` lists

The plan's per-step `Files:` directives named `src/fa/cli.py`,
`tests/test_s7_cli_run_paths.py` and `tests/test_s7_correlation.py`. Three more
were touched. Recorded here rather than left for a reviewer to find, because an
undeclared file in a diff is exactly what those directives exist to surface.

| File | Why | Verdict |
|---|---|---|
| `tests/test_event_type_c1_producers.py` | the contextvar leak S7 Do #9 uncovered (§11.4) | **in scope** — the S7 test cannot pass while it leaks, and weakening the S7 assertion instead would have been the wrong repair. Ignoring whitespace the change is **9 insertions / 3 deletions**: the `try/finally` and its reindent, nothing else |
| `.gitignore` | `.coverage.*` and `.gremlins_cache/` | **corrective, see below** |
| `.gremlins_cache/results.db` | untracked | **corrective, see below** |

**Found by this verification pass, not by the gate.** The first S7 commit
included two binary artifacts: a **15 MB** `.coverage.e2b_local.pid….` file and
a mutation-bloated `.gremlins_cache/results.db` (77 KB → 287 KB). `just check`
is blind to both — no linter or test objects to a committed artifact.

Root cause: `.gitignore` carried `.coverage`, but coverage.py's parallel mode
writes `.coverage.<host>.<pid>.<rand>`, which that entry does not match; and
`results.db` was **already tracked**, so a rule alone could not have stopped it.
Fixed by amending the commit, adding both patterns, and `git rm --cached`-ing
the cache. The plan's own workflow caused this — S7.6 mandates a gremlins run,
and gremlins rewrites its cache — so the ignore rules are part of closing S7,
not unrelated hygiene.

### 11.7 Status

**S7 is complete-local / deployment-pending.** The container half
([`PLAN-cli-trace-S7-container-verification.md`](./PLAN-cli-trace-S7-container-verification.md))
is ready for the operator; per the parent's §Do-not, S7 must not claim L3 on
fake transport alone. Verified locally that S7.C6 now reports the post-fix
state it predicts: old `.fa/session.db` **absent**, `.fa/smoke/session.db`
present, `session_id = cli-smoke`.
