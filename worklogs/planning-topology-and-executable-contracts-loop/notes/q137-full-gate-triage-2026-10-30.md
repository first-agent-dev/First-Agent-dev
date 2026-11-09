# Q137 — Full pytest/Pyrefly gate triage (2026-10-30)

**Status: BLOCKING.** W0 remains closed. W1 implementation remains paused pending closure or explicit disposition of these findings. The original exact lists below are the initial full-gate snapshot after PY-SRC-01; the follow-up section records the latest verified run after the first Q137 repair slice. No gate readiness is claimed. Q135 (deferred F2–F4) and Q136 (Pylint) remain separate.

**Operator disposition (2026-10-30):** selected **A — Strict gate closure, best effort**. Individual findings needing direct review may be deferred in the tracker, but remain **BLOCKING**; that is not a pass, waiver, or permission to advance W1.

## Recovered snapshot and CT113 handoff typing follow-up

The patch was recovered onto `9ba095d` in `0fcc93a`, retaining the feature commit's link-availability guards and its uploaded patch. The initial recovery retained the longer skill injections; `756576d` restored the patch's compact injections while preserving the CT88/CT89 E2E handoff wording. The corresponding condensate and skill-conformance banks passed (48 passed); removing `run sheet` from the restored wording killed the conformance test, and the file was restored byte-identically. This was a documentation/injection recovery correction, not live-host acceptance.

A full baseline on `0fcc93a`, before that injection correction, ran with `GIT_DIR` and `GIT_WORK_TREE` unset: `just test` exited **1**, with **89 failed, 7,137 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in 761.00 seconds. Two failures were the oversized retained injection bodies; the previously recorded skill-conformance failure passed with the longer wording. After the injection correction, the focused 48-test bank passed, but the full pytest gate has **not** been rerun; do not treat the earlier total as the current exact count. Shellcheck was not installed, accounting for 12 skips. Baseline `just _pyrefly` exited **1** with **61 errors**, matching the preceding Q137 count.

The CT113 handoff test now passes explicitly typed peer, namespace, and capability arguments rather than unpacking a mixed-type dictionary; the three foreign-principal/actor/token cases and byte-identical workspace refusal oracle are retained. `pytest -q tests/test_execution_handoff.py --tb=short` exited **0** (17 passed); `pyrefly check tests/test_execution_handoff.py` exited **0** (0 errors); Ruff check, format check, and `git diff --check` exited **0**. Restoring the old dictionary killed the static mutant with the original diagnostic; changing the test caller to send valid proofs killed all three negative cases. The test file was restored byte-identically (SHA-256 `577c1c938f7dbe57bc9b3aa278453412d15377f25cf30eaa6ebdd1958c02bc44`) and the 17-test bank passed again. These are test/static and test-caller mutations, not new production-producer or production-EDGE mutation evidence; no production source was changed. The existing I03-LIVE-27 handoff host plan remains unexecuted.

After this slice, full `just _pyrefly` exited **1** with **60 errors**. Comparing diagnostic message and path to the recovered 61-error run gives **one resolved, zero new**: the unpacked-keyword diagnostic in `tests/test_execution_handoff.py`. The exact prior list remains below as historical evidence. Q137, including its managed mutation-metadata direct-review deferral, remains **BLOCKING**; W1 implementation remains paused.

## CT90 resumed-session preflight fixture repair

The failed `tests/test_verify_gate_live.py::test_plan_preflight_resumed_session_does_not_touch_manifest_or_db` stopped during setup with `managed_execution_unavailable`: `SessionManager._new_session` now requires both the managed materializer and readiness preparer. The test now reuses `tests.test_session_lifecycle._manager` to create the session, then replaces both seams with assertion-failing sentinels before calling the real read-only resolver. It retains exact `workspace_mismatch`, file-set, file-bytes and mtime assertions. The fixture is a local test seam, not proof of a live supervisor or the production CLI edge.

Targeted pytest for this test, the read-only workspace resolver control, the lifecycle provisioning control and missing-provisioner refusal control exited **0** (4 passed). Ruff check, Ruff format check and `git diff --check` exited **0**. Targeted Pyrefly exited **1** with five existing diagnostics in this file; the previous full-gate log also contained five in this file. The full pytest and full Pyrefly gates were not rerun for this slice.

Mutants, each applied separately and restored byte-identically: replacing the resolver's manifest-read producer with the workspace root made the selected path assertion fail; making the resolver call the preparer hit the new assertion sentinel; bypassing the resolver in the test caller failed the selected path assertion. Each targeted pytest invocation exited **1**. The last is only a test-caller mutation, **not** a production CLI EDGE kill. Restored test exited **0** (1 passed). Restored SHA-256: `src/fa/session/manager.py` `c3c83f6580cbb64e633a9fb4e0dfcb91843ecf6cbe29007eb556a4c439c8d549`; `tests/test_verify_gate_live.py` `4ee92a01517b8f45551ba6adc01920892c433fc210696283e16ca83fb1c9bcb8`. No product code changed; this closes only the selected stale test setup, not CT90's full CLI proof or Q137.

No live-host test is claimed. The existing I03 live plan includes ledger-append cases L-RCPT-2/L-RCPT-6 and the separate Q112 session-ledger proposal; this test-only fixture change does not create a new live feature or alter their acceptance scope.

## Commands and exact results

- Full pytest command: `just test` (run with `GIT_DIR` and `GIT_WORK_TREE` unset).
- Result: exit **1**; **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **786.02 s**. Coverage: **85.99%** (80% threshold reached; unrelated to the failure status).
- Full Pyrefly gate: `just _pyrefly`, exit **1**, **114 errors**.
- Current Pyrefly vs valid `HEAD` baseline, comparing `(path, name, concise_description)`: **21 unchanged**, **93 current-only**, **0 resolved**. No current diagnostics are under `src/fa/`.
- Baseline pytest probe: 42 selected failing nodeids from unchanged test files were run on `HEAD`: **41 passed, 1 failed**. The remaining failure was readiness integration's `uv sync --locked --extra dev`, blocked downloading CPython 3.15.2 by TLS `UnknownIssuer`; reproduction is in `/home/user/.cache/arena-gate-triage/uv-sync-repro.log`. This is an environment/baseline observation, not justification to weaken or bypass that test.

## Follow-up verification after the first Q137 repair slice

**Environment recovery.** `bash scripts/arena-env-build.sh` exited **0** and restored the repository-pinned CPython **3.13.16**, frozen dev dependencies, and pinned `uv`/`just` launchers. The final output included `ENVIRONMENT_CHECK_OK` and `ENVIRONMENT_READY`. The script builds into ignored/external cache paths and leaves `.venv` ignored; no tracked environment artifacts were added.

**Repair group: test-only typing in `tests/test_managed_acquisition.py`.** The fixture’s three kind parameters now use the `Literal["missing", "file", "directory", "symlink"]` contract already declared by `PortProjectArtifactListing`; its `WrongDigestPort.read_file` and `TruncatedPort.read_file` overrides now declare `@override`. No production code or runtime behavior changed. Targeted pytest: `./.venv/bin/pytest -q tests/test_managed_acquisition.py` — exit **0**, **90 passed**. Targeted Pyrefly: `./.venv/bin/pyrefly check tests/test_managed_acquisition.py` — exit **0**, **0 errors**. Ruff check, Ruff format check, and `git diff --check` for the test file — exit **0**.

