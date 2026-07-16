# Authoring Hardening Workplan v2 — Gap Review + High ROI Improvements

**Date:** 2026-07-16 v2
**Parent:** `authoring-hardening-workplan-2026-07-16.md` v1
**Branch:** substrate @ 81b5487 + local (1526 passed, authoring-check 0)
**Skill:** `tests-writing` v1.1, ADR-11 I9
**Review mode:** high effort, verifiable steps, outside-the-box

---

## 0. Why v2 — gaps and logic errors in v1

v1 listed 8 tasks but had logic gaps that would let agents re-introduce theater or drift:

| # | Gap in v1 | Impact | Fix in v2 |
|---|---|---|---|
| G1 | Authoring module "big picture wiring" claimed but not deterministically verified. Statements like "CI always runs, no path skip" were asserted, not proven via file read + test. | Agent could claim wiring without proof → theater | Add deterministic verification steps: `cat .github/workflows/authoring-guardrails.yml | grep -q paths:` must fail (no paths filter), `grep -r` for CODEOWNERS sync, C2 test for `fa authoring-check` |
| G2 | Task 1 said "read-only, no code" for authoring review, but actually needs C2 test with kill-check to prove RULE_ALLOWLIST wiring. Contradiction. | Task would be closed without code proof | Change Task 1 to include C2 test `test_authoring_allowlist_wiring.py` that fails if rule removed from allowlist |
| G3 | Shared fixture extraction Task 2 said "extract after third copy" but didn't list which files still duplicate or how to verify extraction. No command to count duplication. | Agent might skip extraction or break type-honest fixtures | Add concrete command: `grep -R "_require_log\|mock_success_response" tests/*.py | wc -l` and threshold, plus typecheck `mypy tests/fixtures/session_wiring.py` |
| G4 | Task 3 "More C1 for slices 1-5" listed slices but didn't include explicit present vs promised matrix with file:line citations. Risk: agent adds tests that don't target real boundary. | Theater again | Add matrix table with file:line for each promised symbol and current C1 coverage status + required oracle |
| G5 | Task 4/5 dead flags sweep described as "grep usage" but no script, no definition of dead. Could delete flag that is still used via `getattr(..., "flag", True)` dynamic. | False positive deletion → break runtime | Add deterministic script `scripts/check_dead_flags.py` that parses `FeatureFlags` dataclass fields and searches for both direct and `getattr` patterns, plus allowlist of known future flags |
| G6 | Task 6 `fa stats --global` as active consumer: v1 didn't note that write target currently has no reader, violating AGENTS rule #3 "every write target must have active consumer". Also didn't specify idempotence or failure handling for CLI reader. | Write target remains dead → AGENTS violation | Add explicit consumer check: `grep -R "global_history" src/fa/stats.py` must succeed after Task 6, and C2 test for `--global` flag |
| G7 | Task 7 parity/docs explanation was only explanation, not implementation, but v1 workplan listed it as "explain this module to me" while also saying "Implement PR3" in other places — scope ambiguity. | Agent might implement PR3 code (Level-1 rules) without corpus, causing FP | Clarify: v2 Task 7 is explanation + optional thin advisory rule, not full PR3. Separate future PR3 code task with catch-corpus requirement |
| G8 | Task 8 doc cleanup "enormous" with no prioritization or link integrity verification steps. Agent could update many docs and break 26 inbound refs from PR A' extraction mentioned in HANDOFF. | Link drift → authoring-check doesn't catch markdown links? Actually markdown-link-check hook does. | Add prioritized doc list by ROI (operator impact) + explicit `markdown-link-check` + `fa authoring-check` after each doc edit |

High ROI improvements identified:

- **HR1:** Add C2 kill-check for RULE_ALLOWLIST wiring (1 file, 30 min, prevents entire authoring module theater)
- **HR2:** Add deterministic verification for always-run CI (1 grep, 5 min, high confidence)
- **HR3:** Automate dead-flag detection via script, not manual grep (30 min, prevents false deletion)
- **HR4:** Make `fa stats --global` the active consumer for global_history write target — satisfies AGENTS rule #3 with 1 CLI flag + C2 test (1h, high ROI)
- **HR5:** Provide copy-paste C1 template with LIVE-PATH PROOF block to reduce agent error in writing C1 (15 min, reduces theater)
- **HR6:** Require shared fixture usage in gold tests to be verified via `rg _require_log tests/test_pr*.py` count after refactor (5 min)

