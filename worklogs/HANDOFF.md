# HANDOFF.md — next agent/session

> Read [`knowledge/llms.txt`](../knowledge/llms.txt) §MUST READ FIRST.
> This file records the verified state and the next bounded action.

## Current state

**As of:** 2026-07-27 — S2 SessionManager/session-authority wiring complete for
local verification, with S4/S5 follow-up explicitly pending.

Base:

```text
HEAD        = 3668e758c1522645a1bfb70787ebf53f7ef170a7
origin/main = 3668e758c1522645a1bfb70787ebf53f7ef170a7
branch      = fa/20260725-session-authority-debug-wiring
```

No commit, push, image build, or deployment was performed.

## Verified evidence

### Candidate provenance

- Candidate runtime patch remains unapproved and external:
  `/home/user/backups/First-Agent-dev-20260725Tcandidate-diff-from-3668e758c1522645a1bfb70787ebf53f7ef170a7.patch`.
- Candidate patch size: `23987` bytes.
- Candidate patch SHA-256:
  `ad975712a055697b6089c32f4e72c5f3258d460e98a40a40dd4b4aefff5f9070`.
- Disposable `git apply --check` against the base: PASS.
- Fresh PR bundle patch from `origin/main`:
  `/home/user/backups/First-Agent-dev-20260727T-s2-implementation-s3-ready-from-3668e758c1522645a1bfb70787ebf53f7ef170a7.patch`.
  Exact size/SHA-256 and disposable apply evidence are in the matching
  `.meta.txt` file; the latest `git apply --check` and apply both passed.

### S2 plan review and implementation

- Parent workplan:
  `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`
  Revision v9.
- S2 subplan:
  `worklogs/implementation-plans/PLAN-cli-trace-S2-session-manager-and-authority.md`
  Revision v3.
- S2 verification report:
  `worklogs/implementation-plans/cli-trace-S2-verification-report.md`.
- S2 plan review corrected authority/bootstrap ordering, workflow identity,
  stats read-only discovery, workspace ownership/provisioning, and entrypoint
  ownership before runtime edits.
- `python scripts/check_doc_links.py`: PASS (`172` markdown files).

### Runtime behavior now implemented

- Candidate A session namespace:

  ```text
  ~/.fa/sessions/<session-id>/manifest.json
  ~/.fa/sessions/<session-id>/session.db
  ~/.fa/session-log/<run-id>/
  ```

- `SessionManager` owns session/manifest/DB/run lifecycle for production
  `fa run` and `fa workflow`.
- `--session-id` exists on `fa run` and `fa workflow`.
- `--workspace` preserves `None` versus explicit path on those roots.
- Each top-level invocation receives a fresh run ID; explicit reuse is rejected.
- One workflow invocation uses one run ID shared by its internal stages in S2.
- EventLog is run-scoped over an injected session DB.
- Blackboard is session-scoped over the same injected DB; injected authority
  read failures do not fall back to JSONL.
- `fa stats` current path is DB-only and uses `open_existing()`; old JSONL/old
  per-run DB paths return `legacy_trace_unsupported` without DB creation/import.
- `FA_SESSION_ID` and `FA_RUN_ID` are separate in `scripts/fa-entrypoint.sh`.
- Failed clone/checkout fails closed; auto-run managed workspace provisioning
  delegates manifest/DB creation to `SessionManager`.

### Test/static results

```text
Targeted S2 gate: 127 passed, 1 warning
Full suite:       2014 passed, 15 skipped, 1 warning
Changed-file Ruff format/check: PASS
Strict mypy on 8 changed source/test modules: PASS
py_compile: PASS
bash -n scripts/fa-entrypoint.sh: PASS
git diff --check: PASS
Producer/consumer contract: PASS
LogKind contract: PASS
No mocked dataclasses contract: PASS
Doc links: PASS
```

Repository-wide Ruff format/check remains non-green because of pre-existing
documentation formatting findings and pre-existing unused `noqa` findings in
`src/fa/inner_loop/hooks/base.py`; S2 used the changed-file static gate and did
not mass-edit unrelated documentation/source.

### Verification hygiene

- Pre-final snapshot:
  `/tmp/first-agent-s2-prefinal3-20260727.txt`.
- Post-final snapshot:
  `/tmp/first-agent-s2-postfinal3-20260727.txt`.
