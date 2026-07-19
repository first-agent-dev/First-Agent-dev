# State Assessment — Authoring Hardening (2026-07-16, session 2)

## Workplan v2 criterion checklist

| # | Criterion (§5) | Status | Evidence |
|---|---|---|---|
| 1 | `fa authoring-check` 0 diagnostics on clean tree | ✅ DONE | `0 diagnostics, exit_code: 0` |
| 2 | C2 test for authoring allowlist wiring exists + kill-check | ✅ DONE | `test_authoring_wiring.py` (3 tests) + `test_authoring_protected_paths_parity.py` (2 tests) |
| 3 | C1 tests for every product surface | ⚠️ PARTIAL | Missing: `fs.list_tasks` C1, subagent termination lifecycle C1, drive_session C1 for session DB + observability |
| 4 | Each C1 has kill-check + LIVE-PATH PROOF docstring | ⚠️ PARTIAL | Existing pr1–5 + slice5_6_7 wiring tests have it; new Task 3 tests not yet created |
| 5 | Shared fixture extracted, ≤2 local copies | ✅ DONE | 0 local copies (was 7), 7 files import from session_wiring |
| 6 | No dead flag with zero production consumers | ⚠️ OPEN | No `check_dead_flags.py` script yet; manual scan shows all 12 fields have ≥4 prod refs (likely 0 dead) |
| 7 | `fa stats --global-history` active consumer + C2 green | ✅ DONE | `--global-history` flag in cli.py, `test_stats_global_wiring.py` present |
| 8 | Docs updated for shipped features, link integrity green | ⚠️ PARTIAL | llms.txt missing session_wiring/global_history/list_tasks entries; HANDOFF stale ("Not pushed — apply patch"); llms.txt has instant_grep refs but no bucket entries for new files |
| 9 | `just check` green | ✅ DONE | 1552 passed, 13 skipped, 0 failed |

## Task-by-task status update

| Task | Re-inventory status | Current status | What changed this session |
|---|---|---|---|
| **Task 1** — Authoring C2 + kill-check + protected-path parity | DONE | ✅ DONE | No change (was already done) |
| **Task 2** — Shared fixture extraction | OPEN (partial) | ✅ DONE | All 7 test files refactored to import from `tests.fixtures.session_wiring`; 0 local duplicates |
| **Task 3** — More C1 for slices + list_tasks + termination | PARTIAL | ⚠️ PARTIAL | No new C1 tests created yet; named test files still missing |
| **Task 4/5** — Dead flags script + cleanup | OPEN | ⚠️ OPEN | No change; manual scan suggests 0 dead flags, but script not yet created |
| **Task 6** — `fa stats --global-history` | DONE | ✅ DONE | No change (was already done) |
| **Task 7** — Blueprint PR3 parity/docs V3/V5 | OPEN | ⚠️ OPEN | No change (locked non-goal for full PR3; thin advisory optional) |
| **Task 8** — Doc cleanup | PARTIAL | ⚠️ PARTIAL | No change; HANDOFF stale, llms.txt missing entries |
| **HR2** — Structured "no path filter" check | Optional | ✅ DONE | `scripts/check_workflow_no_path_filter.py` + 13 tests + ci-guardrails-reference doc update |
| **Bot fixes** — 6 code quality issues | N/A | ✅ DONE | spawn_subagent wrong kwarg, 4 empty excepts, unused import |

## Remaining open work (ranked by ROI)

### Tier 1 — High ROI, unblocks downstream (do now)

| Priority | Item | Est. effort | Dependency | Rationale |
|---|---|---|---|---|
| **1** | **Task 4/5: `scripts/check_dead_flags.py`** | 30 min | None | Quick script, expect 0 dead, closes criterion #6, regression guard for future |
| **2** | **Task 3: `test_list_tasks_wiring.py`** | 45 min | Session wiring fixture (done) | `fs.list_tasks` registered but no C1 proves it works via live session; closes a Task 3 gap |
| **3** | **Task 3: `test_subagent_termination_wiring.py`** | 45 min | Session wiring fixture (done) | Subagent lifecycle termination C1 — product claims stateless subagents but no test proves ctrl_c/timeout cleanup |

### Tier 2 — Medium ROI, doc hygiene (do after Tier 1)

| Priority | Item | Est. effort | Dependency | Rationale |
|---|---|---|---|---|
| **4** | **Task 8 (thin): HANDOFF refresh** | 20 min | None | HANDOFF says "Not pushed — apply patch from fd54ce4" — stale, confuses next agent |
| **5** | **Task 8 (thin): llms.txt update** | 20 min | None | Missing entries for session_wiring, global_history, list_tasks, check_workflow_no_path_filter |
| **6** | **Task 8 (thin): AGENTS.md session_wiring mention** | 10 min | None | Agents need to know about shared fixture rule |

### Tier 3 — Lower ROI, optional (defer unless owner requests)

| Priority | Item | Est. effort | Dependency | Rationale |
|---|---|---|---|---|
| **7** | **Task 3: `test_slice1_5_additional_wiring.py`** | 90 min | None | drive_session C1 for session DB + observability; nice-to-have, existing C0/C1 tests cover most of this at different level |
| **8** | **Task 7: thin advisory parity/docs rules** | 60 min | None | Locked non-goal for full PR3; advisory V3/V5 optional, needs FP measurement |
| **9** | **Task 8 (full): project-overview, instructions, DIGEST** | 90 min | All above | Full doc cleanup; can be done incrementally |

## Recommended execution order for this session

1. **`scripts/check_dead_flags.py`** — 30 min, no deps, closes criterion #6
2. **`tests/test_list_tasks_wiring.py`** — 45 min, highest-ROI Task 3 gap
3. **`tests/test_subagent_termination_wiring.py`** — 45 min, second-highest Task 3 gap
4. **HANDOFF refresh** — 20 min, prevents next-agent confusion
5. **llms.txt + AGENTS.md update** — 30 min, knowledge index hygiene

Total: ~2.5h of focused work for Tier 1+2, which would close 3 of 4 remaining workplan criteria.

## What would remain after Tier 1+2

- Task 3 `test_slice1_5_additional_wiring.py` (optional drive_session C1)
- Task 7 advisory V3/V5 rules (optional, locked non-goal)
- Task 8 full doc pass (project-overview, instructions, DIGEST, README)
- Mutation clearing C4 (post-C1 green, separate session)