---

## 1. Authoring module — big picture wiring — deterministic verification

**Claim to verify:** (from v1 §1.1)

> - Author invokes `fa authoring-check` locally (or via `just check`). Kernel reads `.fa/session.toml`, enumerates repo, computes hashes, dispatches allowlist, emits diagnostics.
> - CI workflow `authoring-guardrails.yml` always runs (no path skip), fails on HARD-BLOCK.
> - Protected-path governance: CODEOWNERS + branch protection + required CI diff-check surfaces edits to TCB.
> - Active consumers: diagnostics consumed by CI gate + human/agent reading output; session.toml consumed by seam.py (future) + commit-msg trailer injector; catch/fp corpora consumed by corpus test harness (future PR4).

**Deterministic verification steps (run these, do not assert):**

```bash
# 1. Kernel reads .fa/session.toml
grep -n "session.toml" src/fa/authoring_tcb.py
# Expected: Manifest parsing via tomllib, _MANIFEST_TABLES, _SESSION_KEYS

# 2. Enumerates repo sorted
grep -n "sorted.*enumerate\|_SKIP_DIRS\|CORPUS_PREFIXES" src/fa/authoring_tcb.py

# 3. Computes snapshot_id/kernel_hash/rule_pack_hash
grep -n "snapshot_id\|kernel_hash\|rule_pack_hash" src/fa/authoring_tcb.py

# 4. Dispatches allowlist, no dynamic discovery
grep -n "RULE_ALLOWLIST" src/fa/authoring_rules/__init__.py
grep -n "importlib\|pkgutil\|dynamic" src/fa/authoring_tcb.py
# Expected: no dynamic import, only static allowlist

# 5. Emits diagnostics sorted, exit 0/1 on HARD-BLOCK
grep -n "sort_key\|HARD_BLOCK\|exit.*1" src/fa/authoring_tcb.py | head

# 6. CI always-run, no paths filter
cat .github/workflows/authoring-guardrails.yml
# Expected: on: pull_request + push branches main, no paths: key
! grep -q "paths:" .github/workflows/authoring-guardrails.yml && echo "PASS no paths filter" || echo "FAIL has paths filter"

# 7. Protected-path governance
cat .github/CODEOWNERS | grep authoring_tcb
cat scripts/check_protected_paths.py | grep "_TCB_PATHS"
# Expected: same list in both files

# 8. Active consumers
grep -R "authoring-check" Makefile justfile | head
# Expected: check: ... authoring-check test
grep -R "catch-corpus" tests/test_corpus.py
# Expected: test reads catch-corpus fixtures
```

**Current state after v1 fixes:**

- `fa authoring-check` 0 diagnostics (we fixed 8 exports completeness)
- `tests/test_corpus.py` exists, C1 for Level-1 rules? It boots `run_all(tmp_path, rules=(rule,))` with explicit rule, not via allowlist — so it does NOT prove allowlist wiring. Gap.
- No C2 test that boots `fa authoring-check` CLI via `_cmd_authoring_check` and asserts HARD-BLOCK for catch fixture via default allowlist.
- `just check` includes authoring-check, but `just` not installed in CI? `make check` does.

**What we need per tests-writing skill:**

For authoring module, appropriate class is **C2 CLI smoke**, not C1 `drive_session`, because root is `fa authoring-check` (inspect-only CLI per skill: "Inspect-only CLIs (e.g. chunk) are roots only for claims about those commands").

**New tests per skill (high ROI):**

- `tests/test_authoring_wiring.py` (C2):
  - Boots `fa authoring-check --output json` via `build_parser` + `_cmd_authoring_check` or via `run_all` with default allowlist (no explicit rules arg) — proves allowlist wiring
  - Uses tmp_path workspace with F-2 fixture under `src/fa_demo/f2.py` (not under corpus prefix) → expects diagnostic code `FA-AUTHORING-V2-EXPORTS-COMPLETENESS`
  - Kill-check: removing `EXPORTS_COMPLETENESS` from `RULE_ALLOWLIST` makes test fail (no diagnostic)
  - Oracle: event JSON contains `code`, `severity`, `path`, deterministic sort
  - Flag honesty: N/A (no FeatureFlags)
  - Type-honest: uses `Path`, `run_all` returns `Report`