- Pre/post status entries, tracked-mode hash, and new-file hashes are identical.
- Full pytest introduced no new worktree mutation.
- No raw `llm_bodies.jsonl` was printed.

### Kill-checks

Disposable source mutations were required to fail:

```text
remove _cmd_run SessionManager producer        → lifecycle C2 test FAIL
remove EventLog run_id scope                    → run-isolation test FAIL
replace stats DB reader with legacy JSONL path  → current-stats C2 test FAIL
```

All three kill-checks passed as negative proofs.

## Changed S2 files

Runtime/source:

```text
scripts/fa-entrypoint.sh
src/fa/blackboard/blackboard.py
src/fa/cli.py
src/fa/inner_loop/session_db.py
src/fa/inner_loop/state.py
src/fa/session/__init__.py       (NEW)
src/fa/session/manager.py        (NEW)
src/fa/stats.py
```

Tests:

```text
tests/test_cli.py
tests/test_cli_ergonomics.py
tests/test_fa_entrypoint.py
tests/test_session_db_authority.py
tests/test_session_lifecycle.py  (NEW)
tests/test_stats.py
```

Existing candidate changes in `knowledge/llms.txt`, `tests/test_observability_fix_p2.py`,
`tests/test_observability_redaction.py`, and prior `HANDOFF.md` remain part of
the pre-existing uncommitted baseline; they were not silently treated as S2
implementation.

## Deferred / known follow-up

- S5 owns final concurrent event identity allocation, uniqueness, and the
  `COUNT(*) + 1` replacement proof (`V1`/`V2`).
- S5 owns symmetric Blackboard mutation conflict/fail-closed write behavior
  (`V15`/`V17`) and remaining authority failure matrix.
- Later subagent slice owns Q11-B two-root artifact-only enforcement (`V24`/`V25`).
- Live EventBus redaction (`V23`) remains explicitly deferred.
- Legacy reader/migration is not implemented by policy.
- Direct-container production verification/rebuild/proxy evidence is still
  pending S4/S7. Local green tests do not equal deployment proof.
- An uncommitted source clone omits untracked files by definition. The S2
  entrypoint handoff probe was therefore repeated with a disposable source
  revision containing the new files; the corrected handoff passed.

## S3 liveness/contract audit — EXECUTED 2026-07-27

Report: `worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md`

Audited subject commit `811502ee884aed556e075986ca4a1a09347848b6`
(branch `formal-substrate++`). Audit-only: no `src/`, `tests/`, or `scripts/`
file was modified; all mutation probes ran in disposable `/tmp/fa-s3/` copies.
C0 candidate comparator recorded UNAVAILABLE (host-local patch).

Verdict: **PASS**. All five Step-S3 exit criteria met.

Must-read consequences for the next session:

- **Do not cite `check_log_kind_contract.py` PASS as evidence.** Kill-check K2
  deleted the real `subagent_spawn_done` producer and the checker output was
  byte-identical, still PASS. `check_producer_consumer_contract.py` also reports
  `C1 tested: 20` against 16 EventType literals (five non-EventType strings).
  Checker repair is a separate approved subplan, not part of S5.
- The C1 test layer *is* trustworthy: both K1 and K2 failed the named C1 tests.
- Three `CONSOLE_MIRROR_KINDS` producer sites are durable-only
  (`loop.py:288`, `:420`, `:481`); `loop.py` has no output channel at all.
  Kill-check K4 proved this behaviourally: a real `run_session` with an attached
  bus wrote a durable `run_stopped` row and emitted **zero** console events.
  A 4th suspected site (`state.py:515` `tool_call`) was **cleared** on
  call-graph review — it pairs with `coder_loop.py:1557` at the `drive_session`
  root. Do not "fix" it.
- Fixed and closed by S2, confirmed by probe: V3, V4, V5, V7, V13, V16, V26 and
  V2 on the durable path. Do not re-open these without source evidence.
- Full gate: 2014 passed, 15 skipped, zero tracked-file delta.
- V12 reproduces only on the failure path: `tests/test_hygiene_hooks_install.py:229`
  chmods tracked source and restores it without `try/finally`.

Second-pass re-verification (§12b of the report) added S3-F10..S3-F14 and
corrected three findings:

- **S3-F10 (P0)** — one git commit disables Blackboard conflict detection against
  every pre-commit entry (`_should_check_conflict` skips differing `base_commit`).
- **S3-F13 (P0)** — V3 is not fully closed: `tools/observability.py:42` builds an
  EventLog with no `session_db`, so an agent-facing tool reads the JSONL mirror
  and can report events absent from the authority.
- **S3-F14 (P0)** — CHECK 3 stays green after every assertion in
  `test_event_type_c1_producers.py` is neutralised.
- **S3-F11/F12 (P1)** — bare `print()` to stdout in `worktree_manager.py:235`
  corrupts `fa run > result.txt`; `ConsoleRenderer.on_event` silently drops
  unknown event types.
- **V1 downgraded to LATENT** — the per-instance lock holds; duplicates need a
  stale long-lived handle, and `cli.py:1742` constructs after the stage loop.
- **V12 blast radius upgraded** — the test chmods the *pip-installed* package
  path, so a failure dirties the installed repo, not the copy under test.
- **S3-F2 downgraded to cosmetic** — the stray strings never reach CHECK 3 logic.

Load-bearing gate finding: on the K2 killed tree, all 4 checker tests and
`test_s4_log_kind.py` passed; only 2 C1 wiring tests failed. The C1 wiring tests
are the only real liveness gate.

New blocking question:

- **Q12 — should `src/fa/inner_loop/loop.py` have a live output channel?**
  Answer before any S6 mirror work. S3 stopped rather than choosing the policy.

## S3.5 gap closure — LANDED 2026-07-27

Six CI/audit findings closed before S4. All verified on a green full gate.

| Fix | Finding | Mechanism |
|---|---|---|
| CI mount topology | stale post-S2 contract | `advisory.yml` now passes `FA_SESSION_ID=ci-smoke` + `FA_RUN_ID=ci-run-1` and asserts both. **Plus a new negative case**: a run-id-only container must NOT create `/sessions/<run-id>` — this is the only thing that would detect a V26 regression. |
| authoring-check HARD-BLOCK ×3 | public-looking names | `SCHEMA_META_KEY`/`SESSION_ID_META_KEY`/`SESSION_SCHEMA_VERSION` → `_`-prefixed. Zero external consumers (verified). Persisted string *values* unchanged, so existing DBs stay readable. |
| pylint R0801 #1 | duplicate `_payload_matches_key` | Extracted to `fa.inner_loop._sqlite_common.payload_matches_key` (same module that already exists for this exact R0801 pattern). |
| pylint R0801 #2 | duplicate TraceEvent projection | New `TraceEvent.from_row()` classmethod. The two call sites' differing fallbacks (`""` vs queried run/session id) are parameters, so semantics are preserved exactly. |
| S3-F11 | stdout pollution | `worktree_manager.py:235` bare `print()` → `logger.warning`. Was writing 211 bytes into `fa run > result.txt`. Verified 0 stdout bytes after. |
| S3-F8 / V12 | hygiene leak escaping the checkout | `test_hygiene_hooks_install.py` now chmods a `tmp_path` **copy**, not `Path(install_mod.__file__)` (the pip-installed package). Re-ran the negative fixture: mode stayed 755 through a forced mid-test failure. |
| V11 | `NO_COLOR` process-global mutation | Removed entirely. `ConsoleRenderer(no_color=...)` is now an explicit parameter; env var still honoured for the no-color.org contract. Better than the try/finally restore I first wrote — that broke two `inspect.getsource` tests. |

Deferred by decision: Codacy cyclomatic complexity (`_discover_stats_sources` 30,
`_parse_events` 59). These need structural refactor and would change parsing
semantics; not safe as "minor cleanup".

Gate after all fixes:

```text
pytest            2014 passed, 15 skipped
mypy --strict     Success: 137 source files
pylint            10.00/10 (duplicate-code + cyclic-import gate)
ruff check        clean (2 pre-existing RUF100 in untouched hooks/base.py, newer-ruff artifact)
ruff format       297 files already formatted
authoring-check   0 diagnostics, exit 0
producer/consumer + logkind + no-mocked-dataclasses + dependency-contract: PASS
check_doc_links   177 files OK
git diff --check  PASS
```

`TEST-EDITS:` one test modified — `tests/test_hygiene_hooks_install.py`
(S3-F8). Rationale: the test itself was the defect; it mutated tracked/installed
source outside `tmp_path`. Assertion and coverage are unchanged.