**Mutation proof.** Three static mutants were applied one at a time and restored byte-identically (SHA-256 `9f186607b2b8df108a75c2faf76ccdd7ba83aafd77aa6c3991420e6dcc08ff3c`): widening the three `Literal` parameters back to `str` restored all three `bad-argument-type` diagnostics; removing `@override` from each adversarial port separately restored its `missing-override-decorator` diagnostic. All three mutants were killed. A product producer/caller-EDGE mutation is not applicable: the group changes test fixture typing only and does not alter a production call path.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **858.04 s**. The exact 99 pytest nodeids are unchanged from the initial snapshot. Full `just _pyrefly` exited **1** with **109 errors**; JSON is saved at `/home/user/.cache/arena-gate-triage/pyrefly-after-managed-acquisition-types.json`, full Pyrefly log at `/home/user/.cache/arena-gate-triage/pyrefly-after-managed-acquisition-types.log`, and full pytest log at `/home/user/.cache/arena-gate-triage/pytest-after-managed-acquisition-types.log`. Exact comparison to the initial 114-diagnostic set: **109 unchanged, 5 resolved, 0 new**. Against the valid HEAD baseline, the current set is **21 unchanged baseline + 88 current-only**, with zero diagnostics under `src/fa/`.

### Latest exact Pyrefly diagnostics (109)

