# S2 Verification Report — SessionManager and Session-Authority Wiring

Plan: `worklogs/implementation-plans/PLAN-cli-trace-S2-session-manager-and-authority.md`

Parent plan: `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`

Status: **PASS WITH FOLLOW-UP**

Execution date: 2026-07-27

Base checkout:

```text
HEAD       = 3668e758c1522645a1bfb70787ebf53f7ef170a7
origin/main = 3668e758c1522645a1bfb70787ebf53f7ef170a7
branch     = fa/20260725-session-authority-debug-wiring
```

No commit, push, image build, or deployment was performed.

## 1. Plan review before implementation

The READY S2 subplan was reviewed against the current source before runtime
edits. Revision v2 corrected:

- authority schema/open/reservation ordering before `SessionManager.begin_run`;
- workflow identity to one `run_id` per top-level workflow invocation;
- Candidate A stats discovery and the non-creating DB read path;
- `--workspace=None` versus explicit workspace semantics;
- reverse workspace ownership and partial provisioning failure;
- production injected authority versus direct test/legacy constructors;
- entrypoint handoff ownership.

The parent workplan and S1 report were synchronized with these corrections.
Document checks after the plan edits:

```text
python scripts/check_doc_links.py
  OK: 170 markdown file(s) checked, no broken internal links.

plan structural assertions
  PASS

git diff --check
  PASS
```

## 2. S2.0 baseline and provenance

Candidate runtime patch was not applied automatically.

```text
HEAD and origin/main
  3668e758c1522645a1bfb70787ebf53f7ef170a7

candidate patch
  /home/user/backups/First-Agent-dev-20260725Tcandidate-diff-from-3668e758c1522645a1bfb70787ebf53f7ef170a7.patch
  size: 23987 bytes
  SHA-256: ad975712a055697b6089c32f4e72c5f3258d460e98a40a40dd4b4aefff5f9070

candidate patch disposable apply check
  git apply --check: PASS

S2.0 runtime source/test edits
  NONE
```

Pre-S2 provenance snapshot:
`/tmp/first-agent-s2-preflight-20260727.txt`.

## 3. Implemented behavior

### 3.1 Session authority and lifecycle

Implemented:

- `src/fa/inner_loop/session_db.py`
  - session-bound current schema (`session-v1`);
  - `session_id` on current event/Blackboard rows;
  - DB identity metadata;
  - current-schema validation and legacy-schema rejection for production scope;
  - transactional `reserve_run_binding()` with duplicate rejection;
  - `open_existing()` that never creates a missing DB/parent directory;
  - run-scoped event queries and session-scoped Blackboard queries;
  - deterministic `list_run_ids()` for DB-backed stats.
- `src/fa/session/manager.py`
  - frozen `SessionContext` and `RunContext`;
  - explicit `state_root`, `workspace_root`, and optional source workspace;
  - ID validation/generation;
  - atomic manifest writes;
  - provisioning/active lifecycle;
  - reverse workspace ownership check;
  - partial workspace provisioning cleanup;
  - explicit attach validation;
  - fresh run namespace plus DB run binding.
- `src/fa/session/__init__.py`
  - package export.

Production `fa run`/`fa workflow` use the injected session authority. Direct
`EventLog()`/`Blackboard()` construction remains an explicit compatibility path
for isolated tests and legacy helpers; it is not counted as production session
wiring and is not used by current `fa stats`.

### 3.2 CLI and workflow wiring

Implemented:

- `--session-id` on `fa run` and `fa workflow`;
- `--workspace` parser default `None` for those roots;
- default new session and explicit existing-session attach;
- fresh run ID per top-level invocation;
- reused explicit run ID rejection;
- one workflow run ID shared by internal workflow stages in this slice;
- manager resolution before transport wrapping/provider-chain construction;
- injected `SessionDatabase`, `session_id`, and `run_id` into `EventLog` and
  `SessionState`;
- public `--resume` without `--session-id` rejection before provider calls;
- internal workflow draft continuation remains separate and reuses the workflow
  invocation context.

### 3.3 EventLog and Blackboard scope

Implemented:

- EventLog accepts injected session DB and session identity;
- injected EventLog reads `WHERE run_id = ?` and does not fall back to JSONL;
- current TraceEvent mirror rows carry `session_id`;
- SessionState rejects mismatched explicit log/DB/session identity;
- injected Blackboard validates session identity and fails closed on authority
  read/query failure;
- JSONL mirror writes remain best effort, but mirror reads are compatibility-only
  and never current production authority.

### 3.4 Entrypoint adapter

Implemented:

- `FA_SESSION_ID` is separate from `FA_RUN_ID`;
- no `FA_RUN_ID == SESSION_ID` assignment remains;
- optional `FA_RUN_ID` is passed only as an explicit run override;
- auto-run passes `--session-id` when the entrypoint has a managed session;
- failed clone/checkout stops before command/agent launch;
- auto-run managed workspace manifest/DB provisioning delegates to
  `python -m fa.session.manager provision`;
- command override remains an adapter and does not create a second logical
  authority.

A real handoff probe using a disposable source copy with the new implementation
files included produced:

```text
status=SUCCESS
manifest: <temp>/home/.fa/sessions/handoff-session/manifest.json
session.db: <temp>/home/.fa/sessions/handoff-session/session.db
child argv included:
  run --task ... --workspace ... --session-id handoff-session
```

An earlier probe against a `git clone` of the uncommitted checkout failed because
new `src/fa/session/**` files were untracked and therefore absent from the clone.
That was classified as source-revision drift, not hidden as a pass. The corrected
probe committed the disposable source copy locally and passed.

### 3.5 DB-only stats

Implemented:

- `fa stats --session-id` selector;
- Candidate A manifest/session DB discovery;
- DB-bound run enumeration and `run_id` filtering;
- `fa.stats.parse_session_db()` current-format reducer;
- `StatsSourceError` structured source failures;
- old JSONL/old per-run DB diagnostic `legacy_trace_unsupported`;
- no DB creation/import/fallback for old artifacts;
- direct `parse_session()` retained only for legacy/test compatibility and not
  called by `_cmd_stats` current-format path.

## 4. Tests and verification

### 4.1 Targeted S2 gate

Command:

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

Observed:

```text
127 passed, 1 warning
```

The warning is pytest's pre-existing unknown `asyncio_mode` configuration
warning in the host environment.

### 4.2 Full suite checkpoint

Command:

```bash
PYTHONPATH=src python -m pytest -q
```

Observed:

```text
2014 passed, 15 skipped, 1 warning
```

Skip classification:

```text
12 shellcheck unavailable
1 executable-bit filesystem limitation
2 deferred runtime-server extra
```

### 4.3 Changed-file static gate

Commands:

```bash
ruff format --check \
  src/fa/cli.py src/fa/stats.py src/fa/inner_loop/session_db.py \
  src/fa/inner_loop/state.py src/fa/blackboard/blackboard.py \
  src/fa/session tests/test_session_lifecycle.py tests/test_session_db_authority.py \
  tests/test_cli.py tests/test_cli_ergonomics.py tests/test_stats.py \
  tests/test_fa_entrypoint.py

ruff check <same changed-file set>

mypy src/fa/cli.py src/fa/stats.py src/fa/inner_loop/session_db.py \
  src/fa/inner_loop/state.py src/fa/blackboard/blackboard.py \
  src/fa/session/manager.py src/fa/session/__init__.py \
  tests/test_session_lifecycle.py --strict

python -m py_compile <changed Python source/test files>
bash -n scripts/fa-entrypoint.sh
git diff --check
```

Observed:

```text
Ruff format: PASS
Ruff check: PASS
mypy: Success: no issues found in 8 source files
py_compile: PASS
bash -n: PASS
git diff --check: PASS
```

Repository-wide `ruff format --check .` / `ruff check .` were also probed but
are not green because of pre-existing documentation formatting findings and
pre-existing unused `noqa` findings in `src/fa/inner_loop/hooks/base.py`. Those
findings were not mass-formatted or silently changed in S2. The changed-file
static gate above is the authoritative S2 result.

