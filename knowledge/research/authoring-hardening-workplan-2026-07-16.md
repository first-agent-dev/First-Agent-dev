# Authoring Guardrails Hardening — Comprehensive Workplan (This + Next Session)

**Date:** 2026-07-16
**Branch:** substrate @ 81b5487 + local fixes (1526 passed)
**Parent:** ADR-11 + Amendment 2026-07-15 I9 + tests-writing skill v1.1 + substrate workplans round2
**Goal lens:** Strengthen authoring-time admission so AI-authored harness features cannot pass `just check` while dormant/dead.
**Axes:** A noise-reduction (theater), C goal_lens-advancement (I9 + skill)
**Session type:** implement / authoring-guardrails hardening

---

## 0. Executive intent

Original substrate modernization showed **Stage C theater class**: code exists, unit green, docs say shipped, but `fa run` never calls it. Missing piece was mechanical DoD.

ADR-11-I9 locks DoD: **Harness done when composition-root test that boots real session path fails if production call site removed.**

This workplan hardens authoring module itself (old main module developed before new test-writing skill) and closes remaining Stage B/C gaps with C1, shared fixtures, dead-flag sweep, global stats consumer, parity/docs rules, and doc cleanup — all verifiable, without reopening dual-pyramid debate or introducing STATUS enums / allowlist files / new fs.* wiring-check tools / LLM judges in CI.

---

## 1. Current state — broad scope review (verifiable)

### 1.1 Authoring module — big picture wiring

**Files:**
- `src/fa/authoring_tcb.py` — Level-0 kernel, frozen stdlib-only, 400+ LOC, parses `.fa/session.toml` via tomllib, enumerates repo paths sorted, computes snapshot_id/kernel_hash/rule_pack_hash/session_hash, dispatches allowlisted Level-1 rules, sorts diagnostics (severity rank → code → path → line → message), emits JSON/text, exit 0/1 on HARD-BLOCK. Fail-closed: malformed manifest, unknown key, empty snapshot, rule crash → HARD-BLOCK.
- `src/fa/authoring_rules/__init__.py` — RULE_ALLOWLIST static tuple (EXPORTS_COMPLETENESS, TEST_SEMANTIC_DECAY, PLACEHOLDER_ASSERTION). No dynamic discovery. Append-only.
- `src/fa/authoring_rules/_scan.py` — shared file iteration + AST parse + scope filter (SRC_SCOPE, TEST_SCOPE) to keep rule packs DRY and satisfy duplicate-code gate.
- `src/fa/authoring_rules/exports.py` — V2 EXPORTS_COMPLETENESS, AST checks __all__ completeness (F-2, F-7). HARD-BLOCK.
- `src/fa/authoring_rules/tests.py` — V4 family (PYTEST-SKIP, NON-STRICT-XFAIL, FOCUS-MARKER) and V11 PLACEHOLDER_ASSERTION/CONTRADICTORY-ASSERT, AST checks test semantic decay, HARD-BLOCK.
- Future: `parity.py` (V3) + `docs.py` (V5) for PR3, `seam.py` (V6) + corpora for PR4, `messages.py` (V12) for PR5, `references.py` (V10), `ssot.py` (V7), `trailers.py` (V14).
- `catch-corpus/` — 6 fixtures: F-2, F-7, F-9, I-5-focus, I-5-skip, I-5-xfail (true positives rules must catch)
- `fp-corpus/` — 3 fixtures: pure-compare, skipif, strict-xfail (false positives rules must NOT flag)
- `scripts/check_protected_paths.py` — CI diff-checker for TCB paths, realpath-resolved denylist
- `.github/CODEOWNERS` + `.github/workflows/authoring-guardrails.yml` — always-run CI, no paths filter, per Hermes contributor-check pattern
- `.fa/session.toml` — session manifest source of truth for seam, session id, trailers
- `Makefile` / `justfile` — `check: lint typecheck authoring-check test` — authoring-check is authoritative, pre-commit is convenience

