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

## Next bounded action

1. Human-review the S2 diff and verification report on branch
   `fa/20260725-session-authority-debug-wiring`.
2. Do not commit, push, or deploy without explicit human approval.
3. Execute the next approved slice in dependency order: S3 liveness/contract
   audit, then direct-container S4/S7 verification as scheduled.
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