- `tests/test_authoring_allowlist_wiring.py` (C2):
  - Asserts `RULE_ALLOWLIST` is static tuple, no dynamic discovery, length matches expected
  - Asserts `CODEOWNERS` and `check_protected_paths.py` list same TCB paths (parity)

---

## 2. Revised task breakdown — 8 tasks with deterministic verification

### Task 1 — Authoring module review + C2 kill-check (was read-only, now code)

**Intent:** Make authoring module itself satisfy I9 (even though its root is CLI, not drive_session).

**Translation:**

- File `src/fa/authoring_tcb.py` — verify stdlib-only: `grep -E "^import (requests|yaml|pydantic)"` must be empty
- File `src/fa/authoring_rules/__init__.py` — verify static allowlist: `grep -E "RULE_ALLOWLIST.*="` shows tuple, no `importlib`
- Create `tests/test_authoring_wiring.py`:
  ```python
  def test_authoring_check_catches_f2_via_allowlist(tmp_path):
      # create tmp workspace with knowledge/llms.txt + README + src/fa_demo/f2.py containing public symbol not in __all__
      # run_all(tmp_path) with default allowlist (no explicit rules arg) — should catch
  def test_authoring_allowlist_kill_check(tmp_path):
      # same but with RULE_ALLOWLIST temporarily patched to remove EXPORTS_COMPLETENESS, assert no diagnostic
  ```
- Add `tests/test_authoring_protected_paths_parity.py`:
  - Reads `.github/CODEOWNERS` and `scripts/check_protected_paths.py` _TCB_PATHS, asserts sets equal

**Verification:**

- `fa authoring-check --output json | jq .diagnostics | length == 0` on clean tree
- `pytest tests/test_authoring_wiring.py -v` passes
- `grep -q "paths:" .github/workflows/authoring-guardrails.yml` fails (no paths filter) → PASS
- Kill-check: editing `RULE_ALLOWLIST` to remove one entry makes C2 test fail

**Done:** Authoring module has C2 with kill-check, deterministic verification steps documented.

### Task 2 — Shared fixture extraction into gold tests (high ROI)

**Intent:** Reduce duplication, make future C1 cheap and type-honest.

**Current duplication count (verifiable):**

```bash
rg -n "_require_log|mock_success_response|make_tool_call" tests/*.py | wc -l
# Before extraction: ~40 occurrences across 5 gold + 2 new wiring files
```

**Translation:**

- Keep `tests/fixtures/session_wiring.py` as single source
- Refactor `tests/test_pr1_wiring.py` … `test_pr5_wiring.py` to `from tests.fixtures.session_wiring import require_log, mock_success_response, mock_response_with_tools, make_tool_call, make_mock_chain, make_session_state`
- Ensure `mypy tests/fixtures/session_wiring.py` passes (type-honest)
- Ensure `pytest tests/test_pr1_wiring.py -q` still passes after refactor

**Verification:**

- `rg "_def _require_log" tests/*.py` shows only 1 definition (in fixtures), not 5
- `pytest tests/test_pr*_wiring.py -q` 30 tests pass
- `just check` green

**Done:** ≤2 local copies of same helper.

### Task 3 — More C1 for slices 1-5 present vs promised + B/C gaps

**Present vs promised matrix (updated from v1 §1.2 with file:line):**