- `tests/test_execution_client_port.py:105:9` **missing-override-decorator** — Class member `_CountingClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_execution_client_port.py:120:9` **missing-override-decorator** — Class member `_ScriptedClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_execution_client_port.py:296:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:314:16` **missing-attribute** — Object of class `NeedsClarificationChoice` has no attribute `snapshot`
- `tests/test_execution_client_port.py:339:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:371:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:461:60` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:471:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:699:9` **missing-override-decorator** — Class member `_FramedClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_execution_client_port.py:725:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:739:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:766:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_stage.py:73:17` **implicit-any-parameter** — `_stage_port` is missing an annotation for parameter `managed`
- `tests/test_execution_client_stage.py:73:26` **implicit-any-parameter** — `_stage_port` is missing an annotation for parameter `plan`
- `tests/test_execution_client_stage.py:188:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:253:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:263:54` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:268:57` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:285:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:302:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:316:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_tool_index.py:120:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:134:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:175:51` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_execution_tool_index.py:225:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:240:52` **bad-argument-type** — Argument `_RefusingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:254:52` **bad-argument-type** — Argument `_EofShortPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:271:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:297:62` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:308:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:327:59` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:345:74` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:369:21` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:380:18` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:400:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_port.py:218:65` **bad-argument-type** — Argument `RacingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_bash_tool.py:58:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_discovery_refusal.py:136:91` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:139:64` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_discovery_refusal.py:164:87` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools._register_extra_tools`
- `tests/test_managed_discovery_refusal.py:192:90` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._build_role_registry`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_stage_lease.py:49:9` **missing-override-decorator** — Class member `_RecordingClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_managed_stage_lease.py:57:9` **missing-override-decorator** — Class member `_ReleaseRefusingClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:153:9` **missing-override-decorator** — Class member `LyingStages.stop_view` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_stage_checkpoints.py:159:9` **missing-override-decorator** — Class member `LyingStages.publish` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_stage_checkpoints.py:213:9` **missing-override-decorator** — Class member `TruthyStop.stop_view` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stats.py:158:29` **invalid-argument** — Expected a mapping, got object
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under the selected strict-closure approach. This slice closes five test-only current Pyrefly diagnostics, not the full Pyrefly gate or any pytest failure. Do not advance W1; continue in contract/dependency order and keep any direct-review deferrals explicitly blocking.

## Follow-up verification after the second Q137 repair slice

**Repair group: missing `@override` in test doubles.** Added `@override` to the three `ExecutionClient.request` subclasses, two managed-stage lease client subclasses, and three checkpoint stage adapters in `tests/test_execution_client_port.py`, `tests/test_managed_stage_lease.py`, and `tests/test_stage_checkpoints.py`. These match `ExecutionClient.request` and `StageConnector`; no production source, assertions, or tested behavior changed. The focused suites are C0/C1/C3 as documented in their module headers and preserve their existing production seams.

- Targeted pytest over the three files: exit **0**, **74 passed**.
- Targeted Pyrefly with `--only missing-override-decorator`: exit **0**, **0 errors** (the filter excludes other diagnostic kinds; the full gate below remains authoritative).
- Ruff check, Ruff format check, and `git diff --check` on the three files: exit **0**.
- Eight static mutants, each removing one decorator independently, all restored the expected `missing-override-decorator` diagnostic (exit **1** each). All three test files were restored byte-identically after mutation: `test_execution_client_port.py` SHA-256 `52cd3f5858b206e86c09f8bb0d2132ef18a545968a12ae24a37798310a30c83e`; `test_managed_stage_lease.py` SHA-256 `8b71519b7e31205be0854ee971527ee1a2641743802e83f70e478c33becd2f09`; `test_stage_checkpoints.py` SHA-256 `07bc86e4fa66b7920378a8e47bc9d032e94b91c7bb1477ed3487d9124f97bd1f`. Product producer/EDGE mutations are not applicable to metadata-only edits.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **818.17 s**; coverage was **85.99%**. All **99** pytest failure/error nodeids are identical to the initial snapshot. Full `just _pyrefly` exited **1** with **101 errors**. Against the prior 109-error snapshot: **101 unchanged, 8 resolved, 0 new**. Against the original 114-error snapshot: **101 unchanged, 13 resolved, 0 new**. The latest set contains **18 unchanged HEAD-baseline diagnostics** and **83 current-only diagnostics**; three baseline `@override` diagnostics in `test_stage_checkpoints.py` were resolved. No diagnostics are under `src/fa/`.

Latest full artifacts: `/home/user/.cache/arena-gate-triage/pytest-after-override-decorators.log`, `/home/user/.cache/arena-gate-triage/pyrefly-after-override-decorators.log`, and `/home/user/.cache/arena-gate-triage/pyrefly-after-override-decorators.json`. The exact latest Pyrefly set follows.

### Latest exact Pyrefly diagnostics (101)

- `tests/test_execution_client_port.py:298:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:316:16` **missing-attribute** — Object of class `NeedsClarificationChoice` has no attribute `snapshot`
- `tests/test_execution_client_port.py:341:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:373:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:463:60` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:473:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:728:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:742:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:769:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_stage.py:73:17` **implicit-any-parameter** — `_stage_port` is missing an annotation for parameter `managed`
- `tests/test_execution_client_stage.py:73:26` **implicit-any-parameter** — `_stage_port` is missing an annotation for parameter `plan`
- `tests/test_execution_client_stage.py:188:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:253:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:263:54` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:268:57` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:285:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:302:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:316:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_tool_index.py:120:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:134:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:175:51` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_execution_tool_index.py:225:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:240:52` **bad-argument-type** — Argument `_RefusingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:254:52` **bad-argument-type** — Argument `_EofShortPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:271:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:297:62` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:308:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:327:59` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:345:74` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:369:21` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:380:18` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:400:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_port.py:218:65` **bad-argument-type** — Argument `RacingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_bash_tool.py:58:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_discovery_refusal.py:136:91` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:139:64` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_discovery_refusal.py:164:87` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools._register_extra_tools`
- `tests/test_managed_discovery_refusal.py:192:90` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._build_role_registry`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stats.py:158:29` **invalid-argument** — Expected a mapping, got object
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under the operator-selected A/best-effort approach. The second slice removes eight diagnostics (five current-only and three from the previously unchanged HEAD baseline), but the full gates remain red. Direct-review deferrals, if needed, stay explicitly blocking; W1 does not advance.

## Follow-up verification after the third Q137 repair slice

**Repair group: managed stage-client test typing and fixture preconditions.** In `tests/test_execution_client_stage.py`, `_stage_port` now names its actual `ManagedExecution`, `PlanRef`, and `ClientWorkspacePort` types. The seven direct `ExecutionClient.publish_stage` test seams now assert their grants carry concrete view refs; the foreign-grant case additionally asserts that its view and grant are distinct. This preserves the intended C0 refusal oracle (rather than allowing `None` to trigger the same exception early) and leaves the existing C1/C3 production route tests and behavior unchanged.

- Targeted pytest: `./.venv/bin/pytest -q tests/test_execution_client_stage.py` — exit **0**, **11 passed**.
- Targeted Pyrefly: `./.venv/bin/pyrefly check tests/test_execution_client_stage.py` — exit **0**, **0 errors**.
- Ruff check, Ruff format check, and `git diff --check` — exit **0**.
- Nine static mutants were killed: removing either `_stage_port` parameter annotation restored `implicit-any-parameter`; removing each of the seven view-ref precondition assertions independently restored `bad-argument-type`. All were restored byte-identically; SHA-256 `09e0fe75c93e3b57b27f10bcb3b949f4aaf5b2c7070022abe7feb7eb39c6baed`. Product producer/EDGE mutations are not applicable because this slice changes test typing/preconditions only.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **819.07 s**; coverage was **85.99%**. All **99** pytest failure/error nodeids remain identical to the initial snapshot. Full `just _pyrefly` exited **1** with **92 errors**. Against the prior 101-error set: **92 unchanged, 9 resolved, 0 new**; against the initial 114-error snapshot, **92 unchanged, 22 resolved, 0 new**. The current set is **18 unchanged HEAD-baseline diagnostics + 74 current-only diagnostics**, with none under `src/fa/`.

Latest artifacts: `/home/user/.cache/arena-gate-triage/pytest-after-client-stage-types.log`, `/home/user/.cache/arena-gate-triage/pyrefly-after-client-stage-types.log`, and `/home/user/.cache/arena-gate-triage/pyrefly-after-client-stage-types.json`.

### Latest exact Pyrefly diagnostics (92)

- `tests/test_execution_client_port.py:298:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:316:16` **missing-attribute** — Object of class `NeedsClarificationChoice` has no attribute `snapshot`
- `tests/test_execution_client_port.py:341:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:373:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:463:60` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:473:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:728:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:742:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:769:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_tool_index.py:120:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:134:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:175:51` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_execution_tool_index.py:225:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:240:52` **bad-argument-type** — Argument `_RefusingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:254:52` **bad-argument-type** — Argument `_EofShortPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:271:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:297:62` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:308:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:327:59` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:345:74` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:369:21` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:380:18` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:400:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_port.py:218:65` **bad-argument-type** — Argument `RacingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_bash_tool.py:58:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_discovery_refusal.py:136:91` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:139:64` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_discovery_refusal.py:164:87` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools._register_extra_tools`
- `tests/test_managed_discovery_refusal.py:192:90` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._build_role_registry`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stats.py:158:29` **invalid-argument** — Expected a mapping, got object
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under selected A/best-effort. This slice closes nine test-only diagnostics; no pytest nodeids were resolved. Any direct-review deferral remains blocking, and W1 does not advance.

## Follow-up verification after the fourth Q137 repair slice

**Repair group: managed Bash success-result oracle.** In `tests/test_managed_bash_tool.py`, the positive success case now asserts `answer.result is not None` after confirming `answer.error is None`, before indexing `stdout`. This matches the actual `ToolResult` contract (both fields are independently optional) and prevents a success-shaped result without data from satisfying the assertion. No production behavior or execution fallback changed.

- Targeted pytest: `./.venv/bin/pytest -q tests/test_managed_bash_tool.py` — exit **0**, **9 passed**.
- Targeted Pyrefly: `./.venv/bin/pyrefly check tests/test_managed_bash_tool.py` — exit **0**, **0 errors**.
- Ruff check, Ruff format check, and `git diff --check` — exit **0**.
- Removing the result-narrowing assertion restored the expected `unsupported-operation` (`None` is not subscriptable) diagnostic; mutant Pyrefly exit **1**. The test file was restored byte-identically, SHA-256 `0bbd07e6627253033426ae0f74b2e0d513793f21568d18943c4f26b8b0299178`. Product producer/EDGE mutations are N/A for this test-oracle correction.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **798.06 s**; coverage was **85.99%**. All **99** pytest failure/error nodeids remain identical to the initial snapshot. Full `just _pyrefly` exited **1** with **91 errors**. Against the prior 92-error set: **91 unchanged, 1 resolved, 0 new**; the initial 114-error set has **91 unchanged, 23 resolved, 0 new**. Latest diagnostics comprise **18 unchanged HEAD-baseline** plus **73 current-only**; none are under `src/fa/`.

Latest artifacts: `/home/user/.cache/arena-gate-triage/pytest-after-managed-bash-result-narrowing.log`, `/home/user/.cache/arena-gate-triage/pyrefly-after-managed-bash-result-narrowing.log`, and `/home/user/.cache/arena-gate-triage/pyrefly-after-managed-bash-result-narrowing.json`.

### Latest exact Pyrefly diagnostics (91)

- `tests/test_execution_client_port.py:298:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:316:16` **missing-attribute** — Object of class `NeedsClarificationChoice` has no attribute `snapshot`
- `tests/test_execution_client_port.py:341:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:373:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:463:60` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:473:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:728:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:742:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:769:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_tool_index.py:120:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:134:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:175:51` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_execution_tool_index.py:225:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:240:52` **bad-argument-type** — Argument `_RefusingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:254:52` **bad-argument-type** — Argument `_EofShortPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:271:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:297:62` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:308:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:327:59` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:345:74` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:369:21` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:380:18` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:400:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_port.py:218:65` **bad-argument-type** — Argument `RacingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_discovery_refusal.py:136:91` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:139:64` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_discovery_refusal.py:164:87` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools._register_extra_tools`
- `tests/test_managed_discovery_refusal.py:192:90` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._build_role_registry`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stats.py:158:29` **invalid-argument** — Expected a mapping, got object
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under selected A/best-effort. This slice closes one current-only diagnostic; all pytest failures and direct-review findings remain blocking. W1 does not advance.

## Follow-up verification after the fifth Q137 repair slice

**Repair group: execution-client port test-contract narrowing.** In `tests/test_execution_client_port.py`, five live supervisor tests now assert the managed owner grant has a revision before `pin_reader`; the inventory test asserts the resolver returned `ResolvedExistingIncrement` before reading `.snapshot`; and three direct `stop_view` tests assert their grant has a view before passing it to the client. These are test preconditions for the intended positive/specific authority paths, not product changes. The existing real supervisor/socket, request-count, same-view, and fail-closed assertions remain intact.

- Focused pytest: `./.venv/bin/pytest -q tests/test_execution_client_port.py` — exit **0**, **31 passed**.
- Targeted Pyrefly: `./.venv/bin/pyrefly check tests/test_execution_client_port.py` — exit **0**, **0 errors** (1 suppressed, 1 warning not shown).
- Ruff check and Ruff format check — exit **0**.
- Nine static mutants (five revision assertions, the resolved-variant assertion, and three view assertions) each restored the corresponding `bad-argument-type` or `missing-attribute` diagnostic. All killed and restored byte-identically; SHA-256 `5fe024859844724bbed12fe09ac99fca3e53a6beb29147456344634d26a505f5`. No production producer/EDGE mutation applies to test-only preconditions.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **820.76 s**; coverage **85.98%**. All **99** pytest failure/error nodeids remain identical to the initial snapshot. Full `just _pyrefly` exited **1** with **82 errors**. Against the prior 91-error set: **82 unchanged, 9 resolved, 0 new**; against the initial 114-error snapshot: **82 unchanged, 32 resolved, 0 new**. Latest diagnostics comprise **18 unchanged HEAD-baseline** plus **64 current-only**; none are under `src/fa/`.

Latest artifacts: `/home/user/.cache/arena-gate-triage/pytest-after-execution-client-port-narrowings.log`, `/home/user/.cache/arena-gate-triage/pyrefly-after-execution-client-port-narrowings.log`, and `/home/user/.cache/arena-gate-triage/pyrefly-after-execution-client-port-narrowings.json`.

### Latest exact Pyrefly diagnostics (82)

- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_tool_index.py:120:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:134:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:175:51` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_execution_tool_index.py:225:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:240:52` **bad-argument-type** — Argument `_RefusingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:254:52` **bad-argument-type** — Argument `_EofShortPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:271:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:297:62` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:308:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:327:59` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:345:74` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:369:21` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:380:18` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:400:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_port.py:218:65` **bad-argument-type** — Argument `RacingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_discovery_refusal.py:136:91` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:139:64` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_discovery_refusal.py:164:87` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools._register_extra_tools`
- `tests/test_managed_discovery_refusal.py:192:90` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._build_role_registry`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stats.py:158:29` **invalid-argument** — Expected a mapping, got object
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under selected A/best-effort. This slice closes nine current-only diagnostics; all pytest failures and any direct-review deferrals remain blocking. W1 does not advance.

## Follow-up verification after the sixth Q137 repair slice

**Repair group: typed session-summary fixture content.** In `tests/test_stats.py`, the verdict-precedence test now stores the summary content, asserts it is a `dict`, then adds the coder role, failing exit code, and stop reason. The existing `parse_session` assertions remain unchanged; this is a fixture-shape precondition, not a product edit.

- Focused pytest: `./.venv/bin/pytest -q tests/test_stats.py` — exit **0**, **19 passed**.
- Targeted Pyrefly: `./.venv/bin/pyrefly check tests/test_stats.py` — exit **0**, **0 errors**.
- Ruff check and Ruff format check — exit **0**.
- Removing the `isinstance(content, dict)` narrowing restored `invalid-argument: Expected a mapping, got object`; mutant Pyrefly exit **1**. File restored byte-identically, SHA-256 `ffd5d36bc66942dca2157a5db126c078ac0bef30acc178900e5d828778980395`. Producer/EDGE mutations are N/A for this fixture typing repair.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **810.97 s**; coverage **85.98%**. All **99** pytest failure/error nodeids remain identical to the initial snapshot. Full `just _pyrefly` exited **1** with **81 errors**. Against the prior 82-error set: **81 unchanged, 1 resolved, 0 new**; against the initial 114-error snapshot: **81 unchanged, 33 resolved, 0 new**. Latest diagnostics comprise **18 unchanged HEAD-baseline** plus **63 current-only**; none are under `src/fa/`.

Latest artifacts: `/home/user/.cache/arena-gate-triage/pytest-after-stats-content-narrowing.log`, `/home/user/.cache/arena-gate-triage/pyrefly-after-stats-content-narrowing.log`, and `/home/user/.cache/arena-gate-triage/pyrefly-after-stats-content-narrowing.json`.

### Latest exact Pyrefly diagnostics (81)

- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_tool_index.py:120:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:134:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:175:51` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_execution_tool_index.py:225:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:240:52` **bad-argument-type** — Argument `_RefusingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:254:52` **bad-argument-type** — Argument `_EofShortPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:271:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:297:62` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:308:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:327:59` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:345:74` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:369:21` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:380:18` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:400:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_port.py:218:65` **bad-argument-type** — Argument `RacingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_discovery_refusal.py:136:91` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:139:64` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_discovery_refusal.py:164:87` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools._register_extra_tools`
- `tests/test_managed_discovery_refusal.py:192:90` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._build_role_registry`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under selected A/best-effort. This slice closes one current-only diagnostic; all pytest failures and any direct-review deferrals remain blocking. W1 does not advance.

