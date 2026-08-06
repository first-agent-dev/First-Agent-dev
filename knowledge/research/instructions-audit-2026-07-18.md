# Instructions Audit — Gap Analysis & ROI Assessment

> **Created:** 2026-07-18
> **Purpose:** Thorough review of knowledge/instructions/ against current codebase (post-PR #53, post-doc-refactoring)
> **Scope:** Identify gaps, stale content, missing how-to's; prioritize by ROI

---

## Executive Summary

The instructions (01-install.md + 02-operations.md + README.md) are **partially stale** after PR #53 (substrate gap closure) and the doc refactoring. The install guide is mostly solid. The operations guide has significant gaps around new CLI features, FeatureFlags, and the `fa` wrapper. The instructions README is misleading about planned docs and the "dispatcher" role.

**High-ROI fix:** Update 02-operations.md §7 (CLI usage), §11 (cheat sheet), and the instructions README. Update config.yaml.example. These are the surfaces operators actually use.

---

## 1. Deferred Items — ROI Assessment

| Deferred item | ROI | Rationale |
|---|---|---|
| **ADR-4/7/14 amendments** | LOW | Affects developer/agent routing, not operator instructions |
| **Codemaps update** | LOW | Developer surface, not operator surface |
| **Prompts formalization** | LOW | Agent-facing, not operator-facing |
| **Trace pruning** | LOW | Internal hygiene, not operator-visible |
| **fa generate-llms-txt** | LOW | Future tool, not instruction content |
| **Instructions update** | **HIGH** | Operator-facing surface is stale after PR #53 + refactoring |

**Verdict:** Instructions update is the single highest-ROI deferred item because it directly affects the operator's ability to use features that already exist in the codebase but are undocumented or incorrectly documented.

---

## 2. Gap Inventory — 02-operations.md

### 2.1 CLI command coverage gaps

| Feature in codebase | Documented? | Location in code | Gap |
|---|---|---|---|
| `fa stats --global-history` | Mentioned in §1 table only | `cli.py:635` | No §7 usage example, no how-to for reading cross-run analytics |
| `fa stats --dead-zones` | NOT documented | `cli.py:622` | Missing entirely |
| `fa stats --since` | NOT documented | `cli.py:611` | Missing entirely |
| `fa stats --output json` | NOT documented | `cli.py:616` | Missing entirely |
| `fa authoring-check` | NOT documented | `cli.py:653` | Missing — operator diagnostic tool |
| `fa sessions` (wrapper) | NOT documented | `scripts/fa` | Missing from §11 cheat sheet |
| `fa commit-traces` (wrapper) | NOT documented | `scripts/fa` | Missing from §11 cheat sheet |
| `fa update` (wrapper) | Only `fa-update.sh` documented | `scripts/fa` | Wrapper alias not in cheat sheet |
| `fa clean-rebuild` (wrapper) | Only script documented | `scripts/fa` | Wrapper alias not in cheat sheet |
| `fa rebuild` (wrapper) | NOT documented | `scripts/fa` | Missing from cheat sheet |
| `fa run --detail` values | Documented with wrong values | `cli.py` | Doc says "minimal/verbose/debug" — actual values are `minimal/standard/verbose/debug`. Default is `standard`, not mentioned |
| `fa run --output-mode` | Documented with wrong values | `cli.py` | Doc says nothing about choices; actual choices are `console/quiet`. Default is `console` |
| `fa workflow --task-planner/coder/eval` | Documented ✓ | `cli.py:494-502` | OK but examples could be clearer |
| `fa workflow --max-replans` | Documented ✓ | `cli.py:489` | OK |

### 2.2 FeatureFlags / config.yaml gaps

| Feature in FeatureFlags | Documented in config.yaml.example? | Gap |
|---|---|---|
| `blackboard_enabled: bool = True` | NO | Not in example at all |
| `telemetry_enabled: bool = True` | NO | Not in example |
| `tool_batching_enabled: bool = True` | NO | Not in example |
| `subagent_spawning_enabled: bool = False` | NO | Not in example |
| `context_budget_enabled: bool = True` | NO | Not in example |
| `context_compaction_enabled: bool = False` | NO | Not in example |
| `pty_pool_max_size: int = 2` | NO | Not in example |
| `worktree_mode: str = "shared"` | NO | Not in example |
| `fts_db_path: str = ".fa/fts.db"` | NO | Not in example |
| `prompt_caching: bool = True` | NO | Not in example |
| `offload_threshold: int = 8000` | NO | Not in example |
| `max_subagent_spawns_per_session: int = 3` | NO | Not in example |
| `blackboard_filtered_history_include_plans: bool = False` | NO | Not in example |

**Current config.yaml.example** still shows 5 old ADR-6 capability flags that are NOT in FeatureFlags at all (ENABLE_DYNAMIC_TOOLS, REQUIRE_DYNAMIC_TOOL_SANDBOX, ENABLE_MCP_GATEWAY_MANAGEMENT, ENABLE_DYNAMIC_MCP_SERVERS, ENABLE_SERVER_OPS). These appear to be stale.

### 2.3 Session data documentation gaps

| Feature | Documented? | Gap |
|---|---|---|
| `session.db` as SQLite authority | ✓ Added in Phase 4 | OK |
| `events.jsonl` as mirror | ✓ | OK |
| `global_history.db` | Mentioned in §1 table only | No how-to for reading it |
| `blackboard.jsonl` as mirror | NOT in instructions | Only in reference.md |
| `flow_state.json` | NOT in instructions | Workflow controller state |
| `eval_report.json` | NOT in instructions | Eval verdict |
| `pr_draft.md` | NOT in instructions | PR draft artifact |
| `attempt_history.json` | NOT in instructions | Recovery log |

### 2.4 Wrapper script `fa` coverage

The `fa` wrapper script (`scripts/fa`) exposes these host-side verbs that 02-operations.md §11 "Шпаргалка" doesn't list:

| Wrapper verb | Current doc status | Action needed |
|---|---|---|
| `fa sessions` | Missing | Add to cheat sheet |
| `fa commit-traces` | Missing | Add to cheat sheet |
| `fa clean-rebuild` | Only script path documented | Add wrapper alias |
| `fa rebuild` | Missing | Add to cheat sheet |
| `fa update` | Only script path documented | Add wrapper alias |
| `fa clean` | Missing (alias for clean-rebuild) | Add to cheat sheet |

---

## 3. Gap Inventory — 01-install.md

01-install.md is mostly solid. Issues found:

| Issue | Severity | Detail |
|---|---|---|
| "Ролевой Цикл" section in README says `eval` role "запускает тесты (pytest, mutmut)" | MEDIUM | Stale — eval role doesn't run mutmut; it reads `eval_report.json` and returns a route |
| Instructions README mentions `03-runtime-usage.md` and `04-modules.md` as "планируется добавить" | LOW | These have been planned for months. Either write them or remove the promises |
| Instructions README mentions `dispatcher` role as "ближайшее будущее" | MEDIUM | `fa workflow --mode adaptive` already provides this. The dispatcher concept is stale |

---

## 4. Gap Inventory — instructions/README.md

| Issue | Severity | Detail |
|---|---|---|
| "Ролевой Цикл" section is stale | HIGH | Describes manual `fa run --role` cycling. `fa workflow` already automates this. Should present `fa workflow` as primary, manual roles as fallback |
| "Планируется добавить: 03-runtime-usage.md" | MEDIUM | This is what 02-operations.md §7 already covers. Either create the file or drop the promise |
| "Планируется добавить: 04-modules.md" | LOW | Still missing. Remove or write minimal version |
| No mention of `fa workflow` at all | HIGH | The primary way to run multi-role tasks is absent from the README |
| Mentions `dispatcher` as future | MEDIUM | `fa workflow --mode adaptive` IS the dispatcher. Remove the "future" framing |

---

## 5. Prioritized Action Plan

### Priority 1 — HIGH ROI (operator-facing, affects daily use)

1. **Update config.yaml.example** — Replace 5 stale capability flags with 13 actual FeatureFlags. Add comments explaining each flag and its default.

2. **Update 02-operations.md §7** — Add `fa stats` full documentation (--global-history, --dead-zones, --since, --output json). Add `fa authoring-check` documentation. Fix `--detail` and `--output-mode` values.

3. **Update 02-operations.md §11** — Add missing `fa` wrapper verbs to cheat sheet (sessions, commit-traces, rebuild, clean-rebuild, update).

4. **Update instructions/README.md** — Replace "Ролевой Цикл" section with `fa workflow` as primary. Remove stale dispatcher/03/04 promises or convert to accurate descriptions.

### Priority 2 — MEDIUM ROI (completeness, not daily use)

5. **Add session artifact table to 02-operations.md §1** — Document all session artifacts (flow_state.json, eval_report.json, pr_draft.md, attempt_history.json, blackboard.jsonl) and how to inspect them.

6. **Add FeatureFlags section to 02-operations.md** — Document where config.yaml goes, what flags exist, how to enable/disable, and that changes take effect on next `fa run`.

7. **Add `fa stats --global-history` how-to** — Show operator how to read cross-run analytics, with example output.

### Priority 3 — LOW ROI (nice to have)

8. **Create 03-runtime-usage.md** — Or drop the promise from README.

9. **Create 04-modules.md** — Or drop the promise from README.

---

## 6. What NOT to do

- Do NOT add `blackboard.query()` API details to operator instructions — that's an agent API, not operator-facing
- Do NOT add `fs_instant_grep` to instructions — same reason
- Do NOT rewrite 01-install.md — it's solid and the refactoring didn't change deployment
- Do NOT add ADR details to instructions — that's what knowledge/ is for
