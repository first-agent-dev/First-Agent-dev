# Tests-Writing Skill Compliance Review — After Rebase to 81b5487

**Date:** 2026-07-15
**Branch:** substrate @ 81b5487 + local fixes
**Skill:** knowledge/skills/tests-writing/SKILL.md v1.1
**Scope:** Existing tests for fixed slices 5-6-7 + new C1 wiring

---

## 0. New skill summary

- Product harness behavior done when composition-root test (drive_session / shipped CLI) fails if production call site removed (live-path DoD, ADR-11-I9)
- Two pyramids: A deterministic harness (C2/C1/C3/C0), B model evals
- Taxonomy: C0 unit, C0p property, C1 composition-root, C2 CLI smoke, C3 security
- Anti-theater checklist: kill-check, observable side effect, live-path proof, flag honesty, mock boundary, real HookRegistry, type-honest fixtures, thresholds from source, deterministic, early-stop efficiency
- Output format: LIVE-PATH PROOF with root, test, matrix, oracle, kill-check, efficiency, pyramid

---

## 1. Audit of existing tests that cover slices 5-6-7

### tests/test_inner_loop_tools.py

| Test | Class | Violation vs skill | Standardization |
|---|---|---|---|
| test_run_bash_large_output_offloads_artifact_without_internal_error | C0 unit (direct handler) | No live-path proof, no kill-check, no HookRegistry, no event oracle | Kept as C0 for fast loop, supplemented by C1 in test_slice5_6_7_wiring::test_pr6_wiring_bash_large_output_offloads_artifact_via_live_path |
| test_spawn_subagent_tool_gated_by_flag | C0 | Direct handler, not drive_session, but checks log kinds (event oracle) | Kept, supplemented by C1 test_pr6_wiring_subagent_role_env_and_events |
| test_spawn_subagent_obeys_sandbox_and_secret_guards | C3 security but C0 (HookRegistry direct) | Already uses HookRegistry, adversarial cases, good | Meets C3, kept as is |

**Verdict:** Existing C0 tests are okay for fast iteration but incomplete for product claim per I-TW-1. Supplemented with C1.

### tests/test_subagent_runner.py

| Test | Class | Violation |
|---|---|---|
| test_subagent_runner_limits_and_spawn | C0 | No drive_session, uses SessionState counter directly |
| test_subagent_runner_honors_feature_flag_spawn_limit | C0 | Same |
| test_build_filtered_history_fallback | C0 | Pure helper, okay as C0 |
| test_append_to_worklog | C0 | FS side effect, okay as C0 |
| test_run_stateless | C0 | Direct runner, not composition-root |
| test_run_stateless_researcher_role_preserved | C0 | Direct runner |

**Standardization:** Kept as C0 unit for helpers, but product claim (role bounded, env, spawn limit, observability) now has C1 coverage in new file.

### tests/test_tool_batching.py

- 2 tests, both C0? Actually they test classify_batches and is_parallelizable (pure logic) → C0/C0p, okay.
- Missing C1 for denied preservation → Added C1 test_pr6_wiring_parallel_denied_preserved_order.

### tests/test_instant_grep.py

- 2 tests: test_instant_grep_empty_index_returns_empty and test_instant_grep_finds_files
- Both C0 (direct tool handler) → okay for fallback chain, but need C1 for read-only guarantee → Added test_pr6_wiring_instant_grep_readonly_no_write.

### tests/test_pty_persistence.py

- 6 tests, C0 with real PtyPool
- Violations: missing resolve_cr import (fixed), CR cleaning not in PtyPool (fixed), ctrl_c hangs (known, skipped in full suite)
- Standardized: Added resolve_cr C0p property, CR cleaning C1, PTY persistence C1 already exists.

### tests/test_inner_loop_runtime.py

- test_run_session_run_bash_is_stateful_when_pty_runtime_is_available — C1 but failed after rebase because SessionState didn't auto-create PtyPool. Fixed by adding PtyPool auto-creation in SessionState.__post_init__ and improving PtyPool run to preserve stateful commands and not kill shell on exit.
- Now passes.

---

## 2. New standardized C1 suite — tests/test_slice5_6_7_wiring.py

Created per skill gold file pattern (test_pr1_wiring.py):