**Wiring big picture:**
- Author invokes `fa authoring-check` locally (or via `just check`). Kernel reads `.fa/session.toml`, enumerates repo, computes hashes, dispatches allowlist, emits diagnostics.
- CI workflow `authoring-guardrails.yml` always runs (no path skip), fails on HARD-BLOCK.
- Protected-path governance: CODEOWNERS + branch protection + required CI diff-check surfaces edits to TCB.
- Active consumers: diagnostics consumed by CI gate + human/agent reading output; session.toml consumed by seam.py (future) + commit-msg trailer injector; catch/fp corpora consumed by corpus test harness (future PR4).
- **Gap before new skill:** Main module developed long ago, has C0 unit tests for rules? Check `tests/test_corpus.py` exists. But lacked C1 for composition-root? Actually authoring-check itself is C2 CLI smoke, not C1 via drive_session. For authoring module, C1 would be boot via `fa authoring-check` CLI path? Need C2.
- After new skill: need to ensure authoring module has C1/C2 with kill-check: removing dispatch from RULE_ALLOWLIST fails test.

**Current state after rebase 81b5487:**
- `fa authoring-check` now 0 diagnostics (we fixed 8 exports completeness HARD-BLOCK)
- `just check` equivalent: lock-check pass, 1526 tests pass, authoring-check pass
- No STATUS enum, no wiring-allowlist.toml, no new fs.* tools — respects non-goals

### 1.2 Slices 1-5 code present vs promised (assessment)

| Slice | Promised (workplan) | Present now | Gap |
|---|---|---|---|
| Slice 1 unified DB authority | EventLog DB-first, Blackboard same DB, JSONL mirror-only, split-brain tests, no dual authority | `session_db.py` exists, EventLog append DB-first then mirror, read DB-first, Blackboard facade over same DB, `tests/test_session_db_authority.py` 13 tests, concurrent write test | Done, but verify no remaining `workspace/.fa/blackboard/session.db` hot-path creation — search shows only fallback compatibility in Blackboard.__init__ when session_db=None |
| Slice 2 observability | fs_usage/chronicle_search read active authority, no path guessing, explicit run_id | `observability.py` now DI via contextvar + run_id, `test_observability_runtime_authority.py` 6 tests | Done |
| Slice 3 Stage C | warn/stage2/stage3 distinct, dynamic threshold, compactor model reaches provider body, fallback 4-header, cache-control truth | `context_budget.py` has stage2_threshold, stage3_threshold distinct, warn 70%, `coder_loop.py` composes request_extras, anthropic system hoisting preserves cache_control structured, openai_compat forwards extras, compactor uses config.model, fallback returns 4 headers, `test_compaction_sota.py` + pr1/3/5 | Done, flag honesty: compaction_enabled defaults False, so Stage3 tests use matrix B full cascade, not C defaults — documented |
| Slice 4 governance | PinnedBuffer vs mutable resume, stale pin cleared, hash honest | `cli.py` routes resume to initial_memory_summary, `pinned_buffer.py` refresh replaces cache wholesale + warns on disappearance/change, `coder_loop.py` merges resume + rebuilt summary | Done |
| Slice 5 subagent | role fidelity, spawn limit, env, safety equivalence, lifecycle, observability | `subagent_runner.py` role preserved (researcher vs verifier), spawn limit respects FF > RuntimeLimits, env injection with secret filter, sandbox checks via HookRegistry (SandboxHook, SecretGuard, IntentGuard) dispatched BEFORE tool, spawn_start/done/fail events logged, worklog aggregation, PtyPool not used for subagent (stateless) | Partial: lifecycle termination (SIGTERM) test missing, shared-workspace conflict semantics not fully proven via audit trail test — need C1 test for termination |

### 1.3 Shared fixture — current state

- Created `tests/fixtures/session_wiring.py` with thin factories: `require_log`, `mock_success_response`, `mock_response_with_tools`, `make_tool_call`, `make_mock_chain`, `make_session_state`
- Gold tests `test_pr1..5_wiring.py` still have local copies of same helpers (duplication count 5+). Need to extract usage into them to reduce duplication per skill "extract-on-duplication after third copy".

### 1.4 More C1 for Stage B/C gaps