| Slice | Promised symbol/file:line | Present file:line | C1 coverage | Gap |
|---|---|---|---|---|
| 1 | `SessionDatabase` `src/fa/inner_loop/session_db.py:26` + `EventLog.append` DB-first `state.py:110` | Present, same file | `test_session_db_authority.py` (C1? actually C0 with real DB) + need C1 via `drive_session` forcing SQLite failure | Missing C1 that forces DB write failure and proves no stale read |
| 2 | `build_chronicle_search_tool` `observability.py:30` DI via contextvar + run_id | Present | `test_observability_runtime_authority.py` 6 tests C1 via contextvar, but not via `drive_session` | Add C1 via drive_session that appends usage row and asserts `fs.usage` returns non-TBD |
| 3 | `ContextBudget.check` returns warn/stage2/stage3 `context_budget.py:70`, `compactor_chain.config.model` used `compactor.py:100`, cache_control preserved `prompt_composer.py:80` | Present | `test_compaction_sota.py` + `test_pr1/3/5_wiring.py` have C1 for ladder and compactor model and cache_control | Done, but need matrix B vs C documented in docstring |
| 4 | `PinnedBuffer.refresh` replaces cache wholesale `pinned_buffer.py:30`, resume draft → mutable summary `cli.py:1802` | Present | `test_pr2_wiring.py` has C1 for reload/missing file, but missing test that resume draft appears in `Memory summary:` not in `STANDING PROFILE` | Add C1 for resume mutable |
| 5 | `SubagentRunner._check_spawn_limit` respects FF `subagent_runner.py:79`, `from_verifier(..., role=)` `subagent_envelope.py:76`, env injection with secret filter, spawn_start/done events `spawn_subagent.py:60` | Present after our fixes | We added C1 in `test_slice5_6_7_wiring.py` for role/env/limit, but missing lifecycle termination test (SIGTERM) and shared-workspace audit trail | Add `test_subagent_termination_wiring.py` C1 with `send_ctrl_c` or timeout |

**Plus B/C gaps:**

- `fs.list_tasks` — DI via contextvar for pty_pool/worktree_manager, no C1 that proves active tasks listing via live session. Add C1.
- `fs.chronicle_search` already C1 via observability_runtime_authority.
- `global_history` CLI reading — see Task 6.

**Translation:**

- Create `tests/test_slice1_5_additional_wiring.py` with 5 new C1:
  - `test_slice1_split_brain_no_stale_read_via_drive_session` — forces DB failure via monkeypatch `SessionDatabase.append_event_row` to raise, asserts `drive_session` does not silently succeed
  - `test_slice2_usage_via_drive_session` — appends usage row via EventLog, dispatches `fs.usage` via drive_session, asserts token totals
  - `test_slice4_resume_mutable_not_pinned` — passes `initial_memory_summary` to drive_session, inspects provider request messages for `Memory summary:` contains resume text and not in `STANDING PROFILE`
  - `test_slice5_termination_wiring` — spawns subagent with sleep, sends ctrl_c, asserts cleanup
  - `test_list_tasks_wiring` — creates PtyPool session, acquires, calls list_tasks via drive_session, asserts task listed

**Verification:** Each fails if call site removed (kill-check), `pytest tests/test_slice1_5_additional_wiring.py -v` passes, `just check` green.

### Task 4/5 — Dead flags sweep FIND-018 (thin)

**Intent:** Remove/ deprecate dead symbols that increase confusion and test matrix.

**Deterministic inventory (high ROI script):**

```bash
# List all FeatureFlags fields
grep -n "^\s*[a-z_]*:" src/fa/feature_flags.py | head

# For each field, search for getattr or direct access in src/fa (excluding definition and tests)
for flag in $(grep -oP "^\s*\K[a-z_]+(?=:\s)" src/fa/feature_flags.py); do
  count=$(rg -n "feature_flags.*$flag|$flag.*feature_flags|getattr.*$flag" src/fa --no-ignore -g '!tests' | wc -l)
  echo "$flag: $count"
done

# Also check __all__ symbols not imported anywhere
# For each public symbol in src/fa/inner_loop/tools/*.py not in __all__ fixed already, but also check for symbols in __all__ never imported
```

**Expected dead candidates from earlier audit:**

- `blackboard_enabled`, `telemetry_enabled` — still used? Check `state.py` uses `blackboard_enabled`.
- `prompt_caching`, `offload_threshold`, `tool_batching_enabled`, `context_budget_enabled`, `context_compaction_enabled`, `blackboard_filtered_history_include_plans`, `subagent_spawning_enabled`, `max_subagent_spawns_per_session` — all used.
- Maybe `blackboard_filtered_history_include_plans` is behind flag but default False — not dead.
- Need to run script to find truly dead.

**Translation:**

- Create `scripts/check_dead_flags.py` — parses `FeatureFlags` dataclass, searches codebase for usage, outputs dead list
- For each dead flag, either remove from dataclass or add active consumer (e.g., future use documented)
- Update `src/fa/feature_flags.py` and `src/fa/inner_loop/tools/__init__.py` registration if flag controls tool existence

