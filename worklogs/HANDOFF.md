# HANDOFF.md — next agent/session

> Read [`knowledge/llms.txt`](../knowledge/llms.txt) §MUST READ FIRST.
> This file records the verified state and the next bounded action.

## S13.5 & S13.6 BASELINE + S13.7 NEW PROVIDER ONBOARDING (`aigate` & `anymodel`) (2026-08-07)

**Source-Verified Baseline for S13.5 & S13.6:**
- **S13.5 (`fa conformance` offline matrix):** Verified `CONF-1..7` run offline with real production composer + validator (`tests/conformance/test_offline_matrix.py`, 5 tests passed). `CONF-6` (user-after-tool) recorded as tolerance (`ok=False`, `ran=True`).
- **S13.6 (Rate-limit-aware live runner):** Verified sequential execution, unique `run_id` minting (`conf-<provider>-<case>-<utc>`), 429 backoff/resume without losing prior rows, and glob-based cleanup (`tests/conformance/test_live_runner.py`, 6 tests passed).
- **S13.7 New Providers Onboarded:** Added `"aigate"` (`https://api.aigate.shop/v1`) and `"anymodel"` (`https://anymodel.org/v1`) to `PROVIDERS` (`_OPENAI_COMPAT` adapter category) in `src/fa/providers/registry.py` and `CANONICAL_PROVIDER_BASE_URLS` in `src/fa/providers/routing_lint.py` per attached API documentation.
- **Suite Status:** `just check` green — **2577 passed, 15 skipped, 1 xfailed** (0 failed). Zero `noqa` waivers added.
- **Patch:** `/home/user/s13-aigate-anymodel-registry.patch`.

## S12 COMPLETE — platform capability markers (2026-08-02)

The operator's native-Windows `just check` reached `test` for the first time
(both encoding defects fixed) and reported **92 failed**. None was a product
defect: the suite assumes a POSIX host.

**Root cause was the guard, not the platform.**
`skipif(shutil.which("bash") is None)` asks *"is bash installed?"* when it means
*"can bash here speak this host's path dialect?"*. Git Bash satisfies the former
and answers `/c/Users/x` where Python asked `C:\Users\x`. **A box with no bash
would have skipped cleanly** — the operator was punished for being more capable.

**Delivered:** `tests/_capabilities.py` — six cached probes that test an
*effect*, never `sys.platform` (which would also skip on WSL, where these tests
pass). 85 tests marked. `tests/test_s12_marker_hygiene.py` enforces that every
skip reason names a capability, not a platform.

| | Linux (before) | Linux (after) | Windows (simulated) |
|---|---|---|---|
| passed | 2428 | **2460** | 2362 |
| skipped | 15 | **15** | 104 |
| coverage | 83.22% | **83.22%** | 82.27% (floor 80) |

**CT2 held exactly** — the Linux skip count and coverage are byte-identical, so
no coverage was silently deleted. That was the slice's primary negative proof.

**Patch:** `patches/S12-rebased-on-ddbd03f.patch` (101 commits). Verified by
`git am --3way` onto pristine `ddbd03f` → tree
`0c8b1547ad3fb451517f519d0eb6212b5f95ed6d`, then 2460 passed on the applied
tree.

```
git checkout ddbd03f228f78d462915343408188d3b23ee4ae7
git am --3way patches/S12-rebased-on-ddbd03f.patch
```

### Two findings worth carrying

**The plan's `tmux` probe was wrong and the positive assertion caught it.**
`shutil.which("tmux")` is False on the Linux sandbox, yet all 13 PTY tests pass
via the `pexpect` fallback. Shipping it would have skipped 26 passing tests.
Lesson: *a probe must be validated against the host where the tests currently
pass, not only against the host where they fail.*

**Seven "product defects" were one test-fixture bug.** `monkeypatch.setenv(
"HOME", ...)` does not move the home directory on Windows — `ntpath.expanduser`
prefers `USERPROFILE`. `events.jsonl` *was* written, to the operator's real
`~/.fa`. Opened as **I-43**, because a suite that mutates a developer's real
state directory is worth fixing on its own.

### Next bounded action

1. **Operator applies the patch and runs `just check` on Windows.** Expect
   **0 failed, ~104 skipped**, coverage ~82.3% (floor 80).
2. Then **S11** (`PLAN-cli-trace-S11-controlled-deployment.md`, operator-gated,
   60–90 min). Two S10c behaviour changes affect it: `routing-check` now aborts
   `fa-clean-rebuild.sh` on a bad `--config`, and `fa workflow` exits 1 on a
   non-`DONE` verdict, so any `&&` chain reading `$?` changes behaviour.
3. Parent Do #10: commit/push through the PR workflow **only after human
   approval**.

### BACKLOG delta

- **I-11** — PARTIALLY RESOLVED. The suite is now honest on Windows; FA still
  has no Windows shell backend (`fs_run_cmd`), so the 85 stay unverified there.