- `fs_list_tasks`, `fs_chronicle_search` — chronicle_search has C1 via observability_runtime_authority, list_tasks maybe only C0 (check). `fs_list_tasks` is observability, should have C1.
- `global_history` export has C1 via `test_global_history_export.py` (6 tests) but CLI reading `fa stats --global` absent — no derived consumer yet, violates AGENTS rule "every write target must have active consumer".

### 1.5 Dead flags sweep — FIND-018

- `FIND-018` says dead/partial flags and symbols remain in production tree.
- Examples: feature_flags with blackboard_enabled, telemetry_enabled, etc maybe still present but not used? Need inventory.
- Also `feature_flags` has `subagent_spawning_enabled` false default, but tool exists — is that dead? Not, it's gated.
- Also `context_budget_enabled`, `context_compaction_enabled` defaults? Need grep.

### 1.6 fa stats --global

- Global history DB exists at `~/.fa/global_history.db` after Slice 9, but `fa stats` currently only parses `~/.fa/session-log/*/events.jsonl`, not global db. No `fa stats --global` flag.
- Need to implement as derived consumer to satisfy active consumer rule.

### 1.7 Blueprint PR3 parity/docs — V3, V5

**Module explanation:**

- **Parity (V3) `parity.py`**: Borrowed from Archon pattern `generate --check`. For every committed generated or hand-mirrored artifact, record source-of-truth paths and fail when regenerated content differs. Example pair already live: `knowledge/skills/pr-creation/SKILL.md` ↔ `src/fa/hygiene/pr_intent.py` constants — FA seeds this in `tests/test_pr_intent_snapshot.py`. V3 would generalize: `SQUASH_MSG` Python ↔ Bash drift (F-3). Intent: prevent dual-location update fail. Not yet implemented as Level-1 rule pack, only snapshot test exists. Active consumer: CI gate fails on drift.

- **Docs (V5) `docs.py`**: Stale BACKLOG / missing `llms.txt` row (F-5, F-6). Checks doc integrity: BACKLOG.md milestone closed but blockers remain (line-level invariant), llms.txt not updated after new ADR. Intent: prevent index update omission. Not yet implemented, only blueprint.

Both are PR3 of blueprint rollout: parity + docs rules, after PR2 (exports + tests) which landed.

### 1.8 Doc cleanup — enormous amount of features shipping in this branch

Branch `substrate` shipped:
- Slice 0 contract freeze D8/D9/D10
- Slice 1 unified DB authority + session_db.py
- Slice 2 observability rewiring
- Slice 3 Stage C correctness (warn/stage2/stage3, cache-control, compactor model)
- Slice 4 governance plane repair (PinnedBuffer vs mutable resume)
- Slice 5 subagent hardening (role, limit, env, safety, events)
- Slice 6 bash + PTY truthfulness (artifact put, PtyPool wired, CR cleaning)
- Slice 7 scheduler/search residuals (denied preserved, instant_grep read-only)
- Slice 8 logging standardization (87 prints → logger)
- Slice 9 global_history.db export

Docs that need update:
- `knowledge/project-overview.md` §Four pillars + minimalism
- `knowledge/llms.txt` BY-DEMAND INDEX
- `knowledge/instructions/` human operator docs (01-install, 02-operations)
- `AGENTS.md` session protocol, working in repo, query routing
- `HANDOFF.md` current state
- `knowledge/adr/DIGEST.md`
- `README.md` top-level
- `knowledge/README.md` memory system overview

Many are outdated relative to new substrate features.

---

## 2. Task breakdown — 8 tasks on horizon

### Task 1 — Authoring module broad scope review + hardening per I9

**Intent:** Prevent dormant/dead authoring rules passing just check. Main module old.

**Correct & verifiable?**
- Correct because authoring module is TCB, must be failure-observable and have live-path DoD like other harness surfaces. Verifiable by ensuring `fa authoring-check` is invoked from composition root `drive_session`? Actually authoring-check is separate CLI, not session loop. For authoring module, C2 CLI smoke is appropriate DoD (per skill: shipped CLI session drivers for claims about those commands). So need C2 test that `fa authoring-check` fails if RULE_ALLOWLIST entry removed.
- Also need to verify Level-0 kernel determinism: snapshot_id, kernel_hash, rule_pack_hash stable, sorted diagnostics.

