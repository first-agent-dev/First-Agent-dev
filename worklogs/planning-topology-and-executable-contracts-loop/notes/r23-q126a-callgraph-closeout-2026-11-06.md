# Q126-A / R23 two-path call-graph audit and closeout

**Date:** 2026-11-06

**Disposition:** R23 is **RETIRED / NOT APPLICABLE TO MANAGED W0**, not PASS. Q126-A is implemented. Global W0 remains OPEN; W1 has not started.

This note supplements, and does not rewrite, the archived external snapshot [`w0-external-audit-and-r23-handoff-2026-11-04.md`](w0-external-audit-and-r23-handoff-2026-11-04.md). It records current source and local test evidence for the approved two-path audit. It is not Docker, deployed-host, or live-E2E evidence.

## 1. Dormant isolated Git-worktree producer

`src/fa/workspace/worktree_manager.py::IsolatedWorktreeManager` contains the old host-Git branch probes, `git worktree add`, cleanup, and prune operations. The production lifecycle reaches `WorktreeManagerFactory` from `SessionState`; the factory accepts only `shared` and refuses `isolated`. The actual `SessionState` refusal records a `worktree.mode` config warning, creates no `.fa/worktrees` directory, and runs no subprocess. The legacy class remains only for direct historical characterization in its module; it is no longer re-exported from `fa.workspace`, and the factory does not treat it as a supported upgrade path.

No production caller of `IsolatedWorktreeManager.create_subagent_workspace`, its branch probes, or its cleanup exists. `tests/test_worktree_defensive.py` directly tests the class on temporary repositories; those tests are component characterization, not product-route evidence.

## 2. Distinct legacy host-runner/artifact-root route

The old `spawn_subagent.py` path did **not** call the isolated Git-worktree producer. Its `SessionState.create_subagent_workspace` path creates a guarded `.fa/subagents/...` artifact root via `ensure_subagent_artifact_root`, then the legacy tool calls host `SubagentRunner`. Q126-A moves supported subagent scenarios to managed R13, so product registries no longer bind that legacy builder:

- the unmanaged chat profile no longer declares `fs_spawn_subagent`, and `_add_optional_tool_builders` no longer binds `build_spawn_subagent_tool`;
- `_register_extra_tools` no longer adds the legacy tool to baseline, planner, eval, chat, or other unmanaged registries;
- `_build_run_tool_registry` therefore cannot dispatch the legacy handler for chat/planner/coder/eval;
- `src/fa/cli.py::_register_managed_subagent_tool` remains the sole supported caller edge. It requires a managed workspace and stage lease and binds `build_managed_subagent_tool`; the managed tool uses a pinned read view and does not invoke `SubagentRunner`.

The feature flags used by R13 remain intact. The shared manager, artifact-root derivation, cleanup safeguards, and old helper module remain for direct characterization; manually constructing the legacy helper is not a supported product route or a managed fallback. The legacy `fa workflow` command is unchanged.

## Production-path and no-effect evidence

- `tests/test_managed_registry_binding.py::test_session_state_rejects_isolated_worktree_without_git_effects` drives the real `SessionState`→factory edge in a temporary Git repo. It asserts no manager, no Git subprocess, no `.fa/worktrees`, and the visible config warning.
- `tests/test_managed_registry_binding.py::test_unmanaged_product_run_registries_omit_legacy_host_subagent` covers chat/planner/coder/eval through `cli._build_run_tool_registry`; it asserts the tool is absent, `SubagentRunner` is not called, and no artifact root is created.
- `tests/test_execution_composition.py::test_subagent_commands_carry_no_proxy_credential` exercises the managed `fa workflow` caller with unavailable, unapproved, and approved local backends, both workflow-owner modes. It keeps the R13 managed route exercised and observes no legacy `SubagentRunner`/host Bash fallback. This is R13 caller evidence, not an R23 PASS.
- Direct legacy helper tests explicitly register the old builder themselves and are documented as historical characterization only: `tests/test_slice5_6_7_wiring.py`, `tests/test_subagent_termination_wiring.py`, and `tests/test_worktree_defensive.py`. They are not evidence that a product registry exposes the legacy route.

## Verification

The focused bank passed **115 passed**:

```text
.venv/bin/pytest -q tests/test_managed_registry_binding.py tests/test_chat_role.py tests/test_quality_slice_coverage.py tests/test_prompt_registry_coherence.py tests/test_slice5_6_7_wiring.py tests/test_subagent_termination_wiring.py tests/test_s5_isolation_boundary.py::test_isolated_mode_rejected_at_config_load tests/test_s5_isolation_boundary.py::test_isolated_mode_surfaces_a_config_warning tests/test_worktree_defensive.py tests/test_managed_subagent.py tests/test_execution_composition.py::test_subagent_commands_carry_no_proxy_credential
```

Ruff check, `ruff format --check`, compileall, and `git diff --check` passed; `python scripts/check_doc_links.py` passed for 330 Markdown files. A first assertion attempt used `ToolRegistry.lookup()` as a nullable API; because absence raises `KeyError`, the oracle was corrected to inspect `registry.names()` and the final bank passed.

Four focused mutations were each killed and the source restored byte-for-byte:

1. Re-enable the legacy profile builder → the chat production-registry exclusion test fails.
2. Re-enable legacy registration in `_register_extra_tools` → the coder product-registry exclusion test fails.
3. Let `WorktreeManagerFactory` accept `isolated` → the SessionState no-manager/no-worktree oracle fails in a Git-backed temporary workspace.
4. Remove the managed R13 registration edge → all six parameterizations of the managed `fa workflow` caller test fail.

## Q113/W0 boundary

Q126-A removes R23 from the **active managed W0 set** and records it as retired/not applicable, not as a passing oracle. At E469, Q113's remaining set was 27 rows, R01–R22 and R24–R28. Subsequent Q131-C/E477 removes the unused R21 helper/export and retires R21 separately as NOT APPLICABLE TO MANAGED W0, not PASS. At E477, the then-current Q113 active set was 26 rows, R01–R20, R22, and R24–R28. Q132-D/E481 deferred R24 to W2 (OPEN, not PASS/N/A), initially leaving 25 rows. Q133-B/E482 then defers R25/R26 to W2 and R28 to W1, all still OPEN and not PASS/N/A; the current W0 active set is R01–R20, R22, and R27 (22 rows). Global W0 remains OPEN until all 22 pass through their required production callers. W1 may begin only after those 22 pass, and R28 must pass before W1 closes; require R24–R26 before W2 closes. No Docker or live-host work was run.