- **I-42** (P3) — 11 PTY tests share a hardcoded global `/tmp`.
- **I-43** (P2) — the suite writes into the real `~/.fa` on Windows.
- **I-44** (P3) — `ruff format --check .` fails on 39 pre-existing `.md` files
  (all 353 tracked `.py` clean; present before S12).

### Known coupling created by S12

Windows dev now survives only up to roughly **82%** coverage. BACKLOG **I-28**
wants the floor restored to 90; raising it past ~82 makes the operator's box
unable to pass its own gate. Named here so a future ratchet slice does not
discover it by breaking.

## S10c COMPLETE — deploy-gate contracts, artifact posture, request cost (2026-08-01)

**Three BACKLOG items closed** (I-36, I-39, I-40) plus **Q35b** resolved and
I-37 option 4 shipped. Everything below was measured, not inferred.

| | before | after |
|---|---|---|
| `routing-check` on a missing path | **exit 0** (deploy gate passed) | exit 2 |
| malformed YAML | raw traceback from **5** commands | exit 2 from all five |
| `fa workflow` on BLOCKED | **exit 0** (`&& deploy` proceeded) | exit 1 |
| artifacts under `~/.fa` | **4 files `0644`**, dirs `0755` | all `0600` / `0700` |
| composer extras | silently dropped, unchecked | asserted; 3rd instance found |
| inline tool block | 10,619 bytes | 7,471 (**29.6% off every request**) |

**Gate:** 2415 passed · ruff clean · mypy 322 · pyrefly 0 · pylint exit 0 ·
`cli-coverage-floor` 27/27 · C901 budget still 15. Mutation sweep 15/15 after
one survivor was killed.

### Carry these forward

- **The S10b ratchet paid for itself one slice later.** Adding the Q35b
  derivation inline pushed `_cmd_workflow` to C901 16 > 15. Fixed the design
  (extracted `_workflow_exit_code`), not the symptom.
- **Deriving one fact twice is how artifacts drift.** The `global_history` row
  built `exit_code` from `result_code` while the process returned a
  verdict-derived value — a BLOCKED run reported `code == 1` with
  `row["exit_code"] == 0`. Compute once, use twice.
- **A mutation survivor is a question, not a verdict.** M12 survived because
  two independent layers secure the session directory. Measuring *both*
  disabled proved it was defence in depth, not a weak oracle — so both were
  kept and each got its own test.
- **Run the kill-check; don't trust it.** One of my own CT5 tests re-encoded
  JSON locally and passed with production reverted. It never read production.
- **Sweep specs need a pattern pre-check every time.** M2 stopped matching
  because ruff reformatted an f-string; the harness scores that as SKIP and the
  summary still looks clean.

**Next bounded action: S11** — controlled deployment and closeout, the final
step of the parent plan. It is **operator-gated**: human diff review, image
rebuild with the revision recorded, container/proxy health checked separately,
direct `docker compose exec` run, source-vs-image drift check, then PR.

**Two S10c changes need a line in the S11 runbook**, since both are
operator-visible exit-code contracts: `fa routing-check` now aborts
`fa-clean-rebuild.sh` on a bad `--config` (previously silent), and
`fa workflow` now exits 1 on a non-`DONE` verdict, so any `&&` chain or CI job
reading `$?` changes behaviour.

## S10b COMPLETE — `cli.py` is C901-clean (2026-08-01)

**All four `cli.py` complexity waivers are retired.** `ruff --ignore-noqa`
reports **zero** C901 findings for the file. Budget **19 → 15**, ratcheted one
step per retirement in the same commit and census-verified each time.

| | before | after |
|---|---|---|
| `_cmd_run` | 39 | <15 |
| `_cmd_stats` | 29 | <15 |
| `_discover_stats_sources` | 19 | <15 |
| `_cmd_selfcheck` | 19 | <15 |

16 helpers extracted. Parity cells were written and run green against
**unmodified** `cli.py` before every step, then proven live with injected
regressions. DoD divergence (re-inline → **T2 green / T3 fails**) re-proven at
each step. **Mutation sweep: 15/15 caught, 0 survivors.**

**Gate:** 2387 passed · ruff clean · mypy 318 · pyrefly 0 · pylint exit 0 ·
`cli-coverage-floor` **27/27** (11 at S10b start) · `cli.py` coverage **90.6%**.

### Carry these forward

- **I-41 fixed** (Q53). `fa.stats` bound `stream=sys.stderr` at *import* time —
  a live defect that surfaced as `ValueError: I/O operation on closed file`.
  Fixing `.write` alone was not enough; both functions also `flush()`, so the
  stream is now resolved **once** into a local. Third instance of the class.
- **A kill-check that does not fail is a claim about the kill-check.** S10b.4's
  first divergence attempt re-inlined one of two helpers and T3 passed —
  correctly, complexity was exactly 15. Investigate before concluding either
  way.
- **Sweep specs need a pre-check.** Two of fifteen patterns did not match the
  source; the harness scores those as SKIP, so the run would have silently
  covered 13 while looking clean.
- **A trap removed:** the ratchet's liveness floor briefly equalled the budget
  (both 15), which would have made the next legitimate retirement fail — and
  invited editing the floor down. Now 13, re-verified against a broken census.