**Translation into code:**
- Review `authoring_tcb.py` for stdlib-only, fail-closed, deterministic sort.
- Review `authoring_rules/__init__.py` allowlist static, append-only, no dynamic discovery.
- Review `_scan.py` for shared logic, duplicate-code gate.
- Review `exports.py`, `tests.py` for AST, not regex, HARD-BLOCK.
- Add C2 test `tests/test_authoring_wiring.py`:
  - Boots `fa authoring-check` via `_cmd_authoring_check` or `build_parser` → `authoring-check` subcommand
  - Asserts HARD-BLOCK when fixture from catch-corpus is present
  - Asserts 0 diagnostics for clean tree
  - Kill-check: removing EXPORTS_COMPLETENESS from RULE_ALLOWLIST makes test fail to catch F-2 fixture

**Verification:**
- `fa authoring-check` green, `test_authoring_wiring.py` passes, kill-check by temporarily editing RULE_ALLOWLIST in test fails
- `just check` green

**File map:**
- New: `tests/test_authoring_wiring.py`
- Maybe: `tests/fixtures/authoring_fixtures.py` for catch-corpus helpers
- No edits to TCB itself unless drift found

**Done:** Authoring module has C2 with kill-check, docs explain wiring.

### Task 2 — Shared fixture extraction into gold tests

**Intent:** Reduce duplication per skill recommendation, make future C1 cheaper.

**Correct & verifiable:** Correct because skill says extract after third copy. Verifiable by counting duplication and ensuring gold tests still pass after using shared factory.

**Translation:**
- Refactor `tests/test_pr1_wiring.py` … `test_pr5_wiring.py`, `test_slice5_6_7_wiring.py`, `test_global_history_export.py` to import from `tests/fixtures/session_wiring.py`
- Keep local helpers only if unique

**Verification:**
- `pytest tests/test_pr1_wiring.py ... -q` still pass
- `grep -r "_require_log\|mock_success_response" tests/test_pr*_wiring.py` shows import not local definition

**File map:**
- Edit: `tests/test_pr1_wiring.py`, `test_pr2_wiring.py`, `test_pr3_wiring.py`, `test_pr4_wiring.py`, `test_pr5_wiring.py`, `test_slice5_6_7_wiring.py`, `test_global_history_export.py`
- Keep: `tests/fixtures/session_wiring.py`

**Done:** No more than 2 local copies of same mock helper.

### Task 3 — C1 for slices 1-5 code present vs promised + remaining B/C gaps

**Intent:** Close theater for slices 1-5 with explicit kill-check tests.

**Assessment already done in §1.2:**

- Slice 1: Already has `test_session_db_authority.py` 13 tests, but need C1 via drive_session that proves DB-first read? Existing pr tests maybe cover. Add C1 if missing: `test_slice1_wiring.py` that forces SQLite write failure and proves no stale authority.
- Slice 2: Has `test_observability_runtime_authority.py` 6 tests C1 via contextvar + EventLog, but need C1 via drive_session that appends usage row and checks `fs_usage` returns non-TBD? Could add.
- Slice 3: Has `test_compaction_sota.py` + pr1/3/5, but need provider-body cache-control test that inspects `RequestInfo.extras` reaches outbound JSON body — already in pr3? Check. Add if missing.
- Slice 4: Has pr2 wiring for pinned buffer reload, but need test that resume draft appears in mutable segment not pinned.
- Slice 5: We added C1 for role/env/limit but missing lifecycle termination test (parent SIGTERM → child cleanup) and shared-workspace audit trail test.

**Plus B/C gaps:**

- `fs_list_tasks` — currently only via observability tools, no C1 that proves DI via contextvar + active tasks listing.
- `fs_chronicle_search` — already C1.
- `global_history` CLI reading — see Task 6