## S4 subplan — READY for operator execution

`worklogs/implementation-plans/PLAN-cli-trace-S4-direct-container-baseline.md`

Eight steps (S4.0–S4.7), copy-pasteable `docker compose exec` blocks, each with
an explicit expectation. S4.3 carries the decision-relevant number: the live
`duplicate event_id` count. S3 proved V1 **latent** locally; S4 determines
whether it is live in production, which sets its rank in S5.

Body-file safety is structural in the plan: counts and sizes only, never `cat`.

## S4 direct-container baseline — EXECUTED 2026-07-28

Report: `worklogs/implementation-plans/cli-trace-S4-verification-report.md`

Verdict: **PASS WITH FINDINGS.** All 9 steps ran on the live deployment; zero
fixes applied during S4 per its non-goals.

Verified on the deployed path (previously L2/local only): session/run identity
split (V26 stays fixed), authority == mirror (7 = 7, 14 total), P33 multi-run
on one authority, debug-body gate both states, secret isolation two-sided (no
provider key in the agent container **and** a live 200 through the proxy),
derived-consumer agreement across three surfaces, deterministic root clean,
read-only rootfs intact.

### Must-read for the next session

- **V1 is reclassified: latent → REACHABLE IN PRODUCTION.** The real root
  (`SessionManager.create_or_attach_session → begin_run → EventLog`) produced
  **6 duplicate event ids** with two concurrent runs on one session. Neither
  `reserve_run_binding` (unique run-ids only) nor any lock prevents it.
- **Do not cite S4.4's `DUPLICATE event_id: 0` as V1 evidence.** Those two runs
  were sequential processes, so 0 was structurally guaranteed. A concurrency
  test without a synchronisation barrier passes by accident.
- S3-F10 and S3-F13 must be named explicitly in the S5 file list; the parent
  plan's S5 scope predates both findings.

### Pre-S5 hygiene — LANDED

- **S4-F2** `.gitignore`: `.fa/` → `.fa/*` plus `!.fa/host-bootstrap.json`.
  `!.fa/` was cancelling `.fa/` outright — git cannot re-include a path inside
  an excluded directory — so every runtime artifact showed as untracked after
  each run. This was the real cause of the recurring post-update noise.
- **S4-F3** `git update-index --chmod=+x` on the 12 `scripts/` files. Index had
  them `100644` while `fa-update.sh:872` chmods them `+x` every run, producing
  permanent mode drift. `tests/test_deploy_scripts.py:195` already *required*
  the executable bit, so the index was the wrong side. One previously-skipped
  test now runs (2015 passed, was 2014/15 skipped).

**S4-F1** (`inner-loop-smoke` creates a second session-less `session.db` at
`cli.py:874`) stays with **S6** — bundling it would dilute a P0 authority slice.

Gate after hygiene fixes: pytest **2015 passed, 14 skipped** · mypy strict clean
(137 files) · pylint 10.00/10 · ruff format clean · doc-links 178 OK.

### Q12 evidence from S4.7

The deterministic root narrates the happy path via `print()` in
`_cmd_inner_loop_smoke`, **not** EventBus — `run_session` emitted nothing,
confirming S3-F9 live. The gap is therefore **stop-path only**. Supports
option (b) now + (c) in S6; does not support (a).

## Q12 — RESOLVED 2026-07-28

**Answer: option (b) — `run_session` is intentionally console-silent; the
mirror contract binds `drive_session` only.** Recorded as a scope exemption in
`src/fa/output.py` §Console-mirror kinds.

Rationale from measurement, not preference: S3 kill-check K4 (bus attached,
zero events emitted) plus S4.7 on the deployed container, where the smoke path
narrated itself through `print()` in `_cmd_inner_loop_smoke` rather than the
EventBus. Under `fa run` the operator always gets the mirror because
`drive_session` wraps execution; the gap is **stop-path only** on bare
`run_session`. Wiring an EventBus into `loop.py` (option a) was rejected — it
would add a display dependency to the one pure path in the harness.

Whether `drive_session` should emit on behalf of `run_session` after it returns
(option c, ~10 lines) stays open for **S6**. The exemption comment says so
explicitly so nobody closes it the wrong way.

## S5 subplan — READY (v2, review passed)

