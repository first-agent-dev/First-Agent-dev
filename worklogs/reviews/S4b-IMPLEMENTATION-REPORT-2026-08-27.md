# S4b — `invoke_workflow` — Implementation Report (2026-08-27)

**Branch** `fa/20260826-cae-defect-fixes` · **HEAD** `3a8c977`
**Commits** `6852f9c` (RK6) → `65fbc02` (tool + seam) → `f20f845` (tests + Q15) → `3a8c977` (plan)

**Result:** L0 → **L3**. Suite **3371p / 7f** (7 = known env baseline, zero new).
Mutation **18/18 killed**. Gates: ruff, mypy (6-error baseline), pylint 10.00/10,
7/7 contract scripts.

---

## What shipped

| File | Change |
|---|---|
| `src/fa/inner_loop/tools/workflow_tool.py` | **NEW** — `build_invoke_workflow_tool`, `WorkflowInvocationContext`, `child_run_id`, `parse_roles` |
| `src/fa/cli.py` | `_make_workflow_ctx_provider`; `_build_run_tool_registry(..., workflow_ctx=None)`; chat-only registration |
| `src/fa/inner_loop/workflow_controller.py` | RK6: `deadline_mono`, `WorkflowContext.deadline_mono`, guard in `_run_stage`, `WORKFLOW_DEADLINE_EXIT_CODE`, `DEADLINE_REASON_MARKER` |
| `src/fa/inner_loop/runtime_limits.py` | `workflow_timeout_seconds` (default 1800, strictly positive) |
| `src/fa/inner_loop/loop.py` | `invoke_workflow` in `_NEVER_PARALLEL_TOOLS` (intent; already serial via `permission="workspace"`) |
| `tests/test_invoke_workflow_tool.py` | **NEW** — 76 tests |
| `tests/test_workflow_deadline.py` | **NEW** — 11 tests |
| `tests/test_prompt_registry_coherence.py` | Q15=A: oracle → live corpus; `_PENDING_REGISTRATION` emptied |
| `tests/_chat_registry_fixture.py` | **NEW** — shared live-corpus builder (extracted at the third copy) |

## Live-path proof (L3)

```
chat     invoke_workflow=True   pr_prepare=True   n=13
coder    invoke_workflow=False  pr_prepare=True   n=17
planner  invoke_workflow=False  pr_prepare=True   n=10
eval     invoke_workflow=False  pr_prepare=True   n=6
chat, workflow_ctx=None -> absent + WARNING "invoke_workflow is unavailable"
```

## RK6 measured

| Case | Stages dispatched | Exit | Status |
|---|---|---|---|
| deadline in the past | `[]` | 124 | FAILED + marker |
| expires during stage 1 | `["planner"]` | 124 | FAILED |
| no deadline (every existing caller) | `["planner","coder","eval"]` | 0 | DONE |

Stated limit, pinned by a test rather than hidden: a cooperative check cannot
interrupt a stage in flight, so the worst case is **deadline + one stage**.

## Mutation — 18/18

Registration removed · parent run_id reused · reentrancy guard dropped ·
exceptions propagated · child id concatenated без truncation · `_run_stage`
guard removed · deadline raises · boundary `>=`→`>` · fail-fast overwrite ·
`deadline_mono=None` · `output_mode=console` · mode check removed · roles check
removed · `finally` dropped · every role registered · prompt advertises a
fabricated tool · schema ceiling raised · `permission="read"`.

> **One false survivor, caused by my own tooling.** M15 first "survived" because
> my sed pattern matched `if role == "chat":` at `cli.py:1372`
> (`_build_role_registry`) instead of the S4b seam at `:1446`. Re-applied at the
> correct line it dies with 4 failures. Recorded because the lesson is about
> mutation *tooling* trustworthiness, not about the tests.

## Deviations from the edit packet (all verified)

1. Non-chat caller is `cli.py:2391`, not 2378, and is hardcoded `"coder"` — it can never reach the chat branch.
2. Context provider extracted to module level: the inline closure pushed `_cmd_run` to C901 complexity 16 > 15.
3. `_write_stage_failure_state` needed a pass-through for the deadline exit code, otherwise fail-fast overwrote the marker and `timed_out` reported False (M9).
4. Five new public symbols required in `__all__` (`FA-AUTHORING-V2-EXPORTS-COMPLETENESS`) — a real new suite failure, caught and fixed.
5. `tests/_chat_registry_fixture.py` extracted (pylint R0801 at the third copy).

## Q15 — resolved = A (operator)

`invoke_workflow` registers at the CLI seam, so `build_chat_registry` never
contains it and the Q12 self-retiring exemption **would not have fired** — my
prior-turn prediction that S4b would break that test was wrong. The oracle now
reads the live corpus (13 tools) and `_PENDING_REGISTRATION` is empty; a
fabricated tool in the prompt now fails immediately (mutation M16).

## Still open

- **RK8** — `fa workflow --roles` accepts `chat` as a stage role. That stage runs in a **separate process**, so the thread-local re-entrancy guard cannot see it. Mitigation is a role allowlist in `_cmd_workflow`; deliberately not widened into this slice.
- **S5** (ACRR proxy) — now unblocked: child run ids are distinct, so per-run ratios are meaningful.
- **S6** — ADR-16 + docs.