**Translation:**
- Create `tests/test_slice1_2_4_wiring.py` etc or add to existing wiring suite `test_slice5_6_7_wiring.py` as separate file `test_slice1_5_wiring.py`
- Each test follows skill: drive_session root, matrix A/B/C, oracle event kind / outcome / provider call_count, kill-check docstring

**Verification:**
- Each new C1 fails if production call site removed (manual kill-check)
- `pytest tests/test_*wiring*.py -q` green

**File map:**
- New: `tests/test_slice1_5_additional_wiring.py`
- Edit: maybe `tests/test_pr*_wiring.py` to add missing matrices

### Task 4 — Close literal original Slice 10 task 6 (dead flags sweep) thin follow-up

**Intent:** Same as Task 5, but scoped to Slice 10 original literal.

**Translation:** Inventory dead/partial flags via grep `feature_flags` and `FeatureFlags` fields, check usage in code. Remove or deprecate.

**Verification:** `fa authoring-check` + `pytest` green, no dead flag referenced.

**Done:** FIND-018 residual closed.

### Task 5 — Verify presence and Remove/deprecate dead flags and symbols (FIND-018 drift)

**Intent:** Prevent drift where flag exists but never read, or symbol exported but not used.

**Correct & verifiable:**

- Correct because dead flags cause confusion, increase test matrix, and are theater (present but not wired).
- Verifiable by static analysis: grep flag name in `src/fa/` excluding definition, count 0 → dead.

**Translation:**
- Inventory `src/fa/feature_flags.py` all fields
- For each field, grep `src/fa` for `getattr.*<flag>` or direct attribute access
- If count 0 or only in tests, mark dead
- For each dead flag, either remove from FeatureFlags or document as deprecated and add to active consumer (e.g., future use)
- Same for symbols in `__all__` that are not imported anywhere? But exports completeness rule already enforces __all__ completeness, so dead symbols would be caught if not in __all__? Actually dead flags are not about __all__, but about feature flag fields.

**Verification:**
- Script `scripts/check_dead_flags.py` (optional) or manual grep proof in PR description
- `just check` green after removal
- No existing tests break that relied on dead flag

**File map:**
- Edit: `src/fa/feature_flags.py`, maybe `src/fa/inner_loop/tools/__init__.py`, `profiles.py`, etc.
- Tests: `tests/test_feature_flags.py` if exists

**Done:** No dead flag with zero production consumers.

### Task 6 — Implement `fa stats --global` reading `global_history.db` as derived consumer

**Intent:** Satisfy AGENTS rule #3 every write target must have active consumer. Currently global_history.db has write (export) but no reader besides tests. Need `fa stats --global` to be active consumer.

**Correct & verifiable:**

- Correct because derived projection needs consumer, otherwise it's dead write target.
- Verifiable by `fa stats --global` returning JSON/console with rows from global_history.db, and C2 test for CLI.

**Translation:**
- Edit `src/fa/stats.py` — add function `read_global_history(db_path)` that uses `GlobalHistoryStore.read_all()`
- Edit `src/fa/cli.py` `_cmd_stats` — add `--global` flag boolean, if true, read from global_history.db not session-log, render aggregate
- Add test `tests/test_stats_global_wiring.py` C2: creates global_history.db with known rows via GlobalHistoryStore, runs `_cmd_stats` with `--global` flag, asserts output contains run_ids

**Verification:**
- `fa stats --global --output json` prints JSON with runs array
- C2 test passes, kill-check: removing read from global_history.db makes test fail

**File map:**
- Edit: `src/fa/stats.py`, `src/fa/cli.py` (add --global arg)
- New: `tests/test_stats_global_wiring.py`
- No edits to hot-path authority

**Done:** `fa stats --global` exists as derived consumer, docs updated.

### Task 7 — Blueprint PR3 parity/docs rules (V3, V5) — explanation

**Intent:** Explain module to owner.

**Explanation:**