`worklogs/implementation-plans/PLAN-cli-trace-S5-authority-correctness.md`

Scope (all in one slice per operator decision, landed **incrementally** — each
step behind its own tests before the next starts):

```text
S5.1  V1      event identity: DB-serialized allocation + UNIQUE(event_id)
S5.2  V2res   kind_counts must not lead the commit (consumer: coder_loop.py:573)
S5.3  V6      Blackboard INSERT OR REPLACE -> explicit semantics
      S3-F10  a commit must not disable conflict detection
S5.4  V15/V17 edit_file/write_file share one pre-write contract
S5.5  S3-F13  agent observability tools read the authority, not the mirror
S5.6  V18-V22, V24, V25   isolation boundary denies instead of degrading
```

**The V1 test needs a barrier.** Two concurrent processes started naturally gave
0 duplicates — startup jitter serialized them. Only a synchronisation barrier
reproduces the 6-duplicate result. A concurrency test without one is vacuous.

**Status: GO.** Three review rounds. All four open questions resolved:
**Q6** keep `ev-NNNNNN`; **Q13** Blackboard is append-only (ADR-16 I-6.2/I-6.3);
**Q14** fail closed on pre-existing duplicates, operator prunes state and
re-runs S4 clean; **Q11-B** Option A — artifact dir at
`<session_workspace>/.fa/subagents/<task_id>/`, one value shared by gate and
executor (plan §3.2).

Round 3 caught the most dangerous defect: the v2 mechanism ("serialized
transaction under the existing `_write_lock`") is **process-local**, and the
production shape is separate processes. Measured over 5 trials, 6 procs × 5
appends: app-lock **lost 6/150 events**; `BEGIN IMMEDIATE` lost **0/150**. All
six write paths in `session_db.py` currently use bare `with conn:` (DEFERRED),
the documented SQLite footgun where a read→write upgrade returns `SQLITE_BUSY`
*without honouring `busy_timeout`*. Plan now mandates `BEGIN IMMEDIATE` plus
bounded retry, and adds a **mandatory multiprocess** no-loss test (S5-P22) —
a threads-only test passes the wrong design.

Rounds 1–2 closed **11 parent-trajectory gaps**, **3 SQLite logic errors**, and
**4 missing §13 protocol sections**. Two errors were
material: `UNIQUE(event_id)` would have rejected valid rows in other sessions
(correct shape is `UNIQUE(session_id, event_id)`), and a DDL-only change is a
**silent no-op on existing databases** while indexing a DB that already holds V1
duplicates raises `IntegrityError` — i.e. the naive fix would either do nothing
or brick a session. Both proven with live SQLite; see plan §3.1.

No open question blocks execution. **Q15** is reserved as the only escalation,
scoped to S5.6 if gate and executor cannot share one write root without a wider
refactor. Execution begins at **Step S5.0** (preflight, no production edits):
re-verify citations, audit for pre-existing duplicate event ids, confirm the
clean-state precondition.

## Next bounded action

1. Review and merge the S4 report + pre-S5 hygiene PR.
2. Author the **S5** subplan from S3+S4 evidence, scoped to:
   V1 atomic event-id allocation (now production-reachable — the barrier-based
   concurrency repro is the required kill-check), V2 residual `kind_counts`
   drift, V15/V17 mutation-path conflict symmetry, **S3-F10** (one commit
   disables Blackboard conflict detection), **S3-F13** (agent-facing
   observability tool reads the unauthoritative mirror), and the
   worktree/subagent fail-open cluster (V18, V19, V21, V22, V24, V25).
3. Explicit S5 non-goals: checker edits, `loop.py` output channel (pending
   Q12), V23, CLI extraction, Codacy complexity refactor, S4-F1 (S6).
4. Then S6/S7 per the parent plan.
4. Before deployment, use direct invocation only:

   ```bash
   docker compose -f /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml exec -T ...
   ```

5. Inspect only safe metadata/counts (`ls -lh`, `wc -l`, SQLite counts/metadata)
   and never print raw `llm_bodies.jsonl`.

## Session close protocol

- Load `knowledge/skills/doc-maintenance/SKILL.md`.
- Run `python scripts/check_doc_links.py`.
- Preserve the exact base SHA and candidate patch SHA/size.
- Keep the pre-existing candidate diff distinct from later approved slices.