**Next bounded action:** S11 (parent plan, §Step S11). **Q48 is now live** — the
15 remaining waivers are all outside `cli.py` (`inner_loop/`, `stats.py`,
`skills/`, `memory/`, `sandbox/`, `verifier/`); the recorded default is "no
separate slice, retire them in code you already touch". **I-40 stays open**,
now pinned in two places.

## S10b.0–S10b.2 (2026-08-01)

**GAP1 closed.** `_cmd_run` went **39 → under 15** by ruff (the authority);
its `# noqa: C901` is deleted and the waiver budget ratcheted **19 → 18** in
the same commit. Nine helpers extracted, parity green at every step.

- **S10b.0** hard gate re-measured, not assumed — all four targets above floor
  (`_cmd_selfcheck` at 93.8% means S10b.5 is in scope, not deferred).
- **S10b.1** complexity ratchet: budget census + threshold ceiling +
  dead-weight check (`tests/test_s10b_complexity_ratchet.py`).
- **S10b.2** parity suite written and **run green against unmodified
  `cli.py` first** (recorded: sha256 `8bf6ad56…`, 13 passed, complexity 39),
  then proven live by injecting 3 regressions that each failed exactly one
  cell.

**DoD proof executed:** re-inlining `_validate_run_args` → **T2 green / T3
fails**. Structure and behaviour are measured independently.

**Read this before the next extraction.** The slice caught a *silent*
regression that no behavioural test saw: `_loop_guard_warn_sink` closed over
an `output_bus` assigned ~90 lines later (late binding, resolved at call
time). Making that explicit was fine, but annotating `OutputEvent` under
`TYPE_CHECKING` made the emit raise `NameError` — which the observer's
`except Exception` swallowed. Console `loop_warn` would have stopped dead with
every exit code, artifact and parity cell unchanged. **A decomposition's
characteristic failure is a broken observability path, not a wrong exit code.
Any extraction that moves a callback across a scope boundary needs a direct
functional probe.**

**Coverage floors were raised, not conceded.** `_cmd_run` dipped to 75.7%
mid-slice (missing lines identical at 30 — nothing lost, the same uncovered
statements in a smaller function) and recovered to **84.5%**, so the temporary
concession was reverted. Extraction exposed three helpers whose gaps had been
absorbed into `_cmd_run`'s aggregate; 8 C0p tests were added rather than
low floors — including the fatal `draft_store.clear` path, which is
`IntentGuard`-provenance security-relevant and had no test at all. The gate now
enforces **20** functions, up from 11.

**Next bounded action:** S10b.3 (`_cmd_stats` 29 → ≤15). Same protocol —
parity cells first, run green pre-change, then extract. S10b.4
(`_discover_stats_sources` 19), S10b.5 (`_cmd_selfcheck` 19), S10b.6 (mutation
sweep) follow. Budget must reach **15** if all four retire.

**Gate:** 2361 passed / 14 skipped / 1 xfailed · ruff clean · mypy 318 ·
pyrefly 0 · pylint exit 0 · cli-coverage-floor 20/20.

## Post-S10a baseline — GREEN (2026-08-01)

**`just check` exits 0 on the rebased tree.** This is the clean baseline S10b
was waiting for. HEAD `ec126df` on `s7-rebase`; 76 commits from `fc957f3`;
rebases to 70 on `ddbd03f` (6 auto-dropped as already-upstream).

**Verified numbers** — 2335 passed / 14 skipped / 1 xfailed · ruff check **and
format** clean (632 files) · mypy 316 clean · **pyrefly 0 errors** · **pylint
exit 0** · `authoring-check` 0 · `cli-coverage-floor` 11/11 · tree clean after
a full coverage run.

**Backup + rebase verified** — `patches/S10a-F1F3-*` (patch, bundle, rebased
patch, `.sha256`). Rebase tree == `git am --3way` tree onto a pristine clone:
both `3ee0c7417bfa8c8e3b2b1e201ed4e5805bd6381f`.

> **The older `patches/S10a-*` and `patches/S10b-*` artifacts are STALE.**
> They pin `278dab0` / `0eb6129`, both of which predate all nine S10a
> execution commits; their recorded `2272 passed` predates S10a's 62 tests.
> Use the `S10a-F1F3-*` set.

### What was fixed after S10a closed

Two gates in the `just check` chain were **red and unread** — neither caused by
S10a, both found by rebuilding the sandbox with `uv sync --extra dev` (earlier
sessions used bare `pip`, so `just check` had never actually run end to end).

- **F1 — the pyrefly gate could not fail.** It filtered stdout for `ERROR`
  lines and ignored the return code, so a *missing* pyrefly produced
  `returncode=1, stdout=""` → zero ERROR lines → **green**. Four real type
  errors had accumulated behind it. Now split into
  `test_pyrefly_is_installed` (fails loudly with remediation — **Q51**) and
  `test_pyrefly_check_passes` (exit code + parsed count + the
  `INFO <n> errors` summary pyrefly writes to **stderr**, which nothing had
  ever read, as a liveness control). The two sibling config tests in that file
  were also unfalsifiable — `"search-path" in content` passed on the *comment*
  — and now parse the TOML.
