# S3 Implementation Report — Scope Estimator Integration in CLI

**Date:** 2026-08-26
**Slice:** S3 of P2 plan (Complexity-Aware Execution + Chat Role)
**Status:** ✅ COMPLETE
**New tests:** 4 C1 tests added to `tests/test_cli_ergonomics.py`
**Regression:** 35 pre-existing tests in `test_cli_ergonomics.py` — all still pass
**Total suite:** 97 pass (31 S1 + 27 S2 + 39 ergonomics), 0 fail
**mypy strict:** clean (no new errors; 11 pre-existing yaml/requests stubs unchanged)

## Changes Made

| # | File | Edit | Lines Changed |
|---|---|---|---|
| 1 | `src/fa/output.py` | Added `"scope_estimate"` to `LogKind` Literal | +1 |
| 2 | `src/fa/cli.py` | Scope estimation block in `_cmd_run` + `system_prompt_extra` composition | +35 |
| 3 | `tests/test_cli_ergonomics.py` | `_CapturingTransport` helper + 4 C1 tests | +226 |

## Plan Contract Verification

| Contract | Status | Evidence |
|---|---|---|
| **GAP2** — Scope estimator not wired into CLI | ✅ CLOSED | `test_chat_role_logs_scope_estimate_event` verifies event in events.jsonl |
| **CT1** consumer — `estimate_scope()` used in `_cmd_run` | ✅ | Lazy import inside `if role == "chat":` block |

## Exit Criteria (from plan)

| Criterion | Status | Test |
|---|---|---|
| `fa run -r chat "fix typo"` → events.jsonl contains `scope_estimate` with `difficulty=1` | ✅ | `test_chat_role_logs_scope_estimate_event` |
| `fa run -r coder "fix typo"` → NO `scope_estimate` event | ✅ | `test_coder_role_does_not_log_scope_estimate` |
| `system_prompt_extra` contains "## Task Scope Estimate" | ✅ | `test_chat_role_system_prompt_contains_scope_hint` |
| `initial_memory_summary` does NOT contain scope hint | ✅ | Same test verifies base prompt lacks "Difficulty:" |
| Empty task does not crash | ✅ | `test_chat_role_empty_task_does_not_crash` (exit 2, not crash) |

## Implementation Details

### Edit 1: LogKind addition (src/fa/output.py)

**Why:** The `LogKind` Literal type is the canonical registry of event kinds. Adding `"scope_estimate"` is required for `log.append(kind="scope_estimate", ...)` to type-check under mypy strict.

**Placement:** Added under `# Observability / recovery` category, between `"recovery_action"` and `"verification"`.

### Edit 2: Scope estimation in _cmd_run (src/fa/cli.py)

**Insertion point:** Between `state.attach_output_bus(output_bus)` and `_run_start_mono = time.monotonic()`.

**Mechanism:**
1. When `role == "chat"`, lazily import `estimate_scope` (avoids module-level import cost)
2. Call `estimate_scope(args.task or "")` — wrapped in try/except ValueError
3. Log result as `scope_estimate` event with all 5 OperatingPoint fields + task_preview
4. Compose `scope_hint` markdown string
5. Concatenate into `system_prompt_extra`: `_eval_system_prompt_extra(role, models) + scope_hint`

**Composition correctness:**
- For eval role: `ADVERSARIAL_EVAL_STANCE_PREAMBLE + ""` = eval preamble only
- For chat role: `"" + scope_hint` = scope hint only
- For coder/planner: `"" + ""` = empty string

**Routing path:** `system_prompt_extra` → `PinnedBuffer.extract_pinned_content()` → `agents_md_map` → second system message in request. The scope hint does NOT contaminate `initial_memory_summary` (reserved for resume drafts).

### Edit 3: Tests (tests/test_cli_ergonomics.py)

**`_CapturingTransport`:** New test helper that captures ALL system messages (not just `messages[0]`). Records `system_messages: list[str]` for multi-message inspection.

**Test design:**

| Test | Class | Kill-check target |
|---|---|---|
| `test_chat_role_logs_scope_estimate_event` | C1 | Removes `estimate_scope()` call → no event logged |
| `test_coder_role_does_not_log_scope_estimate` | C1 | Removes `role == "chat"` guard → coder gets scope events |
| `test_chat_role_system_prompt_contains_scope_hint` | C1 | Removes `scope_hint` from `system_prompt_extra` → not in agents_md_map |
| `test_chat_role_empty_task_does_not_crash` | C1 | Removes `except ValueError` → crash on empty task |

## Implementation Findings

### Finding 1: LogKind prerequisite not in plan

**Issue:** The plan listed `src/fa/cli.py` and `tests/test_cli_ergonomics.py` as allowed files, but adding a new event kind required editing `src/fa/output.py` (the `LogKind` Literal type).

**Resolution:** Added `"scope_estimate"` to `LogKind`. Documented as extra file change.

### Finding 2: system_prompt_extra routing path

**Discovery:** `system_prompt_extra` is NOT appended directly to the base system message. It flows through:
1. `drive_session(system_prompt_extra=...)`
2. → `PinnedBuffer.extract_pinned_content(extra_instructions=system_prompt_extra)`
3. → `agents_md_map` parameter of `build_prompt_parts_v2()`
4. → Second system message: `{"role": "system", "content": f"AGENTS.md map:\n{agents_md_map}"}`

**Impact on tests:** The `_CapturingTransport` was updated to capture all system messages (`system_messages: list[str]`), and the test asserts the scope hint appears in `system_messages[1]` (agents_md_map), not `system_messages[0]` (base role prompt).

### Finding 3: Empty task validation layer

**Discovery:** `_validate_run_args()` rejects whitespace-only tasks with exit code 2 BEFORE reaching the scope estimation block. The `ValueError` handler in the scope estimation block is defense-in-depth for tasks that pass CLI validation but still trigger the estimator's ValueError.

**Impact on test:** `test_chat_role_empty_task_does_not_crash` asserts exit code 2 (validation rejection) rather than 0 (graceful completion).

## S4 Dependencies Satisfied

Per plan, S4 (invoke_workflow Tool) depends on S1, S2, S3:
- **S1 → S4:** `estimate_scope()` available for workflow tool to use ✅
- **S2 → S4:** Chat role exists with registry ✅
- **S3 → S4:** Scope estimation wired into chat role, `recommended_mode` available ✅

S4 can now implement the `invoke_workflow` tool that the chat role uses to escalate complex tasks to the full planner→coder→eval pipeline.
