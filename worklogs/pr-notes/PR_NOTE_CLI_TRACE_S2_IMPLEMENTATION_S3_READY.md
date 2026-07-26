# PR Note: CLI Trace Substrate — S2 Session Authority + S3 Audit Plan

**Intent:** IMPLEMENT + PLAN

**Goal lens:** Make session/run identity, SQLite authority, durable mirrors,
workflow artifacts, and liveness claims independently verifiable before the
next authority/EventBus hardening slice.

**Base revision:** `3668e758c1522645a1bfb70787ebf53f7ef170a7`

**Branch:** `fa/20260725-session-authority-debug-wiring`

**Date:** 2026-07-27

**Deployment:** none

**Commit/push:** none

## Summary

This PR bundle contains:

1. the parent CLI/trace substrate workplan;
2. the S1 session-lifecycle design/verification artifacts;
3. the implemented S2 SessionManager/session-authority wiring;
4. S2 verification evidence with targeted/full tests and producer kill-checks;
5. a fresh S3 liveness/contract-audit subplan;
6. an independent S3 plan-review report with a READY verdict.

S3 audit execution is **not** included in this PR change. The runtime/test
implementation boundary is paused after S2 as requested.

## Included planning artifacts

```text
worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md
  parent workplan, Revision v10

worklogs/implementation-plans/PLAN-cli-trace-S1-session-lifecycle.md
  S1 lifecycle/authority design subplan

worklogs/implementation-plans/cli-trace-S1-verification-report.md
  S1 source/design verification and accepted decisions

worklogs/implementation-plans/PLAN-cli-trace-S2-session-manager-and-authority.md
  S2 implementation subplan, Revision v3

worklogs/implementation-plans/cli-trace-S2-verification-report.md
  S2 implementation evidence, PASS WITH FOLLOW-UP

worklogs/implementation-plans/PLAN-cli-trace-S3-liveness-contract-audit.md
  S3 audit-only subplan, READY FOR AUDIT EXECUTION

worklogs/implementation-plans/cli-trace-S3-plan-review-report.md
  independent S3 plan review, PASS

worklogs/HANDOFF.md
knowledge/llms.txt
```

## Implemented S2 changes

### Session authority

- Added `src/fa/session/manager.py` and lazy package exports in
  `src/fa/session/__init__.py`.
- Added typed `SessionContext` and `RunContext` boundaries.
- Added Candidate A session namespace:

  ```text
  ~/.fa/sessions/<session-id>/manifest.json
  ~/.fa/sessions/<session-id>/session.db
  ~/.fa/session-log/<run-id>/
  ```

- Added session-bound SQLite schema/version/identity validation.
- Added transactional `run_binding:<run-id>` reservation.
- Added non-creating `SessionDatabase.open_existing()`.
- Added run/session scoped DB reads.
- Added reverse workspace ownership checks.
- Added provisioning/active manifest lifecycle.
- Added cleanup for partially created unowned workspaces.
- Added explicit rejection of legacy/incompatible session DB schemas on the
  production session-bound path.

### CLI/workflow

- Added `--session-id` to `fa run` and `fa workflow`.
- Changed those roots to preserve `--workspace=None` versus explicit workspace.
- Added default new-session behavior and explicit attach behavior.
- Every top-level invocation receives a fresh `run_id`.
- Explicit reused `run_id` is rejected before provider execution.
- One workflow invocation uses one run ID shared by its internal stages in S2.
- Session/run resolution occurs before transport wrapping and provider-chain
  construction.
- Public `--resume` without `--session-id` is rejected before provider calls.

### EventLog/Blackboard

- Production `fa run`/`fa workflow` inject the session DB and session identity.
- EventLog reads are filtered by `run_id` for injected current-format authority.
- Injected EventLog does not fall back to JSONL on empty/failing authority reads.
- Current trace rows carry `session_id`.
- SessionState rejects mismatched explicit log/DB/session identity.
- Injected Blackboard validates session identity and fails closed on authority
  read/query failures.
- Direct constructors remain compatibility-only for existing isolated tests and
  legacy helpers; they are not used by current `fa stats`.

### Stats

- Added current-format DB reducer `fa.stats.parse_session_db()`.
- Added Candidate A manifest/session DB discovery to `_cmd_stats`.
- Added `fa stats --session-id`.
- Added DB-bound run enumeration and filtering.
- Added deterministic `StatsSourceError` diagnostics.
- Old JSONL/old per-run DB artifacts return `legacy_trace_unsupported` and are
  not created/imported/migrated.

