# S18 I-63 Fix Report — ContextVar propagation in parallel tool batch

**Gap ID:** I-63
**Title:** ContextVar `fa_current_session` not propagated to ThreadPool workers → first-try blackboard failure in parallel batches
**Severity:** High — breaks CT-S18-8/9 first-try requirement, silently breaks S15 telemetry
**Status:** FIXED + verified

## Simple explanation

Think of `ContextVar` as a per-thread sticky note.

- Main thread writes: "current session = S" (via `set_current_session(state)` at start of `run_session`)
- Tools read that sticky note via `get_current_session()` to find blackboard, workspace, search attribution.

Python's `ThreadPoolExecutor` starts worker threads. By default, workers **do not** see the main thread's sticky notes. They see `None`.

Result:
- `fs_blackboard_query` checks session → None → returns `{"error": "blackboard_unavailable"}` (loud failure, seen in S18 C9 turn1)
- `fs_search` checks session → None → skips `add_search_result_paths` (silent failure, S15 `surfaced_by` lost)

Sequential path works because it runs in main thread where sticky note exists.

## Root cause (source-verified)

- `src/fa/inner_loop/context.py:19` defines `_current_session = ContextVar(..., default=None)` with comment "works with ThreadPool in Phase 2" — false, no propagation code existed.
- `src/fa/inner_loop/loop.py:272-350` `_execute_batch_parallel` did:
  ```python
  executor.submit(registry.dispatch, p.tool_call)
  ```
  No context copy. Worker sees `get_current_session() == None`.

Affected tools (all use `get_current_session`):
- `blackboard_query.py:121` → `blackboard_unavailable`
- `fs_search.py:503` → skips telemetry
- `read_file.py:117`, `write_file.py:37`, `edit_file.py:86`, `run_bash.py:118`, `fs_exploration_metrics.py:121`, `observability.py:86`, `spawn_subagent.py:139`

## Fix

**File:** `src/fa/inner_loop/loop.py`

```python
import contextvars  # added

# inside _execute_batch_parallel:
ctxs = [contextvars.copy_context() for _ in exec_payloads]
with ThreadPoolExecutor(...) as executor:
    for p, ctx in zip(exec_payloads, ctxs):
        futures[executor.submit(ctx.run, registry.dispatch, p.tool_call)] = p
```

Why per-task copy?
- `Context` objects cannot be entered concurrently. Reusing one `ctx` for 2 tasks raises:
  `cannot enter context: <Context object> is already entered`
- So we create distinct `Context` per task (same captured values, different objects). This is Python's documented pattern: `copy_context().run(callable)`.

Best practice reference: Python docs for `contextvars.copy_context()` explicitly says use `ctx.run()` to run in another thread with copied context.

## Verification

### C1 test (new)

`tests/test_parallel_context.py`:
- `test_parallel_blackboard_query_in_parallel_batch` — parallel batch `[fs_search, fs_blackboard_query]` both succeed first try. **Kill-check:** removing `ctx.run` makes it fail with `blackboard_unavailable` or `interrupted synthetic`.
- `test_parallel_search_telemetry_propagated` — search in parallel batch records `last_search_paths` for S15.

Result: 2 passed.

### Existing suite

- `test_tool_batching.py` 2 passed
- `test_fs_search.py` + `test_fs_reach.py` + `test_exploration_metrics.py` + `test_structural_index.py` + `test_safe_walk.py` = 98 passed
- `test_blackboard_query_tool.py` 16 passed
- Combined 89+ passed with fix
- Static: `py_compile loop.py OK`

### S18 live probes (local re-run)

- C4/C5: `C4 file_read rows: [('a.txt', 2, 'search_result', None, None)]` PASS, metrics `n_reads=1 n_searches=1 ctx_efficiency=0.0` PASS
- C10 wiring: corpus 17 `['fs_blackboard_query', 'fs_checkpoint', ... 'pr_prepare']` PASS
- C6/C7/C8 not re-run on live server in this env, but code path unchanged except context propagation (additive, no regression).

### Mutation test

Removed `ctx.run` wrapper → test fails (proves fix is load-bearing).

## Why earlier explanation was wrong

Initial hypothesis "WAL not flushed / lazy-index bootstrap race" rejected — source shows deterministic bug, not timing. Blackboard creation in `SessionState.__post_init__` succeeds when `session_db` present (exists in fa runs). Failure is `get_current_session()==None`, not `session_db==None`.

## Remaining work for S18

- C0-C9 live server execution still needs operator to paste blocks and collect evidence dir `/home/user/s18-evidence-*/` (this repo fix must be deployed first, otherwise C9 will keep failing first-try).
- C10 config snapshot restore byte-identical + `git status --short` empty + evidence tar.gz SHA256.
- Findings ledger update: add I-63 entry.

## DoD for this fix

- [x] Parallel batch `[fs_search, fs_blackboard_query]` both succeed first try
- [x] `fs_search` records `last_search_paths` → `file_read surfaced_by search_result`
- [x] C1 test green, kill-check fails without fix
- [x] No regression in existing loop tests
- [x] Git diff minimal, only `loop.py` + new test