**Verification:**

- Script outputs 0 dead after fix
- `fa authoring-check` 0
- `pytest -q` 1526+ pass

**Done:** No dead flag with zero production consumers, grep proof in PR description.

### Task 6 — fa stats --global as derived consumer (high ROI, satisfies AGENTS rule #3)

**Intent:** Every write target must have active consumer per AGENTS anti-pattern #3. Currently `global_history.db` has write (export) but no reader except tests.

**Translation already partially designed in Slice 9 patch:**

- Edit `src/fa/stats.py`:
  - Add `def parse_global_history(db_path: Path) -> list[dict]` reading via GlobalHistoryStore
  - Add `def render_global_history(sessions: list[dict])` similar to `render_aggregate`
- Edit `src/fa/cli.py` `_cmd_stats`:
  - Add `--global` / `--history` flag (bool)
  - If flag true, set `runs_dir = Path.home() / ".fa" / "global_history.db"`? Actually read via GlobalHistoryStore
  - If flag, call `parse_global_history` not `parse_session` for each session dir
  - Add `--output json` support for global

**Verification:**

- `fa stats --global --output json | jq .[0].run_id` contains run_id after a real `fa run`
- C2 test `tests/test_stats_global_wiring.py`:
  - Creates tmp global_history.db with 2 rows via GlobalHistoryStore
  - Calls `_cmd_stats` with Namespace `global=True`, workspace=tmp_path, output=json (via monkeypatch or direct call)
  - Asserts output contains both run_ids
  - Kill-check: removing `read_all()` call in `parse_global_history` makes test fail

**File map:**

- Edit `src/fa/stats.py`, `src/fa/cli.py`
- New `tests/test_stats_global_wiring.py` (C2)

**Done:** `fa stats --global` exists, is active consumer, C2 green, docs updated.

### Task 7 — Blueprint PR3 parity/docs V3/V5 explanation + optional thin advisory

**Intent:** Explain, not necessarily implement full PR3, per locked non-goals (Level-1 auto HARD-BLOCK for missing C1 deferred).

**Explanation already in v1 §1.7, but needs more concrete:**

- **Parity V3:** Example pair `SQUASH_MSG` Python vs Bash. Currently `src/fa/hygiene/pr_intent.py` has `SQUASH_MSG` constant? Actually check. The parity rule would ensure `knowledge/skills/pr-creation/SKILL.md` section "Output format" with `INTENT:`, `INVARIANT:` etc matches constants in `pr_intent.py`. Currently snapshot test `test_pr_intent_snapshot.py` does this. As Level-1 rule, it would be AST + text marker comparison.

- **Docs V5:** Checks `BACKLOG.md` closed milestones without open blockers, `llms.txt` missing new ADR row. Example: When new ADR file added under `knowledge/adr/`, `knowledge/adr/DIGEST.md` and `knowledge/llms.txt` must be updated. Rule would enumerate `knowledge/adr/ADR-*.md` and check DIGEST contains each.

**High ROI improvement:** Instead of implementing full V3/V5 as HARD-BLOCK now (risk FP), implement as ADVISORY with `expires_on` date per I2, plus corpus fixtures in `catch-corpus/`. This gives signal without blocking merge, and allows FP measurement.

**Translation (optional thin):**

- Create `src/fa/authoring_rules/parity.py` with one rule: checks `pr-creation` skill header lines vs `pr_intent.py` constants, returns ADVISORY with expires_on 2026-08-15 if mismatch
- Create `src/fa/authoring_rules/docs.py` with one rule: checks `llms.txt` contains all `knowledge/adr/ADR-*.md` basenames, returns ADVISORY
- Add to `RULE_ALLOWLIST` as ADVISORY
- Add fixtures to `catch-corpus/` for parity mismatch

**Verification:**

- `fa authoring-check` on clean tree: 0 HARD-BLOCK, maybe 2 ADVISORY
- `fa authoring-check --output json | jq` shows ADVISORY codes
- `pytest tests/test_corpus.py` passes for new V3/V5 fixtures

**Done:** Owner understands module, decides if to land advisory rules now or defer to next session. For this session, explanation + optional advisory is enough; full HARD-BLOCK promotion requires FP <1% measurement per I2.