- **Parity V3** `parity.py`: Checks that two committed files that are supposed to be mirrors (generated or hand-mirrored) stay in sync. Example: `knowledge/skills/pr-creation/SKILL.md` says PR description must open with `INTENT: ...` + `INVARIANT:` + `DEGREE-OF-FREEDOM CLOSED:` etc., and `src/fa/hygiene/pr_intent.py` has constants `INTENT_LINE`, `INVARIANT_LINE` etc that mirror that spec. If skill doc changes but code constant not updated, parity fails. Currently implemented as snapshot test `tests/test_pr_intent_snapshot.py` that pins hook constants to skill text. As Level-1 rule, it would AST-parse both files and compare, HARD-BLOCK on drift.

- **Docs V5** `docs.py`: Checks doc integrity: `BACKLOG.md` milestone closed but blockers remain (line-level invariant), `llms.txt` not updated after new ADR (index update omission), `knowledge/README.md` etc. Intent: prevent docs drift. Example: When new ADR added under `knowledge/adr/`, `knowledge/adr/DIGEST.md` and `knowledge/llms.txt` and `knowledge/README.md` must be updated. Rule would parse those indexes and fail if missing row.

Both are PR3 of blueprint rollout: after PR2 (exports + tests) landed, next is parity + docs. They are **I-FROZEN** and **doc integrity** rules, not wiring tests. They have active consumers: CI gate fails on drift.

**Translation into code (if we were to implement PR3):**
- `src/fa/authoring_rules/parity.py` — Rule that reads `pr-creation/SKILL.md` and `pr_intent.py`, extracts required header lines via regex/AST, compares, returns RuleResult HARD-BLOCK if mismatch, with remediation.
- `src/fa/authoring_rules/docs.py` — Rule that enumerates `knowledge/adr/ADR-*.md`, checks `DIGEST.md` contains each, checks `llms.txt` BY-DEMAND INDEX contains new files, checks `BACKLOG.md` closed milestones have no open blockers.
- Add to `RULE_ALLOWLIST` in `__init__.py`
- Add fixtures to `catch-corpus/` (e.g., `SQUASH_MSG` Python vs Bash drift) and `fp-corpus/`

**Verification:**
- `fa authoring-check` catches drift fixture, passes clean tree
- `catch-corpus/F-3` etc

**File map for PR3 (future):**
- New: `src/fa/authoring_rules/parity.py`, `docs.py`
- Edit: `__init__.py` allowlist
- New corpus fixtures

**Done for this task (explanation only):** Owner understands module, decides if we should implement PR3 in this session or defer to next.

### Task 8 — Documentation/cleanup for all features shipping in this branch

**Intent:** Update human and agent facing artifacts for enormous amount of features shipped in substrate branch (Slices 0-9 + authoring hardening).

**Correct & verifiable:**