## Follow-up verification after the seventh Q137 repair slice

**Repair group: workspace-port race wrapper contract.** In `tests/test_execution_tool_port.py`, the C1 `RacingPort` now implements the required project-listing method as a fail-fast sentinel. Listing is outside this edit-race test; accidental `edit_file` use of that capability raises immediately rather than silently delegating. No product implementation changed.

- Focused pytest: `./.venv/bin/pytest -q tests/test_execution_tool_port.py` — exit **0**, **21 passed**.
- Targeted Pyrefly: `./.venv/bin/pyrefly check tests/test_execution_tool_port.py` — exit **0**, **0 errors**.
- Ruff check and Ruff format check — exit **0**.
- Removing the sentinel method restored the `bad-argument-type`/missing-Protocol-member diagnostic; mutant killed and test file restored byte-identically, SHA-256 `638609342cf51b7da87f21604ae719be2c23f390fdb507763889206600327023`.
- Caller EDGE kill-check: temporary injection of `list_project_artifacts` into `edit_file` caused the focused C1 race test to fail on the sentinel; caller mutation was restored byte-identically, SHA-256 `4d19c5816ccea55bc4c35fece1412ed616284215f5e5a91b140f3f5d4c9777a1`.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **815.10 s**; coverage **85.98%**. All **99** pytest failure/error nodeids remain identical to the initial snapshot. Full `just _pyrefly` exited **1** with **80 errors**. Against the prior 81-error set: **80 unchanged, 1 resolved, 0 new**; against the initial 114-error snapshot: **80 unchanged, 34 resolved, 0 new**. Latest diagnostics comprise **18 unchanged HEAD-baseline** plus **62 current-only**; none are under `src/fa/`.

Latest artifacts: `/home/user/.cache/arena-gate-triage/pytest-after-execution-tool-port-workspace-protocol.log`, `/home/user/.cache/arena-gate-triage/pyrefly-after-execution-tool-port-workspace-protocol.log`, and `/home/user/.cache/arena-gate-triage/pyrefly-after-execution-tool-port-workspace-protocol.json`.