- **Q50 RESOLVED — pyrefly is BLOCKING**, and all four seats say so
  (`pyproject.toml`, `justfile`, `advisory.yml`, `ci-guardrails-reference.md`
  Layer 0). It previously read "Advisory-only" while the test blocked; that
  contradiction is why the inert gate went unnoticed.
- **F3 — `pylint src/fa` exited 8 while printing `10.00/10`.**
  `fail-on = ["duplicate-code"]` makes R0801 a **binary** gate, so the score
  line was never evidence of a pass. Red since **S9 (`c611b34`)**.
  `stats.PARSED_KINDS` restated 23 of `LogKind`'s 33 names; it is now derived
  as `frozenset(get_args(LogKind)) - UNPARSED_KINDS` (verified
  identity-preserving). **AP-006 was considered and does not apply** — it
  protects a *behavioural* seam whose duplication is an interface contract;
  this was pure data with no behaviour.
- **F2 — 41 Markdown files failing `ruff format --check`** were rebase drift
  against main's `6262e7d`; 40 clear on rebase, the 2 that did not are fixed
  here. Proven on the rebased tree: 632 files, 0 offenders.

**Lesson worth carrying:** deriving `PARSED_KINDS` would have made
`PARSED_KINDS | UNPARSED_KINDS == set(LogKind)` true *by construction*.
Measured before shipping — a fictional `LogKind` with no parser left the old
assertion green. That tautology was deleted rather than reworded and replaced
with cardinality checks plus a stray-name check for the new failure mode
derivation introduces. **Every structural simplification can silently convert
a live check into a vacuous one; check for it.**

**Next bounded action:** S10b.0 — re-verify the coverage floors, then S10b.1.
See `worklogs/VERIFY-S10a-2026-08-01.md` for the full S10a audit (D1/D2/D3
bookkeeping items remain open and are non-blocking).

## Current state