- Correct because docs out of date cause onboarding failure and theater (docs claim shipped but operator doesn't know).
- Verifiable by link integrity check `markdown-link-check` hook and `fa authoring-check` + `just check` green.

**Translation:**

- `knowledge/project-overview.md` — update §Four pillars, §Minimalism, §Stage C description to reflect unified DB, PinnedBuffer vs mutable resume, Stage C ladder 70/80/90 distinct, cache-control truth, PTY stateful, subagent narrow, global history projection
- `knowledge/llms.txt` — BY-DEMAND INDEX: add new files `session_db.py`, `global_history.py`, `fixtures/session_wiring.py`, `test_slice5_6_7_wiring.py`, `test_global_history_export.py`, `pty_pool.py` resolve_cr, update bucket/line counts
- `knowledge/instructions/01-install.md` and `02-operations.md` — document `fa stats --global`, PTY persistence, `global_history.db` location, `fa authoring-check` I9, `tests-writing` skill
- `AGENTS.md` — update session protocol if changed, working in repo section, query routing for new modules
- `HANDOFF.md` — overwrite §Current state with new truth (substrate Slices 0-9 landed, I9 hardening landed, next is doc cleanup + PR3), rewrite §Next
- `knowledge/adr/DIGEST.md` — ensure I9 one-liner present, add Slice 9 global_history entry
- `README.md` — update top-level description of First-Agent as most token-efficient + now has unified DB + global history
- `knowledge/README.md` — update memory system overview with new research notes

**Verification:**
- `uv run python -m fa.hygiene.hooks.status` (or `just hooks-status`) — hooks installed
- `fa authoring-check` — 0 diagnostics
- `markdown-link-check` pre-commit hook — no broken inbound refs
- `just check` — green

**File map:**
- Edit: many docs files
- No new non-goal artifacts

**Done:** All docs link integrity green, human can onboard and understand substrate features.

---

## 3. Execution order & dependencies

Risk-first, then dependency:

1. **Task 1** authoring module review (read-only, no code change, produces understanding) — can run first
2. **Task 7** explain parity/docs — read-only, can run parallel to 1
3. **Task 4+5** dead flags sweep — needs inventory, low risk, can run after 1
4. **Task 2** shared fixture extraction — needs 1 to know duplication count, low risk
5. **Task 3** more C1 for slices 1-5 + B/C gaps — depends on 2 (fixture ready), needs code present assessment
6. **Task 6** fa stats --global — depends on Slice 9 done (done), needs active consumer, low risk, can run after 3
7. **Task 8** doc cleanup — depends on all above being landed, so last, enormous
8. **Task 3 continued** — after doc cleanup, final `just check` green

Recommended order for this session (thin slices):

- Step A: Tasks 1+7 (review + explain, no code, 30 min) — produces this workplan + understanding
- Step B: Tasks 4+5 (dead flags inventory + removal, 1h) — thin, verifiable via grep
- Step C: Task 2 (fixture extraction into gold tests, 1h) — refactor tests, verify green
- Step D: Task 3 (additional C1 for slices 1-5, list_tasks, etc, 2h) — add 3-5 new C1 tests
- Step E: Task 6 (fa stats --global, 1h) — implement reader + CLI flag + C2 test
- Step F: Task 8 (doc cleanup, 3h) — update all docs, link check

Next session with other agent:

- Continue doc cleanup if enormous
- Implement Blueprint PR3 parity/docs rules (if owner wants)
- Mutation clearing after C1 (C4)
- Final hostile re-audit (Slice 10 original anti-theater)

---

## 4. Verification discipline (per slice)

- V1 static proof: exact symbols changed, paths changed, grep proof for removed ambiguity
- V2 runtime proof: focused C1 integration test that boots real root (drive_session or cli)
- V3 failure proof: intentional failure path (e.g., unwritable DB, denied shell, missing pin)
- V4 no-regression: narrowest relevant existing suite + new tests
- V5 anti-theater: does test stop too early? does it inspect only mocks/intermediate? would bug still pass if provider/DB boundary wrong? If yes, insufficient.

---

## 5. What must be true before we can claim authoring guardrails hardened

1. `fa authoring-check` 0 diagnostics on clean tree
2. C1 tests exist for every product surface claimed as shipped in substrate (DB authority, observability, Stage C, governance, subagent, bash/PTY, scheduler/search, global export)
3. Each C1 has kill-check and fails if call site removed
4. Shared fixture extracted, no more than 2 local copies of same mock helper
5. No dead flag with zero production consumers
6. `fa stats --global` exists as active consumer for global_history write target
7. Docs updated for all shipped features, link integrity green
8. `just check` green (lock, lint, typecheck, authoring-check, test)

---

## 6. Non-goals for this hardening wave (locked)

- STATUS LIVE/EXPERIMENTAL enums
- wiring-allowlist.toml bureaucracy
- New inner-loop tools fs.* for wiring checks
- CodeGraph / repo-intel as merge gate
- LLM-as-judge in every-PR CI
- Making human commit-msg as strict as IntentGuard
- Replacing ADR-11 blueprint PR3+ Level-1 packs with I9 alone
- Full UC5 eval platform

---

## 7. Risks

- Doc cleanup enormous, may introduce link drift — mitigate via markdown-link-check hook + incremental PR
- Dead flag removal may break tests that relied on flag — mitigate via grep and running full suite after each removal
- Shared fixture extraction may cause type-checker errors (Optional log) — mitigate via _require_log pattern from gold files
- fa stats --global may be confused with per-run stats — document clearly

---

## 8. Where we stopped — context for next agent

**As of 2026-07-16 09:00 UTC:**

- Branch substrate @ 81b5487 + local fixes:
  - Slices 0-4 done (DB authority, observability, Stage C, governance)
  - Slices 5-7 done (subagent hardening, bash/PTY truthfulness, scheduler/search) — 8 new C1 tests in test_slice5_6_7_wiring.py
  - Slice 8 logging: 87 print WARNING → logger.warning, fa authoring-check 0
  - Slice 9 global_history.db export: schema + store + cli wiring + 6 tests, 1526 tests pass (was 1520)
  - Authoring-check drift fixed: exports completeness HARD-BLOCK 8 → 0
  - Shared fixture tests/fixtures/session_wiring.py created

- New files present (untracked or modified):
  - src/fa/inner_loop/global_history.py (new)
  - src/fa/inner_loop/tools/run_bash.py (binary capture, CR cleaning, workspace guard)
  - src/fa/runtime/pty_pool.py (resolve_cr, stateful vs exit handling)
  - src/fa/inner_loop/state.py (auto-create PtyPool)
  - src/fa/inner_loop/loop.py (denied preserved)
  - src/fa/inner_loop/tools/instant_grep.py (read-only)
  - src/fa/inner_loop/subagent_runner.py (role/env/limit, logger)
  - src/fa/inner_loop/subagent_envelope.py (role param)
  - src/fa/inner_loop/tools/spawn_subagent.py (env schema, events)
  - src/fa/cli.py (PtyPool wiring, global_history export, duration)
  - tests/test_slice5_6_7_wiring.py (new, 8 C1)
  - tests/test_global_history_export.py (new, 6 tests)
  - tests/fixtures/session_wiring.py (new)
  - knowledge/research/* slice closure docs

- Remaining open from workplan:
  - Slice 10 literal task 6 dead flags sweep — inventory done partially, removal not started (FIND-018)
  - More C1 for slices 1-5 (code present vs promised assessment done in §1.2, but additional C1 not yet added beyond existing)
  - fs_list_tasks C1 missing
  - fa stats --global not implemented (Task 6)
  - Blueprint PR3 parity/docs rules not implemented (Task 7 explanation done, code not)
  - Doc cleanup enormous (Task 8) — not started

- Next agent should start at Task 4/5 dead flags inventory (thin) or Task 2 fixture extraction into gold tests (thin), then Task 3 additional C1, then Task 6 stats --global, then Task 8 docs.

- Verify presence: `fa authoring-check` currently 0, `pytest -q --ignore pty_persistence` 1526 passed, `uv lock --locked` pass.

---

## 9. Explicit file edit map for next steps (thin)

**Task 4/5 dead flags:**
- Read `src/fa/feature_flags.py` fields, grep usage
- Edit `src/fa/feature_flags.py` (remove dead), `src/fa/inner_loop/tools/__init__.py` (if flag controls registration)

**Task 2 fixture extraction:**
- Edit `tests/test_pr1_wiring.py`, `test_pr2_wiring.py`, `test_pr3_wiring.py`, `test_pr4_wiring.py`, `test_pr5_wiring.py` to import from `tests.fixtures.session_wiring`

**Task 3 more C1:**
- New `tests/test_slice1_5_additional_wiring.py` + `tests/test_list_tasks_wiring.py`

**Task 6 stats --global:**
- Edit `src/fa/stats.py` (add read_global_history), `src/fa/cli.py` (add --global flag)

**Task 8 docs:**
- Edit `knowledge/project-overview.md`, `knowledge/llms.txt`, `knowledge/instructions/*`, `AGENTS.md`, `HANDOFF.md`, `knowledge/adr/DIGEST.md`, `README.md`

---

## 10. Final note

This workplan is intentionally heavier than normal feature plan because failure mode is partial reality: features exist just enough to look landed while failing under live boundary.

Optimize for fewer moving parts, stronger authority boundaries, honest contracts, end-to-end proofs. That is shortest path to trustworthy substrate and authoring guardrails that prevent recurrence.