### Latest exact Pyrefly diagnostics (80)

- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_tool_index.py:120:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:134:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:175:51` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_execution_tool_index.py:225:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:240:52` **bad-argument-type** — Argument `_RefusingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:254:52` **bad-argument-type** — Argument `_EofShortPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:271:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:297:62` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:308:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:327:59` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:345:74` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:369:21` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:380:18` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:400:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:136:91` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:139:64` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_discovery_refusal.py:164:87` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools._register_extra_tools`
- `tests/test_managed_discovery_refusal.py:192:90` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._build_role_registry`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under selected A/best-effort. This slice closes one current-only diagnostic; all pytest failures and any direct-review deferrals remain blocking. W1 does not advance.

## Follow-up verification after the eighth Q137 repair slice

**Repair group: shared indexing/read port stubs.** In `tests/test_execution_tool_index.py`, `_CachePort` now exposes the `WorkspacePort.list_project_artifacts` method as a fail-fast sentinel; its refusing, short-read, and exploding subclasses inherit the same contract. These fakes intentionally do not support project listing, and unexpected listing now fails instead of being silently accepted. No production source changed.

- Focused pytest: `./.venv/bin/pytest -q tests/test_execution_tool_index.py` — exit **0**, **21 passed**.
- Targeted Pyrefly: `./.venv/bin/pyrefly check tests/test_execution_tool_index.py` — exit **0**, **0 errors**.
- Ruff check and Ruff format check — exit **0**.
- Removing the sentinel restored **14** `bad-argument-type` diagnostics in this file. The same missing member also explained four diagnostics in `tests/test_managed_discovery_refusal.py`; the shared-port correction resolves **18 total** current diagnostics. Mutant killed; test file restored byte-identically, SHA-256 `bade9bdad0642d6efa4516fc5fe6c2ee25de1fc88822257581db1aeb64e00057`.
- Caller EDGE kill-check: a temporary listing call in managed `read_file` caused `test_an_oversized_managed_read_names_the_bound` to fail on the sentinel. Caller source restored byte-identically, SHA-256 `7056393802a37ae5fe709a4efead6ca28596226933d5f122063d224ee57808a0`.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **804.02 s**; coverage **85.95%**. All **99** pytest failure/error nodeids remain identical to the initial snapshot. Full `just _pyrefly` exited **1** with **62 errors**. Against the prior 80-error set: **62 unchanged, 18 resolved, 0 new**; against the initial 114-error snapshot: **62 unchanged, 52 resolved, 0 new**. Latest diagnostics comprise **18 unchanged HEAD-baseline** plus **44 current-only**; none are under `src/fa/`.

Latest artifacts: `/home/user/.cache/arena-gate-triage/pytest-after-execution-tool-index-workspace-protocol.log`, `/home/user/.cache/arena-gate-triage/pyrefly-after-execution-tool-index-workspace-protocol.log`, and `/home/user/.cache/arena-gate-triage/pyrefly-after-execution-tool-index-workspace-protocol.json`.

### Latest exact Pyrefly diagnostics (62)

- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under selected A/best-effort. This slice closes 18 current-only diagnostics; all pytest failures and any direct-review deferrals remain blocking. W1 does not advance.

## Follow-up verification after the ninth Q137 repair slice

**Repair group: incomplete-read edit fixture.** In `tests/test_managed_edit_completeness.py`, the local fake `Port` now implements `WorkspacePort.list_project_artifacts` as an assertion-failing sentinel. This preserves its narrow contract: exercise EOF validation and prove the write count remains zero; project listing is not an accepted substitute for the managed read.

- Focused pytest: `./.venv/bin/pytest -q tests/test_managed_edit_completeness.py` — exit **0**, **7 passed**.
- Targeted Pyrefly: `./.venv/bin/pyrefly check tests/test_managed_edit_completeness.py` — exit **0**, **0 errors**.
- Ruff check and Ruff format check — exit **0**.
- Removing the sentinel restored the expected `bad-argument-type` missing-Protocol-member diagnostic; mutant killed and test file restored byte-identically, SHA-256 `b2aee0afd1c67555179237ab3fbfe1e22315e62f0bb4d9dac51fddc6d4818941`.
- Caller EDGE check: an initial temporary mutation targeted the wrong consumer (`read_file.py`); the selected test passed, so that attempt was not counted as a kill. After restoring it, the mutation was correctly applied to `edit_file.py`; `test_unconfirmed_eof_never_reaches_write` failed on the sentinel as intended. The caller was restored byte-identically, SHA-256 `4d19c5816ccea55bc4c35fece1412ed616284215f5e5a91b140f3f5d4c9777a1`.

**Latest full gates.** With `GIT_DIR` and `GIT_WORK_TREE` unset, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/just test` exited **1**: **88 failed, 7,138 passed, 18 skipped, 4 xfailed, 2 warnings, 11 errors** in **813.93 s**; coverage **85.99%**. All **99** pytest failure/error nodeids remain identical to the initial snapshot. Full `just _pyrefly` exited **1** with **61 errors**. Against the prior 62-error set: **61 unchanged, 1 resolved, 0 new**; against the initial 114-error snapshot: **61 unchanged, 53 resolved, 0 new**. Latest diagnostics comprise **18 unchanged HEAD-baseline** plus **43 current-only**; none are under `src/fa/`.

Latest artifacts: `/home/user/.cache/arena-gate-triage/pytest-after-managed-edit-completeness-workspace-protocol.log`, `/home/user/.cache/arena-gate-triage/pyrefly-after-managed-edit-completeness-workspace-protocol.log`, and `/home/user/.cache/arena-gate-triage/pyrefly-after-managed-edit-completeness-workspace-protocol.json`.

### Latest exact Pyrefly diagnostics (61)

- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:344:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

**Disposition.** Q137 remains **BLOCKING** under selected A/best-effort. This slice closes one current-only diagnostic; all pytest failures and any direct-review deferrals remain blocking. W1 does not advance.

## Direct-review deferral — managed mutation metadata test fake (still BLOCKING)

The three current-only diagnostics in `tests/test_managed_mutation_metadata.py` (lines 63, 100, and 128) arise because `_Port` is passed as `WorkspacePort` while one parametrized case intentionally supplies `object()` as the result of `read_file`; `managed_version_dependencies` explicitly rejects malformed runtime replies. An exploratory test-only expansion added `cache_dir`, list/write sentinels, and the full read signature, but Pyrefly then reported the intentional `Any` return was not assignable to `PortRead`. Resolving that without a cast/type escape, removing or weakening the malformed-reply case, or changing the production contract needs direct review of whether this helper should depend on the full `WorkspacePort` or a narrower read-only protocol.

- Exploratory focused pytest: `./.venv/bin/pytest -q tests/test_managed_mutation_metadata.py` — exit **0**, **7 passed**.
- Exploratory Pyrefly remained red with **3** `bad-argument-type` diagnostics (the malformed reply return was still `Any`). Ruff check passed; Ruff format check failed on the temporary line wrapping.
- All partial test edits were reverted. After reversion, focused pytest again exited **0** (**7 passed**), Ruff check and format check exited **0**, and targeted Pyrefly reports the original **3** `bad-argument-type` diagnostics requiring `cache_dir`.
- No production source was changed and no full-gate rerun was made after the exact reversion. The latest full gates and counts above remain the current Q137 snapshot.