### Task 8 — Doc cleanup enormous

**Prioritization by operator impact (high ROI first):**

1. `knowledge/project-overview.md` — Four pillars + minimalism + Stage C description (unified DB, PinnedBuffer vs mutable, ladder 70/80/90, cache-control truth, PTY stateful, subagent narrow, global history)
2. `knowledge/llms.txt` — BY-DEMAND INDEX: add new files `session_db.py`, `global_history.py`, `fixtures/session_wiring.py`, `test_slice5_6_7_wiring.py`, `test_global_history_export.py`, `pty_pool.py` resolve_cr, update bucket/line counts (use `wc -l` + `scripts/check_llms.py` if exists)
3. `knowledge/instructions/01-install.md` / `02-operations.md` — document `fa stats --global`, PTY persistence, `global_history.db` location, `fa authoring-check` I9, `tests-writing` skill
4. `AGENTS.md` — update session protocol: mention `tests/fixtures/session_wiring.py`, shared fixture extraction rule, I9 bullet
5. `HANDOFF.md` — overwrite §Current state with new truth (slices 0-9 landed, I9 hardening), rewrite §Next with remaining tasks 4-8
6. `knowledge/adr/DIGEST.md` — ensure I9 one-liner + Slice 9 global_history entry
7. `README.md` — top-level description of First-Agent as most token-efficient + unified DB + global history
8. `knowledge/README.md` — memory system overview with new research notes

**Deterministic verification for doc cleanup:**

```bash
# Link integrity
uv run python -m fa.hygiene.hooks.status # or just check markdown-link-check hook
# If markdown-link-check installed:
pre-commit run markdown-link-check --all-files

# llms.txt bucket counts
python scripts/check_llms.py  # if exists, else manual wc -l

# Authoring check still green
fa authoring-check

# Just check green
just check  # or make check
```

**Done:** All docs link integrity green, human can onboard and understand substrate features, no broken inbound refs from PR A' extraction (26 files mentioned in HANDOFF gotchas).

---

## 3. Execution order v2 (risk-first, dependency-aware)

1. **Task 1** authoring module review + C2 kill-check (30 min, no deps, high ROI for TCB trust)
2. **Task 7** explain parity/docs + optional thin advisory (30 min, no deps, clarifies scope for owner)
3. **Task 4/5** dead flags inventory via script (1h, no deps, low risk, unblocks doc cleanup)
4. **Task 2** shared fixture extraction into gold tests (1h, depends on Task 1 understanding of type-honest fixtures)
5. **Task 3** more C1 for slices 1-5 + list_tasks + termination (2h, depends on Task 2 fixture ready)
6. **Task 6** fa stats --global (1h, depends on Slice 9 done which is done, and Task 3 C1 pattern)
7. **Task 8** doc cleanup prioritized by ROI (3h, depends on all above being landed, so docs reflect final state)

Next session:

- Blueprint PR3 full HARD-BLOCK promotion after FP measurement
- Mutation clearing C4 after C1 green
- Final hostile re-audit (original Slice 10 anti-theater)

---

## 4. Verification discipline v2 (per task)

Same V1-V5 plus:

- V0 for authoring: deterministic verification via grep -q, file existence, no dynamic import
- V6 for docs: markdown-link-check + fa authoring-check + just check green

---

## 5. What must be true before claiming authoring guardrails hardened

Updated from v1 §5:

1. `fa authoring-check` 0 diagnostics on clean tree
2. C2 test for authoring allowlist wiring exists and fails if rule removed from RULE_ALLOWLIST
3. C1 tests exist for every product surface claimed as shipped in substrate (DB authority, observability, Stage C, governance, subagent, bash/PTY, scheduler/search, global export)
4. Each C1 has kill-check and fails if call site removed (documented in docstring LIVE-PATH PROOF)
5. Shared fixture extracted, ≤2 local copies of same mock helper (verified via rg)
6. No dead flag with zero production consumers (script outputs 0 dead)
7. `fa stats --global` exists as active consumer for global_history write target, C2 green
8. Docs updated for all shipped features, link integrity green, no broken inbound refs from PR A' extraction
9. `just check` green (lock, lint, typecheck, authoring-check, test with coverage)