> **Superseded 2026-07-30 — read [§S10a — COMPLETE](#s10a--complete-2026-07-31) and [§S7 container half — EXECUTED](#s7-container-half--executed-2026-07-30) first.**
> Everything below this line describes the tree as of **2026-07-27** (pre-S5)
> and is kept as the historical record. S5, S6, S6.6 and the local half of S7
> have landed since; the base SHA, branch and "next bounded action" in this
> section are all stale.

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

## S10a — COMPLETE 2026-07-31

`cli.py` **59% → 83.5%**. All 11 target functions clear their coverage floors;
a `just`-invoked gate now pins them. Full per-step table, mutation results and
findings: [plan §11](./implementation-plans/PLAN-cli-trace-S10a-cli-coverage.md).

**Gate:** 2334 passed · ruff clean · bare `mypy` 316 files · `pylint` 10.00/10 ·
`authoring-check` 0 · **0 new `noqa`** · tree clean.

**One production change**, as the DoD allowed: a keyword-only
`transport=`/`secrets=` seam on `_cmd_probe`, defaulting to `None` and
resolving to exactly the previous collaborators. It mirrors the house idiom on
`_cmd_run`/`_cmd_workflow`. Its CT1 kill-check initially **survived**, which
exposed a weak test — the no-seam case returned at the "no roles" guard before
the default was ever resolved. Now a valid-config test drives the real default
and both halves bite.

**The mutation minimum earned its keep**: ~30 guards deleted, **7 survivors**,
all resolved. Two were *redundant guards* in the product (recorded, not
"fixed"); four were weak oracles asserting only an exit code that a downstream
handler also produces; one was a **hang** — deleting the empty-token guard let
execution reach the real blocking `serve()` and the 300s timeout scored as
"SURVIVED". All proxy tests now patch `serve` so mutations fail fast.

**Two findings filed, deliberately not fixed** (coverage slice, one-edit DoD):

- **I-40** — `fa routing-check --config /nonexistent` exits **0**, and
  `scripts/fa-clean-rebuild.sh:471` treats that as a passing **deploy gate**.
  Behaviour is pinned so the fix is a visible diff.
- **I-41** — `fa.stats` renderers bind `stream=sys.stderr` at import time.
  **Third instance** of the class after V10 and S8.8.

**Next: S10b** — in-module decomposition, now unblocked. Its hard precondition
(every target ≥ its floor) is met, so the parity suite it writes can fail.

---

## S9 — COMPLETE 2026-07-31

All seven steps executed. Gate: **2272 passed** / 14 skipped / 1 xfailed ·
bare `mypy` **315 files clean** · `ruff` clean · `pylint src/fa` **10.00/10** ·
`fa authoring-check` **0** · **0 new `noqa`**. Per-step table and kill-check
matrix: [plan §11](./implementation-plans/PLAN-cli-trace-S9-stats-projections.md).

**One production defect fixed (F6).** `_parse_since("-5d")` returned
`-432000.0`; both call sites compute `cutoff = time.time() - since`, so a
negative window pushed the cutoff into the *future* and filtered out every
session. The operator saw `no matching sessions found` — a wrong answer
indistinguishable from an empty one. Now rejected (negative, zero, non-finite)
with **exit 2** from a single pre-dispatch guard covering both `fa stats`
branches. Valid windows, including `1e3h`, are unchanged.

**Two guards that could not fail, replaced.** The projection-only check was a
7-file denylist while `src/fa` has **139** modules; it is now an **AST**
allowlist scan with two liveness controls (AST because `output.py` mentions
`global_history` in a docstring and a string scan false-positives). The
tautological `test_stats_global_history_projection_only` — which asserted
`"global_history" in cli.py`, true for 17 unrelated reasons — was **deleted**.

**`PARSED_KINDS` now derived.** A deleted `_parse_events` dispatch branch used
to leave the contract test green; an AST cross-check now catches it with a
precise drift diff. 23 parsed + 10 unparsed = 33 LogKinds, exact.

### Two places where a *reading* was overturned by a *measurement*

1. **S9.5's premise was wrong.** The plan asked us to pin that `created_at`
   survives re-export. Measured: `run_id` reuse is **refused**
   (`run_id_reused`, `manager.py:394`), so `export_run` runs at most once per
   run id and F5 is **unreachable, not latent** — the earlier probe bypassed
   the session manager by calling the store directly. The test now pins the
   guard instead.
2. **S9.6's sweep found two survivors.** Deleting the `manifest_path_mismatch`
   and inactive-manifest guards in `_discover_stats_sources` left all 2270
   tests green. The preflight had rated Do#1 **L3 by reading** them — but
   those are stats-side *copies*, independent of `SessionManager`'s
   (`manager.py:144-164`), and stats never builds a manager. Two adversarial
   C2 tests added; both mutations now caught (**6/6**).

**Rule for S10/S11: rate liveness from an executed probe, never from source
inspection.** "The guard is present" is not "the guard is verified."

**Mutation:** `stats.py` (887 lines, the largest never-mutation-tested module
in the substrate) added to both mutmut and gremlins scope — gremlins
**164/164 zapped**, `41 passed` confirmed.

**Owed forward:** `Q35b` (a BLOCKED workflow verdict still exits `0`),
`Q38` (`read_all` pagination), `Q39` (`--run-id` overrides `--since`, pinned).
`I-36`/`I-37`/`I-39` remain operator-deferred.

### Next bounded action

**S10 — decide whether CLI extraction is warranted** (parent plan line ~1840).
Depends on S2, S3, S7, S8, S9 — all now complete. Note it is explicitly a
*decision* step: extraction only if the evidence demands it.

---

## S8 — COMPLETE 2026-07-30

All eight steps executed. Gate: **2252 passed** / 14 skipped / 1 xfailed ·
bare `mypy` **314 files clean** · `ruff` clean · `pylint src/fa` **10.00/10** ·
`fa authoring-check` **0 diagnostics** · **0 new `noqa`**. Full per-step table
and kill-check matrix: plan §11.

**Two production defects fixed**, both found by review/execution rather than by
the suite:

1. **RV4 / S8.7** — `global_history.stop_reason` was derived from `result_code`,
   and every mode returns `0` when the pipeline merely *ran to completion*. A
   BLOCKED run was recorded as `workflow_complete`. **S9's success rates would
   have counted rejected runs as successes.** Now derived from
   `FlowState.status` via `_WORKFLOW_STATUS_TO_STOP_REASON`.
2. **S8.8** *(operator-approved scope addition)* — `global_history.db` used an
   **import-time** `Path.home()` constant, so the writer ignored
   `FA_STATE_ROOT` while `fa stats --global-history` already honoured it:
   split brain, operator sees an empty history. Fixed with a call-time
   `default_global_history_path()`, mirroring the V10 fix in `state.py`. Reader
   and writer now share one definition.

**I-38 closed by S8.4** — quiet-scoped stdout contract; `console` byte-identical.
`I-36`, `I-37`, `I-39` remain deferred per operator decision.

**Mutation:** statement-deletion sweep over the S8 delta **7/7 caught, 0
survived** (`scripts/sweep_specs/s8_workflow_controller.json`); gremlins over
`workflow_artifacts.py` **49/49 zapped**, `70 passed` confirmed. Both tools now
cover `workflow_artifacts.py`, which had never been mutation tested.

**One pre-existing test intentionally revised** — `test_s7_cli_run_paths.py`
matrix-D asserted `stderr == ""` under quiet; S8.4 moves the status line there
by design. Now pins the real guarantee (clean stdout, no live renderer). RK1
materialised exactly as the plan predicted.

**Owed to S9:** revisit **Q35b** — a BLOCKED verdict still exits `0`. That was
defensible while `stop_reason` was the only signal; now that it is honest, the
exit code is the last remaining lie, and CI gating is the main reason to run
`fa workflow` unattended.

### Next bounded action

**S9 — verify stats and derived projections** (parent plan line 1796). Note S9
depends on S5 **and** S8, both now complete, and it consumes the very column
S8.7 just corrected.

---

## S8 plan — v3 record (superseded by the completion note above)

> **v3 review pass found a production defect and two dead steps in v2.**
> Read `§Preflight → Review-pass findings (RV1–RV6)` in the plan first.

**RV4 — production defect, now owned by S8.7.** For one run with a `BLOCKED`
eval verdict, three artifacts disagree:

```text
eval_report.json : verdict='BLOCKED'
flow_state.json  : status='FAILED'
global_history   : stop_reason='workflow_complete'   <-- wrong
process exit     : 0
```

`cli.py:1782` derives `stop_reason` from `result_code`, and every mode returns
`0` when the pipeline merely *ran to completion*. **S9 builds cross-run
dashboards on this table — every success rate would count BLOCKED runs as
successes.** S8.7 fixes it by deriving `stop_reason` from `FlowState.status`.

**RV1/RV2 — v2's S8.3 was both impossible and ceremonial.** It planned to have
`_print_terminal_summary` consume a re-read `FlowState`, but that function is
called from *inside* the mode functions (7 sites) before `_cmd_workflow`
resumes. And once corrected, its only effect would have been a printed string —
a "consumer" that satisfies the exit criterion's letter while a deleted
artifact costs nothing. **S8.3 is redesigned** around the consumer that already
needed the data and was fabricating it (the `global_history` export). This is
the same class of error as the S7 sheet's unfalsifiable checks: a verification
that cannot fail.

**RV5** — the failure path *does* still write a projection row (probed:
`exit_code=2`, `stop_reason='workflow_failed'`); untested, so S8.6 now asserts
it. A future early-return would silently drop failed runs and bias every S9
metric.

**RK6 — execution order is load-bearing.** S8.2, S8.3 and S8.7 all edit
`cli.py:1780–1794`; they are **strictly sequential** (S8.2 → S8.3 → S8.7).
S8.6 is parallel-safe (tests only); S8.4 has the largest blast radius; S8.5
(mutation) last.

**S8.7 is the highest-ROI step** — the only one fixing a wrong value in
production data, and a prerequisite for S9 computing an honest success rate.

**Q35 upgraded.** Exit code on rejection is no longer cosmetic: it was the sole
input to `stop_reason`. S8.7 severs that coupling, which makes the exit code a
pure CLI concern and safe to decide later. Default stays **Q35a** (keep
`exit 0`, assert it); recommend revisiting as **Q35b** in S9, since CI gating is
the main reason to run `fa workflow` unattended.

Plan now: **6 goals, 7 contracts, 8 steps, 16 named tests, 12 paths, 8 risks.**

---

## S8 plan — v2 record (superseded by v3 above)

[`PLAN-cli-trace-S8-workflow-controller-surface.md`](./implementation-plans/PLAN-cli-trace-S8-workflow-controller-surface.md)
**v2, status READY**, depth P2. Six steps (S8.0–S8.6). Recommended order:
S8.0 → {S8.2, S8.3, S8.6 in parallel} → S8.4 → S8.5 (mutation).

**Operator decisions folded in (2026-07-30):**

- **Q32 RESOLVED — `quiet` is a console-verbosity control, not a processing
  control.** Adopted I-38 option (a) **scoped to `quiet`**: default `console`
  stdout is **unchanged**; under `--output-mode quiet` the status line goes to
  stderr and stdout is byte-exactly `final_text`. Durable side effects (DB
  rows, `flow_state.json`, `eval_report.json`, `global_history`) are identical
  in both modes and S8.4 must prove it. This is strictly smaller than the v1
  assumption (unconditional move) — no `console`-mode test can break.
- **Q34 RESOLVED — workflow is a SECOND deployment gate.** Detailed workflow
  testing happens after the whole workplan. **A container workflow
  verification sheet (the S7-container analogue) is therefore owed after the
  final slice — do not lose it.**
- **Q33** (no `route` column in `global_history`) and **Q35** (exit code on a
  BLOCKED verdict) are non-blocking with recorded defaults.

**BACKLOG I-38 will close via S8.4** — it is the one deferred finding pulled
forward, because S9 consumes machine-parseable CLI output. I-36, I-37, I-39
remain deferred to after the workplan per operator decision.

### v1 → v2: an audit finding I got wrong, and how

v1 dismissed parent Do #4 as "already L3" and scoped S8 to four gaps. Re-audit
found that **too aggressive** — a fifth gap was real:

- `_write_stage_failure_state` (`cli.py:1242`) has **7 call sites** across all
  three modes; **zero** tests reach any of them.
- `status="FAILED"` is written by production at 2 sites and asserted **0 times**
  in the workflow suite.
- `BLOCKED → FAILED` (`cli.py:1081`) is tested only at the **parser** level
  (`test_workflow_artifacts.py:200`) — the *C0-consumer-only false-confidence
  trap* named in tests-writing skill §10.

Confirmed by probe with a persistent-500 transport (what `UrllibTransport`
actually produces, `transport.py:117`): `exit=2`, `status='FAILED'`,
`active_role='planner'`, fail-fast message on stderr. **The behaviour is
correct — it is simply unverified.** Added as **G5 / CT6 / S8.6**.

**Root cause of the bad audit, recorded so it does not repeat:** coverage was
judged per-*feature* ("repair mode is tested") instead of per-*branch*
("repair mode's failure path is tested"). All five happy-path tests v1 cited
assert `code == 0` or a *pre-dispatch* validation `code == 2`; none drives a
stage to a non-zero exit. **Rule for S9–S11: "already covered" must be verified
per-branch.** Recorded as RN4b in the plan.

**Q35 (new, non-blocking).** A `BLOCKED` verdict yields `status='FAILED'` but
**`exit=0`**; an exhausted repair budget also returns 0
(`test_cli_ergonomics.py:369` pins this deliberately). So a stage *crash* exits
2 while a controller-level *rejection* exits 0 — meaning `fa workflow && deploy`
proceeds on a BLOCKED verdict. Defensible (the tool ran fine; the code was
rejected), but S8.6 pins today's behaviour so any future change is a visible
diff rather than silent drift. Decide with S9/S10.

---

## S7 container half — EXECUTED 2026-07-30

**S7 is now complete (local + container).** The operator ran S7.C0–S7.C7 on
`fa@fa-HP` against deployment revision **`6262e7d`**. Full per-step verdict
table and verbatim evidence: [`PLAN-cli-trace-S7-container-verification.md`](./implementation-plans/PLAN-cli-trace-S7-container-verification.md)
§3 "Execution record".

| Step | Verdict |
|---|---|
| C0 identity · C1 cell A · C2 authority/mirror · C3 correlation | MATCH |
| C4 body gate (cells B+C) · C4b request anatomy · C6 S4-F1 regression | MATCH |
| **C5 quiet mode** | **PARTIAL** — trace contract MATCH, stdout contract MISMATCH |
| C7 hygiene | MATCH (with a caveat, below) |

**The headline result — S4-F1 is closed on the machine that exhibited it.**
C6: old `<workspace>/.fa/session.db` **absent**, `.fa/smoke/session.db`
**present**, `distinct session_id = [('cli-smoke',)]` and not `[('',)]`. Empty
was never inert — every guard reads `if self.session_id and ...`, so the old
artifact accepted rows stamped for a foreign session. A non-empty id re-arms
them *by construction*.

**C7 caveat — one line of that output proves less than it appears to.** The
`find /workspace -name session.db 2>/dev/null` and
`cd /repo && git status --short` checks both printed **nothing**, which reads
as "clean". But with `2>/dev/null` and `cd ... 2>/dev/null`, *searched-and-found-nothing*
and *could-not-look* are byte-identical. Verified in the sandbox: `find` on a
non-existent path exits **0** and prints nothing. And per `docker-compose.fa.yml`
there is **no `/workspace` mount** for this service — `fa-entrypoint.sh:160`
clones into `/sessions/<id>` instead, which is why C0 reported "no shadow". So
the stray-authority check most likely searched a near-empty directory. The
*conclusion* is still supported — C1/C2/C3 independently show exactly one
authority per session under `/home/fa/.fa/sessions/` — but the C7 command
itself should search `/sessions` and `/home/fa` and echo a sentinel when a path
is missing. Same defect class as the two below; recorded, not fixed.

**Two sheet defects were found and corrected mid-execution**, both "a check
that cannot fail": C3's orphan query was
`WHERE run_id=? AND (run_id IS NULL OR run_id="")` — a contradiction returning
`0` on every database (proven by seeding 3 real orphans and watching it still
print `0`); and C4 asserted an absence with no liveness witness, so a crashed
run would have printed the passing string. Both were authoring defects in the
sheet, not product defects. *An absence assertion needs a positive control, or
it is decoration.*

### Findings from the container half — all recorded, none fixed

Per the sheet's §0 stop rule (*record and classify; do not fix*). **The user
has decided these are addressed after the main workplan and all remaining
slices are finished** — they are not S8 blockers and must not be folded into
S8 opportunistically.

| ID | Severity | One line |
|---|---|---|
| [`BACKLOG I-36`](../knowledge/BACKLOG.md) | P2 | `llm_bodies.jsonl` is `0644` while the session manifest is `0600` — the most sensitive artifact is the most permissive. Fix with an `opener=` (atomic), **not** post-hoc `chmod` (race window). Also covers `events.jsonl` and the run-dir `mkdir`. |
| [`BACKLOG I-37`](../knowledge/BACKLOG.md) | P2 | Tool schemas transmitted **twice** per request (inline system message + native `tools` array), 12,130 B of pure duplication on every call. **And**: the `AGENTS.md` map is **48.4%** of the live request — bigger than `AGENTS.md` on disk. 84.5% of every request is standing context; the task is 0.1%. Characterise the map *before* optimising the tool block. |
| [`BACKLOG I-38`](../knowledge/BACKLOG.md) / **Q31** | P2 | `--output-mode quiet` writes **34 bytes** to stdout (`cli.py:2212` 29 B + `:2214` 5 B) while `QuietRenderer`'s docstring promises "nothing on stdout … so `> result.txt` stays parseable". The renderer is innocent — those `print()`s bypass the `EventBus`, so no renderer test can see them. **Policy fork, promoted not decided**; Q31 is in the S7 plan §9. Recommend (a) status line → stderr. **Resolve before S9**, the next consumer of parseable CLI output. |
| [`BACKLOG I-39`](../knowledge/BACKLOG.md) | P3 | `prompt_cache_retention` is emitted by the composer and silently dropped for every Mistral route (not in `MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS`). Reaches `openai_compat`, never Mistral. `routing_lint.py` check 3 cannot see composer-injected extras. |

Sequencing note: **I-37 and I-39 both touch request composition**; do them in
one slice. **I-36 and I-38 are independent** and small. I-38 has a hard
ordering constraint (before S9); the rest are genuinely deferrable.

Four findings, none of which the 2,227-test local suite could produce. That is
the argument for the container sheet existing.

---

## S7 handoff — 2026-07-30 (local half; context for the above)

**State.** S5 (upstream `fc957f3`), S6, S6.6 and the **local half of S7** are
landed. Gate on the rebased branch: **2227 passed** / 14 skipped / 1 xfailed,
coverage **81.30 %**, `mypy` + `pyrefly` + `ruff` clean, `pylint src/fa`
10.00/10, `deptry` clean, 9/9 contract scripts, `fa authoring-check` 0
diagnostics.

```text
base   = fc957f3  (origin main, "s5")
patch  = patches/S7-stack-from-fc957f3.patch   (git am; sha256 in SHA256SUMS)
```

**Rebase note.** Upstream landed S5 as `fc957f3`, a *sibling* of the local
`57f574a` — both children of `adc29d1`. The two are byte-identical in
`state.py`, `session_db.py`, `output.py` and `cli.py`, so replaying 31 commits
was conflict-free. Three things upstream's S5 lacks were carried forward, each
found by **running the gate**, not reading the diff: `mutation_guard` exports
(`authoring-check` exit 1), five S5 test typing fixes (pyrefly
`bad-assignment`), and **S4-F3** (12 deploy scripts at `100644`, including
`scripts/fa`). Note that the S5 post-merge review closed S4-F3 as "already
fixed" — correct for `57f574a`, wrong for `fc957f3`. *A finding's status is a
property of a base, not of the finding.*

**Next bounded action — SUPERSEDED 2026-07-30: the container half is DONE
(see the section above). The next bounded action is S8 — workflow as a separate
controller surface, parent plan line 1753.** Original text follows for context.

**~~Next bounded action~~ — S7 container half.** Run
[`PLAN-cli-trace-S7-container-verification.md`](./implementation-plans/PLAN-cli-trace-S7-container-verification.md)
after deploying this branch: eight steps (S7.C0–S7.C7) with exact
`docker compose exec` commands and EXPECT lines. **Order matters** — S7.C6 is
the regression check for the S7.5 fix, so it must run *after* deployment; the
rest are order-independent after S7.C0. Never print `llm_bodies.jsonl`
contents: counts, byte sizes and identifiers only. Return the §2 evidence
blocks and they fold into the S7 plan §11.

~~S7 stays **complete-local / deployment-pending** until then~~ — **resolved
2026-07-30: the container half ran, so S7 is complete and the parent's §Do-not
is satisfied with real-deployment evidence rather than fake transport. S8 is
UNBLOCKED.**

**Toolchain change to be aware of.** The pre-commit ruff hook is no longer the
pinned mirror; it is `repo: local` / `language: system`, so it runs the ruff
`uv sync` installed. The mirror pinned v0.15.18 independently of
`pyproject.toml`'s `ruff>=0.5`, and the two disagreed: 0.16 exempts a broad
`except` that logs with `exc_info=`, v0.15.18 did not, and a local `--fix`
stripped two waivers the hook then demanded back. Upgrading is now
`uv lock --upgrade-package ruff` — one place, no drift.

**New backlog items opened this session:**

- [`PLAN-ble001-waiver-reduction.md`](./implementation-plans/PLAN-ble001-waiver-reduction.md)
  — **DRAFT, needs Q30.** Measured: **197** broad catches are waived vs **37**
  that satisfy BLE001, i.e. 84 % waived, so the rule no longer carries
  information. Classified A/B/E with the conversion traps recorded (notably:
  category B is only mechanical while the ruff floor stays ≥0.16, and raising a
  log level is a product decision). Recommendation is option (c) — ratchet
  first, then the one mechanical batch.
- `BACKLOG I-34` — Q19/V24/V25 subagent containment (open security gap; strict
  `xfail` is its executable record).
- `BACKLOG I-35` — `SessionDatabase` first-create is not concurrency-safe under
  a DEFERRED DDL transaction. P3: production serialises creation via
  `mkdir(exist_ok=False)`. Resolve with S7 **Q29** — both touch the same three
  unserialised construction sites.

## Next bounded action (2026-07-27 — superseded, see above)

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