**Disposition under selected A:** defer this contract decision to direct review; keep all three diagnostics and both full gates **BLOCKING**. This is not a waiver or a reduction of the 43 current-only diagnostics. W1 remains paused.

## Triage interpretation

- The refreshed pytest failures include many paths stopped by the required managed-provisioner refusal (`managed_execution_unavailable`) or by an unapproved execution profile (`UNAPPROVED_PROFILE`). These results identify test/setup paths that must be checked against the accepted managed execution/profile contract; they do **not** establish that production refusal behavior is wrong. Do not add a fallback or weaken fail-closed behavior.
- Other current pytest findings include feature-flag usage/dead-flag checks, C901 complexity-ratchet drift, S127 budget/outline drift, tool-name/schema portability, skill conformance, vulture, read-only-operation-set mismatch, and domain/CLI assertions. Their exact nodeids are below; each still needs contract/dependency-order triage.
- In the initial set, all 93 current-only Pyrefly errors were in tests, not `src/fa/`; after the two verified repair slices, the latest set has 43 current-only errors and 18 remaining unchanged HEAD test diagnostics (three baseline diagnostics were repaired). No Pyrefly suppression or test weakening has been applied.
- Initial-run artifacts were emitted under `/home/user/.cache/arena-gate-triage/` as `pytest-after-source.log`, `pyrefly-after-source.json`, `pyrefly-after-source.stderr`, `pyrefly-head.json`, and `pyrefly-head.stderr`. The exact initial nodeids/diagnostics are preserved below; the latest full artifacts are listed in the follow-up section.

## Exact pytest nodeids

### Failed (88)

- `tests/test_dead_flags.py::TestDeadFlagsUnit::test_no_dead_flags_on_clean_tree`
- `tests/test_dead_flags.py::TestDeadFlagsUnit::test_all_current_fields_present`
- `tests/test_dead_flags.py::TestDeadFlagsUnit::test_each_field_has_usage`
- `tests/test_dead_flags.py::TestDeadFlagsCLI::test_exit_code_zero_on_clean_tree`
- `tests/test_dead_flags.py::TestDeadFlagsCLI::test_json_output_valid`
- `tests/test_dead_flags.py::TestDeadFlagsCLI::test_text_output_no_dead`
- `tests/test_execution_pty_control.py::test_a_foreign_view_or_grant_is_unauthorized_and_sends_nothing`
- `tests/test_iteration_cap.py::test_cmd_run_applies_config_per_role_limit_end_to_end`
- `tests/test_pyrefly_import_topology.py::test_pyrefly_check_passes`
- `tests/test_readiness_announcement.py::test_drive_path_announces_ready_workspace`
- `tests/test_readiness_announcement.py::test_drive_path_silent_without_venv`
- `tests/test_s10a_cli_coverage.py::test_s10a_authoring_check_runs_on_a_real_workspace`
- `tests/test_s10a_cli_coverage.py::test_s10a_run_proxy_mode_rewrites_the_chain`
- `tests/test_s10a_cli_coverage.py::test_s10a_stats_renders_a_real_session`
- `tests/test_s10a_cli_coverage.py::test_s10a_stats_aggregate_across_sessions`
- `tests/test_s10a_cli_coverage.py::test_s10a_stats_console_render_and_dead_zones`
- `tests/test_s10a_cli_coverage.py::test_s10a_stats_reports_source_errors_from_discovery`
- `tests/test_s10a_cli_coverage.py::test_s10a_run_resume_reads_the_existing_draft`
- `tests/test_s10a_cli_coverage.py::test_s10a_run_builds_compactor_chain_under_proxy`
- `tests/test_s10b_cli_parity.py::test_s10b_parity_happy_path`
- `tests/test_s10b_cli_parity.py::test_s10b_parity_quiet_mode_moves_status_off_stdout`
- `tests/test_s10b_cli_parity.py::test_s10b_parity_proxy_mode`
- `tests/test_s10b_cli_parity.py::test_s10b_parity_proxy_mode_builds_compactor_chain`
- `tests/test_s10b_cli_parity.py::test_s10b_parity_outcome_sink_suppresses_global_history_export`
- `tests/test_s10b_cli_parity.py::test_s10b_parity_without_sink_exports_global_history`
- `tests/test_s10b_cli_parity.py::test_s10b_stats_parity_dead_zones_report`
- `tests/test_s10b_cli_parity.py::test_s10b_stats_parity_single_session_json_shape`
- `tests/test_s10b_complexity_ratchet.py::test_s13_11_c901_ratchet_tracks_retired_waiver`
- `tests/test_s10b_complexity_ratchet.py::test_s10b_c901_waiver_budget`
- `tests/test_s10b_complexity_ratchet.py::test_s10b_retired_waiver_stays_retired[_cmd_run]`
- `tests/test_s10c_artifact_posture.py::test_s10c_session_dir_is_private_at_creation_without_the_repair_pass`
- `tests/test_s127_budget.py::test_s127_scatter_table_matches_registry`
- `tests/test_s127_outline.py::test_s127_fold_cli_py_matches_ast_truth`
- `tests/test_s13_10_tool_names.py::test_composition_root_rejects_non_portable_name`
- `tests/test_s13_10_tool_names.py::test_composition_root_accepts_a_non_fs_pr_prefixed_name`
- `tests/test_s7_cli_run_paths.py::test_output_mode_never_suppresses_the_durable_trace[D-console]`
- `tests/test_s7_cli_run_paths.py::test_output_mode_never_suppresses_the_durable_trace[D-quiet]`
- `tests/test_s7_cli_run_paths.py::test_two_runs_in_one_process_do_not_leak_session_state`
- `tests/test_s9_stats_projection.py::test_s9_authority_and_projection_agree`
- `tests/test_s9_stats_projection.py::test_s9_discovery_rejects_manifest_pointing_elsewhere`
- `tests/test_s9_stats_projection.py::test_s9_discovery_rejects_inactive_manifest`
- `tests/test_s9_stats_projection.py::test_s9_run_id_reuse_is_refused_so_reexport_cannot_occur`
- `tests/test_scope_hint_cache_key.py::test_live_hint_reaches_the_model`
- `tests/test_scope_hint_cache_key.py::test_live_agents_map_is_identical_across_estimates`
- `tests/test_skill_conformance.py::test_transferred_e2e_roles_and_ready_semantics_are_preserved`
- `tests/test_tool_schema_portability.py::test_every_current_role_tool_schema_satisfies_pts_v1`
- `tests/test_verify_gate_live.py::test_plan_preflight_resumed_session_does_not_touch_manifest_or_db`
- `tests/test_verify_gate_live.py::test_plan_preflight_real_cli_uses_selected_workspace_not_cwd[False]`
- `tests/test_verify_gate_live.py::test_plan_preflight_real_cli_uses_selected_workspace_not_cwd[True]`
- `tests/test_verify_gate_live.py::test_plan_preflight_resolver_rejects_invalid_session_without_writes[unknown-unknown_session]`
- `tests/test_verify_gate_live.py::test_plan_preflight_resolver_rejects_invalid_session_without_writes[missing-workspace-workspace_missing]`
- `tests/test_verify_gate_live.py::test_plan_preflight_resolver_rejects_invalid_session_without_writes[corrupt-manifest_corrupt]`
- `tests/test_verify_gate_live.py::test_plan_preflight_resolver_rejects_invalid_session_without_writes[inactive-session_not_active]`
- `tests/test_verify_gate_live.py::test_plan_preflight_resolver_rejects_invalid_session_without_writes[escape-path_escape]`
- `tests/test_verify_gate_live.py::test_plan_preflight_new_workspace_cannot_bypass_existing_owner`
- `tests/test_verify_gate_live.py::test_plan_preflight_allocated_workspace_mismatch_blocks_provider`
- `tests/test_verify_gate_live.py::test_ct91_public_q68_failed_prepare_invalidates_even_after_recovery[observe]`
- `tests/test_verify_gate_live.py::test_ct91_public_q68_failed_prepare_invalidates_even_after_recovery[enforce]`
- `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[None]`
- `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[coder]`
- `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[planner]`
- `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[planner,eval]`
- `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[eval]`
- `tests/test_vulture_clean.py::test_vulture_clean_src`
- `tests/test_workflow_global_history.py::test_standalone_run_still_exports_its_own_row`
- `tests/test_workspace_authorize.py::test_exec_authorizes_the_stored_plan_not_a_payload_claim`
- `tests/test_workspace_authorize.py::test_the_readonly_classification_covers_the_closed_enum`
- `tests/test_workspace_publication.py::test_seal_leaves_canonical_bytes_current_and_pins_untouched`
- `tests/test_workspace_publication.py::test_pinned_readers_keep_the_old_revision_across_publish`
- `tests/test_workspace_publication.py::test_publish_plan_replaces_the_canonical_file_and_commits_a_revision`
- `tests/test_workspace_publication.py::test_candidate_publish_applies_a_patch_after_an_unrelated_revision_commit`
- `tests/test_workspace_publication.py::test_candidate_publish_refuses_plan_bytes_that_moved_since_the_snapshot`
- `tests/test_workspace_publication.py::test_candidate_publish_of_the_current_bytes_reports_a_repeat_and_writes_nothing`
- `tests/test_workspace_publication.py::test_publish_plan_refuses_bytes_that_are_not_a_plan`
- `tests/test_workspace_publication.py::test_publish_plan_requires_the_owner_grant_and_no_live_view`
- `tests/test_workspace_publication.py::test_candidate_publish_requires_closed_view_and_matching_terminal_receipt`
- `tests/test_workspace_publication.py::test_record_terminal_does_not_substitute_for_draining_active_candidate_work`
- `tests/test_workspace_publication.py::test_candidate_publish_refuses_owner_capability_in_place_of_view_grant`
- `tests/test_workspace_publication.py::test_publish_plan_refuses_a_plan_swapped_for_a_link_before_the_replace`
- `tests/test_workspace_publication.py::test_publish_plan_refuses_after_a_concurrent_write_between_staging_and_replace`
- `tests/test_workspace_publication.py::test_publish_plan_refuses_bytes_that_are_not_the_ones_it_staged`
- `tests/test_workspace_publication.py::test_publish_plan_refuses_a_replaced_plan_with_the_wrong_mode`
- `tests/test_workspace_publication.py::test_a_failure_after_the_plan_replace_keeps_the_new_bytes_and_the_intent`
- `tests/test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication`
- `tests/test_workspace_recovery.py::test_recovery_completes_a_replaced_plan_forward`
- `tests/test_workspace_recovery.py::test_recovery_clears_a_plan_intent_when_the_old_bytes_are_still_there`
- `tests/test_workspace_recovery.py::test_recovery_refuses_a_plan_that_matches_neither_hash`
- `tests/test_workspace_recovery.py::test_recovery_refuses_a_plan_intent_that_does_not_describe_the_bytes`