### Entrypoint

- Separated `FA_SESSION_ID` and `FA_RUN_ID`.
- Removed the old `FA_RUN_ID == SESSION_ID` assignment.
- Failed clone/checkout transitions to explicit invalid/standby state.
- Auto-run managed-session provisioning delegates to
  `python -m fa.session.manager provision`.
- The `fa.session` package uses lazy exports so module provisioning does not
  emit a runpy self-import warning.
- Host wrapper `scripts/fa` was not changed.

## Test and verification evidence

### Targeted S2 gate

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_session_lifecycle.py \
  tests/test_session_db_authority.py \
  tests/test_observability_fix_p2.py \
  tests/test_observability_runtime_authority.py \
  tests/test_inner_loop_audit_sink.py \
  tests/test_cli.py \
  tests/test_cli_ergonomics.py \
  tests/test_stats.py \
  tests/test_stats_global_wiring.py \
  tests/test_fa_entrypoint.py
```

Result:

```text
127 passed, 1 warning
```

### Full suite

```bash
PYTHONPATH=src python -m pytest -q
```

Result:

```text
2014 passed, 15 skipped, 1 warning
```

Skip classification:

```text
12 shellcheck unavailable
1 executable-bit filesystem limitation
2 deferred runtime-server extra
```

### Static and contract checks

```text
changed-file Ruff format/check: PASS
strict mypy, 8 changed source/test modules: PASS
py_compile: PASS
bash -n scripts/fa-entrypoint.sh: PASS
git diff --check: PASS
check_producer_consumer_contract.py: PASS
check_log_kind_contract.py: PASS
check_no_mocked_dataclasses.py: PASS
check_doc_links.py: PASS (175 markdown files after S3/PR-note artifacts)
```

Repository-wide Ruff remains non-green on pre-existing documentation formatting
and unrelated stale `noqa` findings in `src/fa/inner_loop/hooks/base.py`. Those
files were not mass-edited.

### Producer kill-checks

Disposable source mutations were required to fail:

```text
remove _cmd_run SessionManager producer
  → lifecycle C2 test failed as required

remove EventLog run_id query scoping
  → injected run-isolation test failed as required

replace stats DB reader with legacy events.jsonl reader
  → current DB stats test failed as required
```

Entrypoint failed-clone negative proof and partial workspace cleanup tests also
passed.

### Hygiene

Final full-gate snapshots:

```text
pre:  /tmp/first-agent-s2-prefinal3-20260727.txt
post: /tmp/first-agent-s2-postfinal3-20260727.txt
```

Pre/post status entries, tracked-mode hash, and new-file hashes were identical.
The full gate introduced no new worktree mutation. Raw `llm_bodies.jsonl` was
never printed.

## S3 plan status

The S3 subplan is **READY FOR AUDIT EXECUTION** after review.

The S3 plan is deliberately audit-only and requires:

- B0/C0/S2 source provenance;
- hybrid AST/source-context inventory beyond regex checker PASS;
- EventType/LogKind/console-mirror two-sided tables;
- explicit dynamic producer treatment;
- explicit parent path index P1–P33;
- flag/failure and verification-hygiene matrices;
- current V1–V26 dispositions;
- producer-focused disposable kill-checks;
- no runtime/test edits;
- direct-container claims kept pending S4/S7/S11.

S3 audit execution has not started. The expected next artifact is:

```text
worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md
```

## Deferred follow-up

- S5: final concurrent event identity allocation and uniqueness (`V1`/`V2`).
- S5: symmetric mutation conflict/fail-closed policy (`V15`/`V17`).
- Later subagent slice: Q11-B two-root artifact-only enforcement (`V24`/`V25`).
- Live EventBus redaction (`V23`) remains explicitly deferred.
- Legacy reader/migration remains unsupported by policy.
- S4/S7/S11: direct-container/image/proxy production verification.

## Review instructions

Review in this order:

1. `cli-trace-substrate-rebaseline-2026-07-25.md`;
2. S1 plan/report;
3. S2 plan/report;
4. implemented S2 source/test diff;
5. S3 subplan;
6. S3 plan-review report;
7. patch metadata and apply check.

Do not apply the old candidate patch automatically. Do not commit, push, build,
or deploy from this note without explicit human approval.

## Rollback

S2 rollback is a source-slice revert with no automatic DB migration or deletion
of old JSONL/DB artifacts. S3 rollback is removal of the new plan/review/index
artifacts only; it has no runtime effect.