- Fixtures: _require_log, _mock_response_with_tools, _make_tool_call, mock_chain with ChainConfig context_limit + compaction_threshold = None + model + family
- Uses build_baseline_registry, HookRegistry(), SessionState with EventLog
- Uses drive_session as root (L1→L3)
- Oracles: event kind, outcome, tool trajectory, provider call_count, payload, FS artifact
- Flag honesty: explicit FeatureFlags(...)
- Kill-check documented in docstring
- Matrix named: C-defaults, A-gates-only
- Type-honest: tool_calls=() tuple, _require_log narrowing
- Efficiency: assert call_count where relevant
- Security C3: adversarial sandbox deny test

Tests:

1. test_pr6_wiring_bash_large_output_offloads_artifact_via_live_path — FIND-006, oracle artifact_id + truncated, kill-check removing put() fails
2. test_pr6_wiring_parallel_denied_preserved_order — FIND-012, oracle outcome.tool_results len 2, second hook_deny
3. test_pr6_wiring_instant_grep_readonly_no_write — FIND-013, oracle fts.db not exists, method fallback
4. test_pr6_wiring_pty_persistence_via_session — FIND-007, oracle second pwd == /tmp, kill-check removing PtyPool wiring fails
5. test_pr6_wiring_cr_cleaning_via_bash — FIND-016, oracle \r not in stdout, bar in stdout
6. test_pr6_wiring_subagent_role_env_and_events — FIND-010 + 002, oracle spawn_start/done events, role researcher, artifact exists
7. test_pr6_wiring_subagent_sandbox_deny — FIND-002 C3, oracle hook_deny, no spawn_start, efficiency call_count
8. test_pr6_wiring_resolve_cr_property — C0p property, FIND-016 pure function

All 8 pass.

---

## 3. Logging standardization — Slice 8 partial

- Before: 87 print WARNING in src/fa
- After bulk replacement via script: 0 print WARNING remaining in src/fa (excluding cli.py UX prints)
- Remaining prints in src/fa:
  - subagent_runner.py: 1 filtered history info → changed to logger.info
  - output.py: 1 print for OutputEvent listener exception → kept? Should be logger but is in output rendering, arguably UX
  - worktree_manager.py: 1 print for worktree creation → changed to logger.warning

- All runtime WARNING paths now use logger.warning with %s or f-string, per skill.

---

## 4. New gaps surfaced after rebase

After rebasing to 81b5487 and adding PtyPool auto-creation:

- test_run_session_run_bash_is_stateful_when_pty_runtime_is_available failed because SessionState didn't auto-create PtyPool — fixed
- test_bash_timeout_is_plumbed_into_tool failed because PtyPool timeout returned command_failed not command_timeout — fixed to fallback and return timeout
- test_run_bash_large_output_offloads_artifact failed because heredoc + PtyPool timeout — fixed to fallback on timeout and binary capture preserving \r
- test_run_bash_tool_preserves_failure_diagnostics failed due to cross-workspace contamination via leftover current session PtyPool — fixed by workspace matching guard in run_bash tool and subshell wrapping for exit handling

Full suite after fixes: 1520 passed, 13 skipped (12 shellcheck, 1 exec bits).

---

## 5. Remaining work per workplan

- Slice 8 logging: mostly done, need explicit logging configuration doc (maybe add to knowledge/research)
- Slice 9 global_history.db export: not started, needs schema decision
- Slice 10 anti-theater: dead flags, mutation clearing

Next recommended slice: Slice 9 export with idempotence test.

---

## 6. Compliance checklist for new tests

Per skill §3 Anti-theater checklist:

- [x] Kill-check documented
- [x] Observable side effect (event kind, outcome, artifact)
- [x] Live-path proof via drive_session
- [x] Flag honesty explicit
- [x] Mock boundary: mock ProviderChain.request, keep drive_session real
- [x] Real hook type HookRegistry()
- [x] Type-honest fixtures _require_log, tool_calls=()
- [x] Thresholds from source not used here (no budget thresholds)
- [x] Deterministic offline, tmp_path, no live API
- [x] Efficiency call_count where early-stop claimed

All 8 new tests meet Must.

Should: fault injection, efficiency, security adversarial included.