### 4.4 Contract/document checks

```text
python scripts/check_producer_consumer_contract.py  → PASS
python scripts/check_log_kind_contract.py           → PASS
python scripts/check_no_mocked_dataclasses.py       → PASS
python scripts/check_doc_links.py                   → PASS
```

### 4.5 Worktree hygiene

Pre-final snapshot:
`/tmp/first-agent-s2-prefinal3-20260727.txt`.

Post-final snapshot:
`/tmp/first-agent-s2-postfinal3-20260727.txt`.

Comparison:

```text
pre/post status entries: identical
pre/post tracked-mode hash: identical
pre/post new-file hashes: identical
git diff --summary after full suite: empty
```

The full gate introduced no new worktree mutation. The pre-existing candidate
backup/diff baseline remains separate from S2 evidence.

## 5. Producer kill-checks

Disposable source mutations were applied only under `/tmp`:

```text
remove _cmd_run SessionManager producer
  targeted composition test: FAIL (required)

remove EventLog run_id query scope
  injected run-isolation test: FAIL (required)

replace current stats DB reader with legacy events.jsonl reader
  current DB stats test: FAIL (required)
```

The three kill-checks prove the tests are not consumer-only or vacuous.

## 6. Path/matrix result

| Path | Result |
|---|---|
| default `fa run` session creation | PASS local C2 |
| default `fa workflow` session creation | PASS local C2 |
| explicit `--session-id` attach | PASS local C2 |
| two runs in one session | PASS C1/C2 |
| two sessions cannot share authority | PASS C3 |
| explicit reused run ID | PASS C3 |
| public `--resume` without selector | PASS C2, rejected before provider |
| workflow internal continuation | PASS existing workflow matrix |
| workspace mismatch/path escape | PASS C3 — outer layer only at the time; see note ¹ |
| corrupt/missing manifest | PASS C3 — unreadable JSON only at the time; see note ¹ |
| failed clone/checkout | PASS shell C2 |
| current DB-only stats | PASS C2 |
| legacy JSONL/old DB stats | PASS C2/C3, unsupported/no-write |

¹ **Amended 2026-07-29 (S6.6d).** Both rows were accurate about what was *run*
and over-broad about what it *proved*. A mutation sweep of `session/manager.py`
later showed 8 of 9 guards could be deleted with the whole suite green:

* *workspace mismatch/path escape* — `workspace_escape` is raised at two sites
  (`manager.py:182` and `:248`). The assertion was on the error **code** at the
  API boundary, which the outer site satisfies alone, so the inner validator was
  deletable invisibly. Untested redundancy is not redundancy.
* *corrupt/missing manifest* — exercised only unreadable JSON. Manifest
  **tampering** (identity, `schema_version`, `status`, non-canonical DB path)
  was unverified, though each guard was later confirmed live.

Closed by `tests/test_session_manifest_guards.py`, which drives the public
`create_or_attach_session` against a tampered on-disk manifest per field and
asserts the specific error code, plus a registry guard that fails when a new
`SessionManagerError` code has no test. Post-fix the same sweep reports
`caught=9 survived=0`. See
[`PLAN-cli-trace-S6.6-mutation-gap-closure.md`](../archive/PLAN-cli-trace-S6.6-mutation-gap-closure.md).

## 7. Deferred and follow-up work

S2 does not claim:

- final concurrent event allocator/unique event identity (`V1`/`V2`, S5);
- symmetric Blackboard mutation conflict/fail-closed write policy (`V15`/`V17`,
  S5);
- artifact-only subagent two-root enforcement (`V24`/`V25`);
- live EventBus redaction (`V23`, explicitly deferred);
- direct production container acceptance/rebuild/proxy verification (S4/S7);
- legacy reader/migration support.

## 8. Final S2 disposition

```text
S2 STATUS: PASS WITH FOLLOW-UP
Local lifecycle/authority/stats wiring: VERIFIED
Changed-file static gate: VERIFIED
Full local suite: VERIFIED
Direct-container production verification: PENDING S4/S7
Next approved owner: S3 liveness/contract audit, then S4/S5 as dependency order requires
```