---

## 6. Non-goals (locked, from your patch doc)

- STATUS LIVE/EXPERIMENTAL machine enums
- wiring-allowlist.toml bureaucracy
- New inner-loop tools fs.* for wiring checks
- CodeGraph / repo-intel as merge gate
- LLM-as-judge in every-PR CI
- Making human commit-msg as strict as IntentGuard
- Replacing ADR-11 blueprint PR3+ Level-1 packs with I9 alone
- Full UC5 eval platform

---

## 7. Risks v2

- Doc cleanup enormous may introduce link drift → mitigate via markdown-link-check + incremental PR per doc bucket (project-overview, llms.txt, instructions, AGENTS/HANDOFF/DIGEST)
- Dead flag removal may break tests that relied on flag via getattr dynamic → mitigate via script that searches both direct and getattr patterns, plus full suite after each removal
- Shared fixture extraction may cause mypy errors on Optional log — mitigate via _require_log pattern from gold files
- fa stats --global may be confused with per-run stats — document clearly in --help and in 02-operations.md
- Authoring C2 kill-check may be flaky if catch-corpus fixture path changes — pin fixture content and use tmp_path workspace not real corpus prefix

---

## 8. Where we stopped — for next agent (updated)

As of 2026-07-16 12:00 UTC, branch substrate @ 81b5487 + local fixes (1526 passed, authoring-check 0 after exports fix):

- Slices 0-9 landed, see closure docs
- New files: global_history.py, session_wiring.py fixture, test_slice5_6_7_wiring.py (8 C1), test_global_history_export.py (6 tests)
- Remaining open from v1 workplan:
  - Dead flags inventory script not yet created, removal not done
  - Fixture extraction into gold tests not yet done (gold still have local copies)
  - Additional C1 for slices 1-5 present vs promised: assessment done in v1 §1.2 table, but extra tests not yet added
  - list_tasks C1 missing, termination wiring missing
  - stats --global not implemented
  - Doc cleanup not started (project-overview, llms.txt, instructions, etc)
  - PR3 parity/docs code not implemented (explanation done)

Next agent should start at Task 1 C2 kill-check for authoring allowlist (30 min, high ROI, no deps) and Task 5 dead flags script (30 min), then Task 2 fixture extraction.

---

## 9. Explicit file edit map for next steps (thin, v2)

**Task 1 authoring C2:**
- New: `tests/test_authoring_wiring.py`, `tests/test_authoring_protected_paths_parity.py`
- No edits to TCB unless drift found

**Task 5 dead flags:**
- New: `scripts/check_dead_flags.py`
- Edit: `src/fa/feature_flags.py`

**Task 2 fixture extraction:**
- Edit: `tests/test_pr1_wiring.py`, `test_pr2_wiring.py`, `test_pr3_wiring.py`, `test_pr4_wiring.py`, `test_pr5_wiring.py` to import from `tests.fixtures.session_wiring`

**Task 3 more C1:**
- New: `tests/test_slice1_5_additional_wiring.py`, `tests/test_list_tasks_wiring.py`, `tests/test_subagent_termination_wiring.py`

**Task 6 stats --global:**
- Edit: `src/fa/stats.py`, `src/fa/cli.py` (add --global flag)
- New: `tests/test_stats_global_wiring.py` (C2)

**Task 8 docs:**
- Edit: `knowledge/project-overview.md`, `knowledge/llms.txt`, `knowledge/instructions/01-install.md`, `02-operations.md`, `AGENTS.md`, `HANDOFF.md`, `knowledge/adr/DIGEST.md`, `README.md`

---

## 10. Final note

v2 is intentionally more explicit than v1 because failure mode is partial reality: docs claim wiring, tests exist, but no kill-check. v2 adds deterministic verification steps (grep -q, file existence, no dynamic import) that an agent can run without LLM judgement, plus high ROI improvements that clarify intent and unblock execution.

Shortest path to trustworthy substrate and authoring guardrails that prevent recurrence:

- Prove TCB wiring via C2 kill-check (HR1)
- Prove CI always-run via grep (HR2)
- Automate dead-flag detection (HR3)
- Provide active consumer for global_history (HR4)
- Provide copy-paste C1 template (HR5)
- Enforce shared fixture usage (HR6)