### Errors (11)

- `tests/test_s10c_artifact_posture.py::test_s10c_no_artifact_is_group_or_world_accessible`
- `tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[global_history.db]`
- `tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[session-log/posture/events.jsonl]`
- `tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[session-log/posture/llm_bodies.jsonl]`
- `tests/test_s10c_artifact_posture.py::test_s10c_session_db_and_wal_sidecars_are_private`
- `tests/test_s10c_artifact_posture.py::test_s10c_directories_are_0700`
- `tests/test_s7_correlation.py::test_every_trace_row_carries_the_run_and_session_identity`
- `tests/test_s7_correlation.py::test_event_ids_are_unique_and_ordered_within_the_run`
- `tests/test_s7_correlation.py::test_logical_call_id_joins_the_trace_to_the_captured_body`
- `tests/test_s7_correlation.py::test_one_provider_call_correlates_its_attempt_and_call_rows`
- `tests/test_s7_correlation.py::test_documented_non_join_tool_call_id_is_empty_without_tool_calls`

## Initial full Pyrefly diagnostics after PY-SRC-01 (114)

### Diagnostic-kind counts

- `bad-argument-type`: 81
- `missing-override-decorator`: 10
- `unsupported-operation`: 10
- `missing-attribute`: 5
- `implicit-any-parameter`: 2
- `missing-argument`: 2
- `implicit-any-attribute`: 1
- `bad-unpacking`: 1
- `bad-assignment`: 1
- `invalid-argument`: 1

### Exact diagnostics

