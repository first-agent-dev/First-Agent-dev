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

## Next bounded action

1. Review and merge the S3 audit + S3.5 gap-closure PR.
2. Rebuild the deployment from the merged commit (S4 Step S4.0).
3. Execute `PLAN-cli-trace-S4-direct-container-baseline.md` on `fa@fa-HP` and
   post each step's output for joint debugging.
4. Then author the **S5** subplan from S3+S4 evidence: V1 atomic event-id
   allocation, V15/V17 + **S3-F10** (a commit disables conflict detection),
   **S3-F13** (observability tool reads the mirror), and the worktree/subagent
   fail-open cluster (V18, V19, V21, V22, V24, V25).
   Explicit S5 non-goals: checker edits, `loop.py` output channel (pending Q12),
   V23, CLI extraction, Codacy complexity refactor.
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
