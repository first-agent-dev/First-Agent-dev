# S4a Implementation Report — Extract Workflow Controller

**Date:** 2026-08-26
**Slice:** S4a of P2 plan (Complexity-Aware Execution)
**Status:** ✅ COMPLETE
**Tests:** 564 passed, 0 failed (all workflow/cli/scope/blackboard/global_history/stats tests)
**cli.py:** 3965 → 3165 lines (−800)
**workflow_controller.py:** 792 lines (NEW)
**mypy strict:** clean
**ruff:** not available in environment

## Summary

Extracted ~970 lines of workflow controller code from `cli.py` into a new
`src/fa/inner_loop/workflow_controller.py` module. The workflow controller is
now independently testable, importable from tools (for S4b invoke_workflow),
and easy to iterate on.

## Changes Made

| # | File | Action | Lines |
|---|---|---|---|
| 1 | `src/fa/inner_loop/workflow_controller.py` | NEW | +792 |
| 2 | `src/fa/cli.py` | EDIT (remove ~970, add ~110 wrapper + imports) | −800 net |
| 3 | `tests/test_s8_workflow_controller.py` | EDIT (import path fix) | +1 |
| 4 | `tests/test_global_history_export.py` | EDIT (allowlist update) | +1 |

## Architecture

### Dependency Graph (no circular imports)

```
cli.py ──imports──▶ workflow_controller.py
  │                        │
  │  _cmd_run              │  run_workflow()
  │  _cmd_workflow         │  _run_linear/repair/adaptive
  │  (thin wrapper)        │  _run_stage (takes run_stage_fn)
  │                        │  Context/Progress/Result types
  │                        │
  └──── passed as ────────▶│  run_stage_fn parameter
```

- `workflow_controller.py` does NOT import from `cli.py`
- `_run_stage` receives `run_stage_fn` as a callable parameter (dependency injection)
- `cli.py` imports from `workflow_controller.py` (one-way dependency)
- No circular imports (verified by import test)

### Public API

```python
def run_workflow(
    *,
    roles: list[str],
    task: str | None,
    per_role_task: Mapping[str, str | None],
    mode: str,
    max_repairs: int,
    max_replans: int,
    run_id: str,
    config: Path,
    workspace: Path,
    max_turns: int,
    output_mode: str = "console",
    run_stage_fn: Callable,
    transport: Transport | None = None,
    secrets: Mapping[str, str] | None = None,
    session_context: SessionContext | None = None,
    run_context: RunContext | None = None,
    session_db: SessionDatabase | None = None,
) -> tuple[int, FlowState | None]:
    """Run the workflow pipeline. Callable from CLI and from tools."""
```

### Key Refactoring Decisions

1. **`WorkflowContext` lost `args: argparse.Namespace`** — replaced with explicit
   `config`, `workspace`, `max_turns`, `output_mode` fields. This removes the
   argparse dependency from the internal API.

2. **`_run_stage` takes `run_stage_fn: Callable`** — instead of calling `_cmd_run`
   directly. This breaks the circular dependency and makes the controller
   testable with mock stage dispatchers.

3. **`_cmd_workflow` is now a thin wrapper** — parses args, validates, resolves
   session lifecycle, then calls `run_workflow()`. All pipeline logic lives in
   the new module.

4. **Names made public** — `_WorkflowContext` → `WorkflowContext`, `_run_stage`
   stays private but `_cmd_workflow` → `run_workflow()`, etc. Constants like
   `DEFAULT_MAX_REPAIRS` and `WORKFLOW_MODES` are now public.

## Exit Criteria

| Criterion | Status | Evidence |
|---|---|---|
| `workflow_controller.py` exists with ~792 lines | ✅ | `wc -l` confirms |
| `cli.py` drops from ~3965 to ~3165 lines | ✅ | −800 lines |
| No circular imports | ✅ | `python -c "from fa.cli import ..."` works |
| All existing workflow tests pass | ✅ | 41/41 in test_cli_ergonomics.py |
| All S8 controller tests pass | ✅ | 25/25 in test_s8_workflow_controller.py |
| All S10c exit contract tests pass | ✅ | 7/7 in test_s10c_workflow_exit_contract.py |
| `_cmd_workflow` delegates to `run_workflow()` | ✅ | Verified by code review |
| `run_workflow()` callable without argparse | ✅ | Takes structured params only |

## Test Fixtures Updated

| Test File | Change |
|---|---|
| `tests/test_s8_workflow_controller.py` | `_read_back_terminal_state` → import from `workflow_controller` |
| `tests/test_global_history_export.py` | Added `workflow_controller.py` to projection import allowlist |

## S4b Readiness

S4a establishes the foundation for S4b (invoke_workflow tool):
- `run_workflow()` is callable from tools (no argparse dependency)
- `WorkflowContext` is a clean dataclass (no CLI coupling)
- `run_stage_fn` parameter allows tools to inject their own stage dispatcher
- The tool handler in S4b will import `run_workflow` from `workflow_controller.py`