- `tests/test_execution_client_port.py:105:9` **missing-override-decorator** — Class member `_CountingClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_execution_client_port.py:120:9` **missing-override-decorator** — Class member `_ScriptedClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_execution_client_port.py:296:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:314:16` **missing-attribute** — Object of class `NeedsClarificationChoice` has no attribute `snapshot`
- `tests/test_execution_client_port.py:339:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:371:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:461:60` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:471:65` **bad-argument-type** — Argument `str | None` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.client.ExecutionClient.pin_reader`
- `tests/test_execution_client_port.py:699:9` **missing-override-decorator** — Class member `_FramedClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_execution_client_port.py:725:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:739:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_port.py:766:48` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.stop_view`
- `tests/test_execution_client_stage.py:73:17` **implicit-any-parameter** — `_stage_port` is missing an annotation for parameter `managed`
- `tests/test_execution_client_stage.py:73:26` **implicit-any-parameter** — `_stage_port` is missing an annotation for parameter `plan`
- `tests/test_execution_client_stage.py:188:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:253:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:263:54` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:268:57` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:285:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:302:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_client_stage.py:316:49` **bad-argument-type** — Argument `ViewRef | None` is not assignable to parameter `view` with type `ViewRef` in function `fa.execution.client.ExecutionClient.publish_stage`
- `tests/test_execution_composition.py:229:33` **implicit-any-attribute** — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation.
- `tests/test_execution_composition.py:305:13` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage`
- `tests/test_execution_composition.py:557:30` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:2806:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace`
- `tests/test_execution_composition.py:2966:9` **bad-argument-type** — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__`
- `tests/test_execution_composition.py:3051:34` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow`
- `tests/test_execution_composition.py:3342:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3346:43` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3352:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3357:39` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_composition.py:3360:42` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._session_manager_for_args`
- `tests/test_execution_handoff.py:200:32` **bad-argument-type** — Unpacked keyword argument `NamespaceRef | PeerIdentity | str` is not assignable to parameter `target` with type `NamespaceRef` in function `move`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `run_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:43` **missing-argument** — Missing argument `session_id` in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_receipts.py:710:46` **bad-unpacking** — Expected argument after ** to be a mapping, got: dict[str, Unknown] | str | Any in function `fa.execution.types.NamespaceRef.__init__`
- `tests/test_execution_tool_index.py:120:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:134:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_index.py:175:51` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_execution_tool_index.py:225:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:240:52` **bad-argument-type** — Argument `_RefusingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:254:52` **bad-argument-type** — Argument `_EofShortPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:271:52` **bad-argument-type** — Argument `_ExplodingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.read_file.build_read_file_tool`
- `tests/test_execution_tool_index.py:297:62` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:308:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:327:59` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.build_baseline_registry`
- `tests/test_execution_tool_index.py:345:74` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.profiles.build_registry_for_role`
- `tests/test_execution_tool_index.py:369:21` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:380:18` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `port` with type `WorkspacePort | None` in function `fa.inner_loop.tools.workspace_port.index_db`
- `tests/test_execution_tool_index.py:400:77` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_execution_tool_port.py:218:65` **bad-argument-type** — Argument `RacingPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_acquisition.py:562:36` **bad-argument-type** — Argument `str` is not assignable to parameter `project_kind` with type `Literal['directory', 'file', 'missing', 'symlink']` in function `fa.inner_loop.tools.workspace_port.PortProjectArtifactListing.__init__`
- `tests/test_managed_acquisition.py:562:50` **bad-argument-type** — Argument `str` is not assignable to parameter `roadmap_kind` with type `Literal['directory', 'file', 'missing', 'symlink']` in function `fa.inner_loop.tools.workspace_port.PortProjectArtifactListing.__init__`
- `tests/test_managed_acquisition.py:562:64` **bad-argument-type** — Argument `str` is not assignable to parameter `increments_kind` with type `Literal['directory', 'file', 'missing', 'symlink']` in function `fa.inner_loop.tools.workspace_port.PortProjectArtifactListing.__init__`
- `tests/test_managed_acquisition.py:658:13` **missing-override-decorator** — Class member `WrongDigestPort.read_file` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_managed_acquisition.py:671:13` **missing-override-decorator** — Class member `TruncatedPort.read_file` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_managed_bash_tool.py:58:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_discovery_refusal.py:136:91` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_discovery_refusal.py:139:64` **bad-argument-type** — Argument `test_falsey_port_is_still_a_managed_binding.FalseyPort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_discovery_refusal.py:164:87` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools._register_extra_tools`
- `tests/test_managed_discovery_refusal.py:192:90` **bad-argument-type** — Argument `_CachePort` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._build_role_registry`
- `tests/test_managed_edit_completeness.py:64:58` **bad-argument-type** — Argument `test_unconfirmed_eof_never_reaches_write.Port` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.edit_file.build_edit_file_tool`
- `tests/test_managed_mutation_metadata.py:63:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:100:45` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_mutation_metadata.py:128:55` **bad-argument-type** — Argument `_Port` is not assignable to parameter `workspace_io` with type `WorkspacePort` in function `fa.inner_loop.tools.mutation_guard.managed_version_dependencies`
- `tests/test_managed_project_tool_paths.py:31:77` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:40:81` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_search.build_fs_search_tool`
- `tests/test_managed_project_tool_paths.py:75:51` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_project_tool_paths.py:83:61` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.inner_loop.tools.fs_reach.build_fs_reach_tool`
- `tests/test_managed_registry_binding.py:383:62` **bad-argument-type** — Argument `(_entry: ChainEntry) -> test_missing_explicit_executor_fails_closed_through_production_chat_session.ScriptedProvider` is not assignable to parameter `provider_factory` with type `(ChainEntry) -> Provider` in function `fa.providers.chain.ProviderChain.__init__`
- `tests/test_managed_stage_lease.py:49:9` **missing-override-decorator** — Class member `_RecordingClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_managed_stage_lease.py:57:9` **missing-override-decorator** — Class member `_ReleaseRefusingClient.request` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_managed_subagent.py:200:17` **bad-argument-type** — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:201:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:203:20` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool`
- `tests/test_managed_subagent.py:233:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:234:53` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:253:60` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:275:32` **bad-assignment** — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile`
- `tests/test_managed_subagent.py:298:22` **bad-argument-type** — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:299:21` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:300:22` **bad-argument-type** — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:303:16` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool`
- `tests/test_managed_subagent.py:308:16` **bad-argument-type** — Argument `object` is not assignable to parameter `iterable` with type `Iterable[@_]` in function `set.__init__`
- `tests/test_managed_subagent.py:357:12` **unsupported-operation** — `None` is not subscriptable
- `tests/test_managed_subagent.py:358:57` **unsupported-operation** — `None` is not subscriptable
- `tests/test_plan_candidate_retention.py:95:13` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:96:13` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:139:9` **bad-argument-type** — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_plan_candidate_retention.py:140:9` **bad-argument-type** — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair`
- `tests/test_stage_checkpoints.py:153:9` **missing-override-decorator** — Class member `LyingStages.stop_view` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_stage_checkpoints.py:159:9` **missing-override-decorator** — Class member `LyingStages.publish` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_stage_checkpoints.py:213:9` **missing-override-decorator** — Class member `TruthyStop.stop_view` overrides a member in a parent class but is missing an `@override` decorator
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `artifact_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `kind` with type `CheckpointKind` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `operation_ids` with type `tuple[str, ...]` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `original_revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `plan_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `revision_id` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stage_checkpoints.py:341:30` **bad-argument-type** — Unpacked keyword argument `list[str] | Any` is not assignable to parameter `tree_sha256` with type `str` in function `fa.execution.checkpoints.CheckpointRecord.__init__`
- `tests/test_stats.py:158:29` **invalid-argument** — Expected a mapping, got object
- `tests/test_verify_gate_live.py:3282:78` **bad-argument-type** — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3339:45` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3346:48` **bad-argument-type** — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher`
- `tests/test_verify_gate_live.py:3366:78` **bad-argument-type** — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan`
- `tests/test_verify_gate_live.py:3537:24` **bad-argument-type** — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow`
- `tests/test_workspace_authorize.py:282:17` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:304:49` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:333:64` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_authorize.py:340:79` **missing-attribute** — Object of class `NoneType` has no attribute `to_dict`
- `tests/test_workspace_publication.py:848:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1250:52` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`
- `tests/test_workspace_publication.py:1277:68` **unsupported-operation** — `+` is not supported between `None` and `Literal[1]`

## HEAD-baseline Pyrefly diagnostic locations (21)

- `tests/test_execution_handoff.py`: 1
- `tests/test_execution_receipts.py`: 3
- `tests/test_stage_checkpoints.py`: 10
- `tests/test_workspace_authorize.py`: 4
- `tests/test_workspace_publication.py`: 3

The full baseline diagnostic records are in `/home/user/.cache/arena-gate-triage/pyrefly-head.json`. The 21 diagnostics are unchanged from the valid HEAD run; the 93 current-only records are listed above.
