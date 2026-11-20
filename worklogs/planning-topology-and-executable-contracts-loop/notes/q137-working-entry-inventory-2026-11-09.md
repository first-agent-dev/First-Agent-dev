# Q137 / checks — exact working inventory (2026-11-09)

**Status: OPEN / BLOCKING.** Latest immutable full `just test` before subsequent refactors: exit 1, 37 failed / 7252 passed / 18 skipped / 4 xfailed / 11 errors, coverage 86.52%; exact IDs and date are in “Full immutable test refresh”. It is not a result for the current source snapshot. Latest full Pyrefly previously reported 0 errors (168 suppressed / 72 warnings); full mypy previously reported 3 errors in 3 files. Neither full check was rerun after the latest refactors. Targeted history/tool-turn/scope/composer banks and mutations are recorded at the end; they do not close W0, W1 or live-host acceptance. Producer/consumer and LogKind checkers passed on the recent targeted snapshot. Original inventories below are historical; retain each finding until explicitly resolved.


## Exact pytest entries from activated snapshot (62)

- [ ] `tests/test_s10c_artifact_posture.py::test_s10c_no_artifact_is_group_or_world_accessible` — OPEN; individual resolution pending
- [ ] `tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[global_history.db]` — OPEN; individual resolution pending
- [ ] `tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[session-log/posture/events.jsonl]` — OPEN; individual resolution pending
- [ ] `tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[session-log/posture/llm_bodies.jsonl]` — OPEN; individual resolution pending
- [ ] `tests/test_s10c_artifact_posture.py::test_s10c_session_db_and_wal_sidecars_are_private` — OPEN; individual resolution pending
- [ ] `tests/test_s10c_artifact_posture.py::test_s10c_directories_are_0700` — OPEN; individual resolution pending
- [ ] `tests/test_s7_correlation.py::test_every_trace_row_carries_the_run_and_session_identity` — OPEN; individual resolution pending
- [ ] `tests/test_s7_correlation.py::test_event_ids_are_unique_and_ordered_within_the_run` — OPEN; individual resolution pending
- [ ] `tests/test_s7_correlation.py::test_logical_call_id_joins_the_trace_to_the_captured_body` — OPEN; individual resolution pending
- [ ] `tests/test_s7_correlation.py::test_one_provider_call_correlates_its_attempt_and_call_rows` — OPEN; individual resolution pending
- [ ] `tests/test_s7_correlation.py::test_documented_non_join_tool_call_id_is_empty_without_tool_calls` — OPEN; individual resolution pending
- [ ] `tests/test_iteration_cap.py::test_cmd_run_applies_config_per_role_limit_end_to_end` — OPEN; individual resolution pending
- [x] `tests/test_pyrefly_import_topology.py::test_pyrefly_check_passes` — fixed locally; see wide-slice verification
- [ ] `tests/test_readiness_announcement.py::test_drive_path_announces_ready_workspace` — OPEN; individual resolution pending
- [ ] `tests/test_readiness_announcement.py::test_drive_path_silent_without_venv` — OPEN; individual resolution pending
- [ ] `tests/test_s10a_cli_coverage.py::test_s10a_authoring_check_runs_on_a_real_workspace` — OPEN; individual resolution pending
- [ ] `tests/test_s10a_cli_coverage.py::test_s10a_run_proxy_mode_rewrites_the_chain` — OPEN; individual resolution pending
- [ ] `tests/test_s10a_cli_coverage.py::test_s10a_stats_renders_a_real_session` — OPEN; individual resolution pending
- [ ] `tests/test_s10a_cli_coverage.py::test_s10a_stats_aggregate_across_sessions` — OPEN; individual resolution pending
- [ ] `tests/test_s10a_cli_coverage.py::test_s10a_stats_console_render_and_dead_zones` — OPEN; individual resolution pending
- [ ] `tests/test_s10a_cli_coverage.py::test_s10a_stats_reports_source_errors_from_discovery` — OPEN; individual resolution pending
- [ ] `tests/test_s10a_cli_coverage.py::test_s10a_run_resume_reads_the_existing_draft` — OPEN; individual resolution pending
- [ ] `tests/test_s10a_cli_coverage.py::test_s10a_run_builds_compactor_chain_under_proxy` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_cli_parity.py::test_s10b_parity_happy_path` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_cli_parity.py::test_s10b_parity_quiet_mode_moves_status_off_stdout` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_cli_parity.py::test_s10b_parity_proxy_mode` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_cli_parity.py::test_s10b_parity_proxy_mode_builds_compactor_chain` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_cli_parity.py::test_s10b_parity_outcome_sink_suppresses_global_history_export` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_cli_parity.py::test_s10b_parity_without_sink_exports_global_history` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_cli_parity.py::test_s10b_stats_parity_dead_zones_report` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_cli_parity.py::test_s10b_stats_parity_single_session_json_shape` — OPEN; individual resolution pending
- [ ] `tests/test_s10b_complexity_ratchet.py::test_s13_11_c901_ratchet_tracks_retired_waiver` — OPEN; individual resolution pending
- [x] `tests/test_s10b_complexity_ratchet.py::test_s10b_c901_waiver_budget` — locally passes at 14/14; exact census and retired `_cmd_run` remain open
- [ ] `tests/test_s10b_complexity_ratchet.py::test_s10b_retired_waiver_stays_retired[_cmd_run]` — OPEN; individual resolution pending
- [x] `tests/test_s10c_artifact_posture.py::test_s10c_session_dir_is_private_at_creation_without_the_repair_pass` — fixed locally with managed fixture; see grouping report
- [x] `tests/test_s127_budget.py::test_s127_scatter_table_matches_registry` — targeted-fixed; absent from refreshed full failure list
- [x] `tests/test_s127_outline.py::test_s127_fold_cli_py_matches_ast_truth` — targeted-fixed; absent from refreshed full failure list
- [x] `tests/test_s13_10_tool_names.py::test_composition_root_rejects_non_portable_name` — targeted-fixed; absent from refreshed full failure list
- [x] `tests/test_s13_10_tool_names.py::test_composition_root_accepts_a_non_fs_pr_prefixed_name` — targeted-fixed; absent from refreshed full failure list
- [ ] `tests/test_s7_cli_run_paths.py::test_output_mode_never_suppresses_the_durable_trace[D-console]` — OPEN; individual resolution pending
- [ ] `tests/test_s7_cli_run_paths.py::test_output_mode_never_suppresses_the_durable_trace[D-quiet]` — OPEN; individual resolution pending
- [ ] `tests/test_s7_cli_run_paths.py::test_two_runs_in_one_process_do_not_leak_session_state` — OPEN; individual resolution pending
- [ ] `tests/test_s9_stats_projection.py::test_s9_authority_and_projection_agree` — OPEN; individual resolution pending
- [ ] `tests/test_s9_stats_projection.py::test_s9_discovery_rejects_manifest_pointing_elsewhere` — OPEN; individual resolution pending
- [ ] `tests/test_s9_stats_projection.py::test_s9_discovery_rejects_inactive_manifest` — OPEN; individual resolution pending
- [ ] `tests/test_s9_stats_projection.py::test_s9_run_id_reuse_is_refused_so_reexport_cannot_occur` — OPEN; individual resolution pending
- [ ] `tests/test_scope_hint_cache_key.py::test_live_hint_reaches_the_model` — OPEN; individual resolution pending
- [ ] `tests/test_scope_hint_cache_key.py::test_live_agents_map_is_identical_across_estimates` — OPEN; individual resolution pending
- [x] `tests/test_tool_schema_portability.py::test_every_current_role_tool_schema_satisfies_pts_v1` — targeted-fixed; absent from refreshed full failure list
- [ ] `tests/test_verify_gate_live.py::test_plan_preflight_real_cli_uses_selected_workspace_not_cwd[False]` — OPEN; individual resolution pending
- [ ] `tests/test_verify_gate_live.py::test_plan_preflight_real_cli_uses_selected_workspace_not_cwd[True]` — OPEN; individual resolution pending
- [x] `tests/test_verify_gate_live.py::test_plan_preflight_new_workspace_cannot_bypass_existing_owner` — fixed locally with managed fixture; see grouping report
- [x] `tests/test_verify_gate_live.py::test_plan_preflight_allocated_workspace_mismatch_blocks_provider` — fixed locally with managed fixture; see grouping report
- [x] `tests/test_verify_gate_live.py::test_ct91_public_q68_failed_prepare_invalidates_even_after_recovery[observe]` — targeted-fixed Q68; full rerun pending
- [x] `tests/test_verify_gate_live.py::test_ct91_public_q68_failed_prepare_invalidates_even_after_recovery[enforce]` — targeted-fixed Q68; full rerun pending
- [ ] `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[None]` — OPEN; individual resolution pending
- [ ] `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[coder]` — OPEN; individual resolution pending
- [ ] `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[planner]` — OPEN; individual resolution pending
- [ ] `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[planner,eval]` — OPEN; individual resolution pending
- [ ] `tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[eval]` — OPEN; individual resolution pending
- [ ] `tests/test_workflow_global_history.py::test_standalone_run_still_exports_its_own_row` — OPEN; individual resolution pending
- [ ] `tests/test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication` — OPEN; individual resolution pending

## Full Pyrefly diagnostics after local corrections (23; exit 1)

Each is OPEN; paths/lines are the current snapshot and can shift after edits.

- [x] `tests/test_execution_composition.py:229:33` — This expression is implicitly inferred to be `Any | None`. Please provide an explicit type annotation. [implicit-any-attribute] — fixed locally, see preliminary report
- [x] `tests/test_execution_composition.py:305:13` — Argument `SimpleNamespace` is not assignable to parameter `log` with type `EventLog` in function `fa.cli._run_cli_stage` [bad-argument-type] — fixed locally, see preliminary report
- [x] `tests/test_execution_composition.py:557:30` — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow` [bad-argument-type] — fixed locally, see preliminary report
- [x] `tests/test_execution_composition.py:2806:21` — Argument `SimpleNamespace` is not assignable to parameter `managed` with type `ManagedExecution | None` in function `fa.cli._drive_stage_with_managed_workspace` [bad-argument-type] — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:2966:9` — Argument `_ScriptedAuthority` is not assignable to parameter `client` with type `ExecutionClient` in function `fa.execution.composition.ManagedExecution.__init__` [bad-argument-type] — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:3051:34` — Argument `SimpleNamespace` is not assignable to parameter `args` with type `Namespace` in function `fa.cli._cmd_workflow` [bad-argument-type] — fixed locally, see preliminary report
- [x] `tests/test_managed_subagent.py:201:17` — Argument `_ParentWriter` is not assignable to parameter `managed` with type `ManagedExecution` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool` [bad-argument-type] — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:202:22` — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool` [bad-argument-type] — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:204:20` — Argument `SimpleNamespace` is not assignable to parameter `chat_chain` with type `ProviderChain | None` in function `fa.inner_loop.tools.managed_subagent.build_managed_subagent_tool` [bad-argument-type] — actual ProviderChain fixture; positive/negative/producer/EDGE verified
- [x] `tests/test_managed_subagent.py:277:32` — `SimpleNamespace` is not assignable to attribute `read_only_profile` with type `ExecutionProfile` [bad-assignment] — fixed locally using real profile/limits; R13 mutation checks passed
- [x] `tests/test_managed_subagent.py:300:22` — Argument `object` is not assignable to parameter `workspace_io` with type `WorkspacePort | None` in function `fa.cli._register_managed_subagent_tool` [bad-argument-type] — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:301:21` — Argument `SimpleNamespace` is not assignable to parameter `stage_lease` with type `_ManagedStageLease | None` in function `fa.cli._register_managed_subagent_tool` [bad-argument-type] — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:302:22` — Argument `_ParentState` is not assignable to parameter `parent_state` with type `SessionState` in function `fa.cli._register_managed_subagent_tool` [bad-argument-type] — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:305:16` — Argument `SimpleNamespace` is not assignable to parameter `limits` with type `RuntimeLimits` in function `fa.cli._register_managed_subagent_tool` [bad-argument-type] — fixed locally using real profile/limits; R13 mutation checks passed
- [x] `tests/test_plan_candidate_retention.py:95:13` — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair` [bad-argument-type] — resolved locally; focused Pyrefly and mypy 0
- [x] `tests/test_plan_candidate_retention.py:96:13` — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair` [bad-argument-type] — resolved locally; focused Pyrefly and mypy 0
- [x] `tests/test_plan_candidate_retention.py:139:9` — Argument `_Ctx` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._run_admission_repair` [bad-argument-type] — resolved locally; focused Pyrefly and mypy 0
- [x] `tests/test_plan_candidate_retention.py:140:9` — Argument `None` is not assignable to parameter `progress` with type `WorkflowProgress` in function `fa.inner_loop.workflow_controller._run_admission_repair` [bad-argument-type] — resolved locally; focused Pyrefly and mypy 0
- [x] `tests/test_verify_gate_live.py:3302:78` — Argument `test_ct94_real_session_edits_fresh_candidate_before_validated_publication.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan` [bad-argument-type] — fixed locally; focused Pyrefly 0
- [x] `tests/test_verify_gate_live.py:3359:45` — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher` [bad-argument-type] — fixed locally; focused Pyrefly 0
- [x] `tests/test_verify_gate_live.py:3366:48` — Argument `SimpleNamespace` is not assignable to parameter `ctx` with type `WorkflowContext` in function `fa.inner_loop.workflow_controller._require_managed_publisher` [bad-argument-type] — fixed locally; focused Pyrefly 0
- [x] `tests/test_verify_gate_live.py:3386:78` — Argument `test_ct94_promotion_port_receives_only_the_pinned_destination.RecordingPublisher` is not assignable to parameter `publisher` with type `CandidatePlanPublisher` in function `fa.inner_loop.workflow_controller._promote_validated_plan` [bad-argument-type] — fixed locally; focused Pyrefly 0
- [x] `tests/test_verify_gate_live.py:3557:24` — Argument `_CT91TestPlanPublisher` is not assignable to parameter `plan_publisher` with type `CandidatePlanPublisher | None` in function `fa.inner_loop.workflow_controller.run_workflow` [bad-argument-type] — fixed locally; focused Pyrefly 0

## Mypy diagnostics (117; 33 files, activated just _mypy exit 1)

Exact messages from the subsequent independent static run; OPEN, baseline-relative comparison not yet performed.

- [x] `scripts/check_execution_e2e_coverage.py:591: error: Incompatible types in assignment (expression has type "str", variable has type "Match[str] | None")  [assignment]` — typed local seam; full mypy and targeted bank verified
- [x] `scripts/check_execution_e2e_coverage.py:592: error: Value of type variable "AnyStr" of "escape" cannot be "Match[str] | None"  [type-var]` — typed local seam; full mypy and targeted bank verified
- [ ] `src/fa/inner_loop/managed_acquisition.py:265: error: Call to untyped function "dispose" in typed context  [no-untyped-call]`
- [x] `tests/test_execution_worker_reply_budget.py:283: error: Module "fa.execution.worker_client" does not explicitly export attribute "decode_cell_reply"  [attr-defined]` — transport test seam corrected; full mypy + mutation verified
- [x] `tests/test_execution_protocol.py:455: error: Unpacked dict entry 0 has incompatible type "object"; expected "SupportsKeysAndGetItem[str, list[str]]"  [dict-item]` — typed local seam; full mypy and targeted bank verified
- [x] `tests/test_execution_client.py:699: error: Function is missing a return type annotation  [no-untyped-def]` — fixed locally; see wide-slice verification
- [x] `tests/test_execution_cell_worker.py:157: error: Module "fa.execution.cell_worker" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed locally; focused mypy 0
- [x] `tests/test_execution_cell_worker.py:178: error: Module "fa.execution.cell_worker" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed locally; focused mypy 0
- [x] `tests/test_execution_cell_worker.py:198: error: Module "fa.execution.cell_worker" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed locally; focused mypy 0
- [ ] `tests/test_e2e_artifact_contract.py:18: error: Skipping analyzing "fastjsonschema": module is installed, but missing library stubs or py.typed marker  [import-untyped]`
- [x] `tests/test_e2e_artifact_contract.py:327: error: Returning Any from function declared to return "dict[str, Any]"  [no-any-return]` — fixed locally; see wide-slice verification
- [x] `tests/test_e2e_artifact_contract.py:331: error: Returning Any from function declared to return "dict[str, Any]"  [no-any-return]` — fixed locally; see wide-slice verification
- [x] `tests/test_e2e_artifact_contract.py:581: error: "append" of "list" does not return a value (it only ever returns None)  [func-returns-value]` — fixed locally; see wide-slice verification
- [x] `tests/test_execution_environment_artifact.py:52: error: Function is missing a return type annotation  [no-untyped-def]` — fixed locally; see wide-slice verification
- [x] `tests/test_execution_readers.py:37: error: Function is missing a return type annotation  [no-untyped-def]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:94: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:117: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:136: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:171: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:183: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:200: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:204: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:220: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:237: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:264: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:275: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:291: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:324: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:364: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:387: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:433: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:451: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:479: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:504: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:536: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:546: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:549: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:564: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:578: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:591: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_readers.py:615: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_project_request_json.py:67: error: Module "fa.execution.project_tools" does not explicitly export attribute "base64"  [attr-defined]` — transport test seam corrected; full mypy + mutation verified
- [x] `tests/test_execution_project_request_json.py:71: error: Returning Any from function declared to return "bytes"  [no-any-return]` — transport test seam corrected; full mypy + mutation verified
- [x] `tests/test_execution_project_request_json.py:73: error: Module "fa.execution.project_tools" does not explicitly export attribute "base64"  [attr-defined]` — transport test seam corrected; full mypy + mutation verified
- [x] `src/fa/inner_loop/tools/managed_subagent.py:128: error: Returning Any from function declared to return "str"  [no-any-return]` — fixed locally; see wide-slice verification
- [x] `tests/test_workspace_authorize.py:166: error: Argument "payload" to "_request" has incompatible type "object"; expected "dict[str, Any] | None"  [arg-type]` — fixed typed payload maps; full mypy verified
- [x] `tests/test_workspace_authorize.py:167: error: Argument "payload" to "_request" has incompatible type "object"; expected "dict[str, Any] | None"  [arg-type]` — fixed typed payload maps; full mypy verified
- [x] `tests/test_workspace_authorize.py:170: error: Argument "payload" to "_request" has incompatible type "object"; expected "dict[str, Any] | None"  [arg-type]` — fixed typed payload maps; full mypy verified
- [x] `tests/test_workspace_authorize.py:287: error: Argument "payload" to "_request" has incompatible type "object"; expected "dict[str, Any] | None"  [arg-type]` — fixed typed payload maps; full mypy verified
- [x] `tests/test_workspace_authorize.py:288: error: Argument "payload" to "_request" has incompatible type "object"; expected "dict[str, Any] | None"  [arg-type]` — fixed typed payload maps; full mypy verified
- [x] `tests/test_workspace_authorize.py:291: error: Argument "payload" to "_request" has incompatible type "object"; expected "dict[str, Any] | None"  [arg-type]` — fixed typed payload maps; full mypy verified
- [x] `tests/test_workspace_authorize.py:294: error: Argument "payload" to "_request" has incompatible type "object"; expected "dict[str, Any] | None"  [arg-type]` — fixed typed payload maps; full mypy verified
- [x] `tests/test_workspace_authorize.py:296: error: Argument "payload" to "_request" has incompatible type "object"; expected "dict[str, Any] | None"  [arg-type]` — fixed typed payload maps; full mypy verified
- [x] `tests/test_workspace_authorize.py:302: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_purposes.py:62: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_fs_search.py:1080: error: Module "fa.inner_loop.tools.fs_search" does not explicitly export attribute "RootedFileReader"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_fs_search.py:1241: error: Module "fa.memory.search_index" does not explicitly export attribute "sqlite3"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_fs_search.py:1264: error: Module "fa.memory.search_index" does not explicitly export attribute "sqlite3"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_fs_reach.py:565: error: Module "fa.memory.structural_index" does not explicitly export attribute "sqlite3"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_execution_project_tools.py:488: error: Returning Any from function declared to return "StructuralIndex"  [no-any-return]` — transport test seam corrected; full mypy + mutation verified
- [x] `tests/test_execution_project_tools.py:593: error: Module "fa.execution.project_tools" does not explicitly export attribute "build_fs_search_tool"  [attr-defined]` — transport test seam corrected; full mypy + mutation verified
- [x] `tests/test_coder_loop.py:311: error: Module "fa.inner_loop.loop" does not explicitly export attribute "ThreadPoolExecutor"  [attr-defined]` — direct owner import/unused ignore; full mypy and local bank verified
- [x] `tests/test_coder_loop.py:323: error: Module "fa.inner_loop.loop" does not explicitly export attribute "ThreadPoolExecutor"  [attr-defined]` — direct owner import/unused ignore; full mypy and local bank verified
- [x] `tests/test_plan_candidate_retention.py:95: error: Argument 1 to "_run_admission_repair" has incompatible type "_Ctx"; expected "WorkflowContext"  [arg-type]` — resolved locally; focused Pyrefly and mypy 0
- [x] `tests/test_plan_candidate_retention.py:96: error: Argument 2 to "_run_admission_repair" has incompatible type "None"; expected "WorkflowProgress"  [arg-type]` — resolved locally; focused Pyrefly and mypy 0
- [x] `tests/test_plan_candidate_retention.py:139: error: Argument 1 to "_run_admission_repair" has incompatible type "_Ctx"; expected "WorkflowContext"  [arg-type]` — resolved locally; focused Pyrefly and mypy 0
- [x] `tests/test_plan_candidate_retention.py:140: error: Argument 2 to "_run_admission_repair" has incompatible type "None"; expected "WorkflowProgress"  [arg-type]` — resolved locally; focused Pyrefly and mypy 0
- [x] `tests/test_workspace_publication.py:1367: error: Module "fa.execution.workspace" does not explicitly export attribute "os"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_workspace_publication.py:2027: error: Module "fa.execution.workspace" does not explicitly export attribute "os"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_workspace_publication.py:2158: error: Returning Any from function declared to return "Path"  [no-any-return]` — fixed locally; see wide-slice verification
- [ ] `tests/test_workspace_publication.py:2163: error: Skipping analyzing "fastjsonschema": module is installed, but missing library stubs or py.typed marker  [import-untyped]`
- [x] `tests/test_workspace_publication.py:2165: error: Module "fa.execution.protocol" does not explicitly export attribute "Operation"  [attr-defined]` — fixed locally; see wide-slice verification
- [x] `tests/test_workspace_publication.py:2235: error: Module "fa.execution.workspace" does not explicitly export attribute "_rename_directory"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_execution_termination.py:165: error: Returning Any from function declared to return "GrantReply"  [no-any-return]` — fixed locally; see wide-slice verification
- [x] `tests/test_execution_backend.py:479: error: Module "fa.execution.cell_worker" does not explicitly export attribute "subprocess"  [attr-defined]` — transport test seam corrected; full mypy + mutation verified
- [x] `tests/test_execution_backend.py:1072: error: Module "fa.execution.cell_worker" does not explicitly export attribute "subprocess"  [attr-defined]` — transport test seam corrected; full mypy + mutation verified
- [x] `tests/test_workspace_recovery.py:143: error: Module "fa.execution.workspace" does not explicitly export attribute "os"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_workspace_recovery.py:459: error: Module "fa.execution.workspace" does not explicitly export attribute "os"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_workspace_recovery.py:560: error: Module "fa.execution.workspace" does not explicitly export attribute "_rename_directory"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_execution_handoff.py:88: error: Call to untyped function "read_only_profile" in typed context  [no-untyped-call]` — fixed by typed shared profile factory; full mypy verified
- [x] `tests/test_execution_handoff.py:275: error: Module "fa.execution.workspace" does not explicitly export attribute "_replace_private_bytes"  [attr-defined]` — fixed direct imports; full mypy + mutation verified
- [x] `tests/test_execution_receipts.py:40: error: Module "tests.test_execution_backend" does not explicitly export attribute "claim"  [attr-defined]` — direct owner import/unused ignore; full mypy and local bank verified
- [x] `tests/test_verify_gate_live.py:3359: error: Argument 1 to "_require_managed_publisher" has incompatible type "SimpleNamespace"; expected "WorkflowContext"  [arg-type]` — fixed locally; focused Pyrefly 0
- [x] `tests/test_verify_gate_live.py:3366: error: Argument 1 to "_require_managed_publisher" has incompatible type "SimpleNamespace"; expected "WorkflowContext"  [arg-type]` — fixed locally; focused Pyrefly 0
- [x] `tests/test_managed_subagent.py:192: error: Function is missing a return type annotation  [no-untyped-def]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:201: error: Argument "managed" to "build_managed_subagent_tool" has incompatible type "_ParentWriter"; expected "ManagedExecution"  [arg-type]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:202: error: Argument "parent_state" to "build_managed_subagent_tool" has incompatible type "_ParentState"; expected "SessionState"  [arg-type]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:204: error: Argument "chat_chain" to "build_managed_subagent_tool" has incompatible type "SimpleNamespace"; expected "ProviderChain | None"  [arg-type]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:276: error: Incompatible types in assignment (expression has type "SimpleNamespace", variable has type "ExecutionProfile")  [assignment]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:299: error: Argument "workspace_io" to "_register_managed_subagent_tool" has incompatible type "object"; expected "WorkspacePort | None"  [arg-type]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:300: error: Argument "stage_lease" to "_register_managed_subagent_tool" has incompatible type "SimpleNamespace"; expected "_ManagedStageLease | None"  [arg-type]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:301: error: Argument "parent_state" to "_register_managed_subagent_tool" has incompatible type "_ParentState"; expected "SessionState"  [arg-type]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:304: error: Argument "limits" to "_register_managed_subagent_tool" has incompatible type "SimpleNamespace"; expected "RuntimeLimits"  [arg-type]` — fixed locally; see wide-slice verification
- [x] `tests/test_managed_subagent.py:314: error: No overload variant of "set" matches argument type "object"  [call-overload]` — fixed locally; see wide-slice verification
- [x] `tests/test_intent_guard_mode.py:64: error: Unused "type: ignore" comment  [unused-ignore]` — direct owner import/unused ignore; full mypy and local bank verified
- [x] `tests/test_execution_composition.py:38: error: Module "fa.execution.composition" does not explicitly export attribute "PlanPublication"  [attr-defined]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:305: error: Argument "log" to "_run_cli_stage" has incompatible type "SimpleNamespace"; expected "EventLog"  [arg-type]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:406: error: "RuntimeError" has no attribute "code"  [attr-defined]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:557: error: Argument 1 to "_cmd_workflow" has incompatible type "SimpleNamespace"; expected "Namespace"  [arg-type]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:945: error: Module "fa.cli" does not explicitly export attribute "managed_execution_for_run"  [attr-defined]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:2475: error: Unused "type: ignore" comment  [unused-ignore]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:2615: error: Module "fa.cli" does not explicitly export attribute "managed_execution_for_run"  [attr-defined]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:2806: error: Argument "managed" to "_drive_stage_with_managed_workspace" has incompatible type "SimpleNamespace"; expected "ManagedExecution | None"  [arg-type]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:2966: error: Argument 1 to "ManagedExecution" has incompatible type "_ScriptedAuthority"; expected "ExecutionClient"  [arg-type]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:3051: error: Argument 1 to "_cmd_workflow" has incompatible type "SimpleNamespace"; expected "Namespace"  [arg-type]` — local lifecycle/typing seam verified, see preliminary report
- [x] `tests/test_execution_composition.py:3424: error: Module "fa.inner_loop.tools.run_bash" does not explicitly export attribute "ToolResult"  [attr-defined]` — fixed direct import; full mypy + mutation verified
- [x] `tests/test_execution_composition.py:3431: error: Module "fa.inner_loop.tools.run_bash" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed direct import; full mypy + mutation verified
- [x] `tests/test_prompt_registry_coherence.py:249: error: Unused "type: ignore" comment  [unused-ignore]` — direct owner import/unused ignore; full mypy and local bank verified
- [x] `tests/test_prompt_registry_coherence.py:338: error: Unused "type: ignore" comment  [unused-ignore]` — direct owner import/unused ignore; full mypy and local bank verified
- [x] `tests/test_managed_registry_binding.py:35: error: Module "fa.inner_loop.tools.run_bash" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed direct import; full mypy + mutation verified
- [x] `tests/test_managed_registry_binding.py:143: error: Module "fa.inner_loop.tools.run_bash" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed direct import; full mypy + mutation verified
- [x] `tests/test_managed_registry_binding.py:238: error: Module "fa.workspace.worktree_manager" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed direct import; full mypy + mutation verified
- [x] `tests/test_managed_registry_binding.py:276: error: Module "fa.inner_loop.tools.run_bash" does not explicitly export attribute "ToolResult"  [attr-defined]` — fixed direct import; full mypy + mutation verified
- [x] `tests/test_managed_registry_binding.py:302: error: Module "fa.inner_loop.tools.run_bash" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed direct import; full mypy + mutation verified
- [x] `tests/test_managed_bash_tool.py:42: error: Module "fa.inner_loop.tools.run_bash" does not explicitly export attribute "subprocess"  [attr-defined]` — fixed direct import; full mypy + mutation verified
- [x] `tests/test_execution_handoff_return.py:15: error: Module "tests.test_execution_client_port" does not explicitly export attribute "PLAN_RELATIVE"  [attr-defined]` — direct owner import/unused ignore; full mypy and local bank verified
- [x] `tests/test_execution_client_stage.py:45: error: Module "tests.test_execution_client_port" does not explicitly export attribute "PLAN_RELATIVE"  [attr-defined]` — direct owner import/unused ignore; full mypy and local bank verified

## Other gate entries

- [x] `_lock-check`, `_contracts`, `_shell-syntax`, `_deadcode`: exit 0 in independent activated run.
- [ ] `_lint`: Ruff and format pass after AST-verified documentation formatting; deptry passes; pylint exit 8, 2 duplicate-code and 15 cyclic-import diagnostics remain to triage (see preliminary report). Full lint not rerun.
- [ ] `_authoring`: original eight HARD-BLOCK diagnostics below; subsequent local fixes reduce the current authoring output to one (`IsolatedWorktreeManager`). No rule disabled or severity changed.

- [x] `FA-AUTHORING-V2-EXPORTS-COMPLETENESS` `src/fa/inner_loop/tools/workflow_tool.py:88` — public symbol 'ParentStageLease' is defined but not in __all__ — locally resolved; see preliminary report
- [x] `FA-AUTHORING-V2-EXPORTS-COMPLETENESS` `src/fa/inner_loop/tools/workspace_port.py:63` — public symbol 'PROJECT_ARTIFACT_KINDS' is defined but not in __all__ — locally resolved; see preliminary report
- [x] `FA-AUTHORING-V2-EXPORTS-COMPLETENESS` `src/fa/inner_loop/tools/workspace_port.py:64` — public symbol 'PROJECT_ENTRY_KINDS' is defined but not in __all__ — locally resolved; see preliminary report
- [ ] `FA-AUTHORING-V2-EXPORTS-COMPLETENESS` `src/fa/workspace/worktree_manager.py:145` — public symbol 'IsolatedWorktreeManager' is defined but not in __all__
- [x] `FA-AUTHORING-V4-PYTEST-SKIP` `tests/test_managed_discovery_budget.py:125` — pytest.skip(...) call hides a test from the suite; fix the test or delete it — locally resolved; see preliminary report
- [x] `FA-AUTHORING-V4-PYTEST-SKIP` `tests/test_safe_walk.py:239` — pytest.skip(...) call hides a test from the suite; fix the test or delete it — locally resolved; see preliminary report
- [x] `FA-AUTHORING-V4-PYTEST-SKIP` `tests/test_safe_walk.py:305` — pytest.skip(...) call hides a test from the suite; fix the test or delete it — locally resolved; see preliminary report
- [x] `FA-AUTHORING-V4-PYTEST-SKIP` `tests/test_structural_index.py:189` — pytest.skip(...) call hides a test from the suite; fix the test or delete it — locally resolved; see preliminary report

## Separate review findings

- [x] P1 PROJECT_TOOL nested JSON overflow: bounded explicit refusal implemented and tested locally on both worker routes; 61,440-byte result cap and 65,536-byte frame cap unchanged; live-host acceptance remains open.
- [x] P2 worker partial-gate deadline leak: corrected and tested locally; no live-host claim.
- [x] P2 Q98 stats run-cap failure misreported: corrected and tested locally.
- [ ] P2 YAML parser quoted # / block handling.
- [ ] P2 discovery wide-directory fd exhaustion, conditional on host fd limits.
- [ ] P2 managed mutation foreign board: production binding route not proved.
- [ ] P2 managed planner host-tree-dependent path check: live-host reachability not proved.
- [ ] Legacy eval behavior change: contract reconciliation still needed.
- [ ] File review register remains 109 D / 31 P / 32 unchecked of 172; D is primary diff read, not adversarial signoff.
- [x] Live-host ledger append is planned in `i03-live-e2e-test-plan-2026-10-22.md` §4.1 L-RCPT-2/L-RCPT-6 and §4.2 L-ENTRY-4 (proposal): exact durable snapshots, negative controls, required deployment/evidence boundaries; not executed.
- [ ] Live-host acceptance, Q135 F2–F4 and W3–W4 remain open; plan is not a result.

See `adversarial-diff-review-preliminary-2026-11-09.md` for actual commands, mutation evidence, and limitations.

## Gate refresh 2026-11-09

Activated `just test` exit 1: 46 failed, 7218 passed, 18 skipped, 4 xfailed, 11 errors, coverage 86.17%. No new failure IDs vs initial snapshot. Full mypy before latest test-seam repair: 118 errors/33 files versus base 33/8 with the same tool and `--no-incremental`; normalization gives 92 added/7 removed occurrences. Four test-cell-worker attr errors fixed locally; full mypy rerun 114 errors/32 files, before CT94 repairs. Full lint reaches pylint but fails (see detailed note). Live-host remains NOT RUN.

### C901 >20 inventory and R13 CLI child-provider seam (2026-11-09)

After environment rebuild (`scripts/arena-env-build.sh`, exit 0), repository-wide `ruff check . --select C901 --ignore-noqa --output-format json` identified eight functions above 20: `_cmd_run` 24; `_drive_session_inner` 125; `_execute_batch_parallel` 32; `SessionState.__post_init__` 33; `build_managed_subagent_tool` 31 and nested `handler` 27; `_parse_events` 45; `render_session` 39. Each requires responsibility/risk review, not automatic splitting.

R13/ADR-12: `_build_managed_child_chain` now owns chat-provider selection; chat parent reuses its chain, planner/coder select the configured chat chain, proxy or construction failures disable the child without parent fallback. No provider/readiness ordering change; `_cmd_run` complexity 24→18, still above configured 15 and its existing waiver remains. No ratchet claimed fixed. Seven entries remain above 20.

Final `pytest -q tests/test_managed_subagent.py tests/test_execution_composition.py tests/test_cli.py::test_managed_child_chain_selects_only_chat_and_fails_closed tests/test_cli.py::test_readiness_completes_before_provider_build_or_call --disable-warnings`: exit 0, 81 passed/1 existing xfailed. New C0 matrix covers chat reuse, planner/coder chat, eval, missing chat, proxy error and build exception. Existing local-backend C1/C2 managed-child tests exercise the caller; not live-host acceptance. Replacing the caller with `None`: exit 1, 12 composition failures (producer killed); replacing proxy-error refusal with parent fallback: exit 1 in new test (EDGE killed). Source restored SHA256 `f145742dac8ecf76e618c00d1daaeb5760132ef641ac4cbf7dadeff7a1ef5a61`. Focused Ruff, format, Pyrefly, mypy, `git diff --check`: exit 0. Larger bank including legacy real-CLI parity/history: exit 1, 116 passed/1 xfailed/9 failed, all shown failures report managed provisioning unavailable; not treated as new or silently fixed. Q137 strict gate and live-host ledger append remain open.

### Parallel-batch responsibility seam — FIND-012 / S6-F4 / I-63 (2026-11-09)

Separated pool dispatch and failure settlement from lifecycle/order orchestration in `loop.py`; no C901 waiver added, `_execute_batch_parallel` waiver removed. Exactly-once pre-submit marking, no replay of attempted submission, retryability distinction, context propagation, result order and AFTER stop semantics are unchanged. Extended C1 `test_drive_session_settles_parallel_batch_without_replaying_effects` for lost first Future and unsubmitted second call. This tests local thread pool behavior, not host acceptance; executor timeout still cannot force-cancel a running thread.

Bank `pytest -q tests/test_coder_loop.py tests/test_inner_loop_runtime.py tests/test_parallel_context.py tests/test_s6_stop_paths.py tests/test_tool_batching.py tests/test_inner_loop_registry.py --disable-warnings`: exit 0, 63 passed. Ruff, format, focused Pyrefly and mypy, `git diff --check`: exit 0. Removing caller `_dispatch_parallel_batch`: 4 C1 failures (exit 1); removing failure-settlement call: 4 failures (exit 1); changing unknown outcome to retryable: 2 failures (exit 1). Restored focused 16 passed, SHA256 `1d004f00659316f1da1f68bf91ac3961a60331e5a00d57ed2e755941f6b1c2a5`. Repository-wide C901 >20 now six entries: coder loop 125; state init 33; managed subagent factory/handler 31/27; stats parse/render 45/39. Ratchet remains exit 1, 6 passed/2 failed (exact census and `_cmd_run` retirement), not a full gate.

### Session stats rendering seam — S9 / S19 / I-41 (2026-11-09)

Grouped report output into private activity, provider/guard, failure, and pressure/scope renderers; `render_session` retains stream resolution, header, ordering, efficiency and flush. Removed its C901 waiver; no parsing, JSON, discovery, or policy change. Flattening the new renderer groups into the public function gives the same statement AST as the `HEAD` original (comparison printed True; this renderer had no prior in-worktree statement changes). C0 tests cover all sections, missing sections, order, output truncation, error branches, explicit stream and flush. The existing C2/C3 SQLite-authority CLI test now also checks text through a real `compaction_warning` event and the legacy-source refusal.

`pytest -q tests/test_stats.py tests/test_s19_stats_parsers.py tests/test_observability_fix_p5.py tests/test_coverage_failure_paths.py tests/test_cli.py::test_fa_stats_reads_current_session_db_and_rejects_legacy_without_writes --disable-warnings`: exit 0, 51 passed. Deleting pressure/scope caller caused the SQLite CLI test to fail (producer, exit 1); increasing file display limit to 11 failed C0 (EDGE, exit 1). After restore 51 passed; after docstring-only clarification focused 2 passed. Ruff/format/Pyrefly/mypy and `git diff --check` exit 0; initial Pyrefly flagged missing `@override` on test stream and passed after correction. Final stats SHA256 `122abb8ce4d35cff6d2ffed7fb80571994c6595be3a3f43fe7dedef5d2d72e1c`. Five functions remain above 20: coder loop 125; state init 33; managed subagent factory/handler 31/27; stats parser 45. This is not full-gate or live-host acceptance.

### SessionState initialization seams — R13 / Q126 / S5 / V19 (2026-11-09)

Separated authority, flags/transaction, optional stores and workspace runtime initialization into ordered private methods; managed-child validation remains ahead of all four, no fallback or injected dependency behavior changed. Removed `__post_init__` C901 waiver. Added C3: passing a real host ArtifactStore to a managed child is rejected before default authority root is requested or created. Existing R13 child producer verifies no host stores/PTY/worktree, S5 authority mismatch rejects, and Q126 isolated mode logs refusal without host Git.

Bank `pytest -q tests/test_managed_subagent.py tests/test_session_db_authority.py tests/test_s5_isolation_boundary.py tests/test_managed_registry_binding.py tests/test_execution_composition.py --disable-warnings`: exit 0, 126 passed/2 existing xfailed, including Q19 known host-Bash isolation gap (not resolved by this slice). Adjacent runtime/blackboard bank: exit 0, 38 passed. Focused Ruff/format/Pyrefly/mypy and diff-check exit 0. Removing authority seam and runtime seam killed individually by authority mismatch and Q126 producer tests; removing pre-authority child guard and allowing child artifact store killed by C3 and managed-child C1 respectively (all exit 1). Restored bank 126 passed/2 xfailed; state SHA256 `97c5306fc43fa891d4370d8e1992787af8a772e16bd1cb90a4acba69a1289fe4`.

C901 census now 11, below current floor 12: ratchet exit 1, 5 passed/3 failed (exact census, outdated liveness floor/budget, and `_cmd_run` retirement). Floor/budget and exact census must be deliberately lowered together in a subsequent test-contract slice; the ceiling must not rise. Four functions remain >20: coder loop 125, managed child factory/handler 31/27, stats parser 45. Strict gate remains blocking.

### S10b ratchet alignment after verified retirements (2026-11-09)

Actual 11 waivers, exact census 12 and liveness floor 12 were stale. Lowered floor 12→11 and budget 14→13 (maintains two-point headroom; no ceiling change), and pinned exact census 11. Added explicit no-waiver plus real Ruff complexity checks for the three just-retired non-CLI functions. Ratchet full: exit 1, 10 passed/1 failed (`_cmd_run` remains a real retired-waiver regression); excluding that node: exit 0, 10 passed/1 deselected. Ruff/format/Pyrefly/mypy/diff-check exit 0. A test-file mutant returning an empty census fails the budget/liveness test (producer, exit 1); an isolated copied `stats.py` with restored waiver fails the new retired-function check (EDGE, exit 1). The test's final source was type-cleaned after mutations without changing their tested conditions; final SHA256 `5beb4f13b6903b6f0262028911e9b1ad629a51fb909d2ddd4f4b5cdaa2a44262`. No gate signoff.

### CLI terminal completion seam / retired `_cmd_run` (2026-11-09)

LOGIC-11/S8/I-38: moved existing standalone projection vs workflow sink and terminal status rendering into `_finish_cli_run`; missing outcomes still return before this seam. No release, quiet-mode, best-effort projection or managed-boundary behavior changed. `_cmd_run` now passes Ruff C901 <=15 without waiver. C2 through real `_cmd_run`, real session DB and global history with existing local managed-stage test boundary and scripted external provider verifies standalone row, workflow sink/no stage row, export failure, and quiet stream/payload. This is not live supervisor acceptance.

`pytest -q tests/test_s10b_complexity_ratchet.py tests/test_cli.py::test_managed_cli_completion_projects_only_standalone_and_preserves_outcome tests/test_cli.py::test_readiness_completes_before_provider_build_or_call tests/test_managed_subagent.py tests/test_execution_composition.py --disable-warnings`: exit 0, 95 passed/1 existing xfailed, also after mutants. Full complexity ratchet included and now passes 11 tests; budget 13→12, floor 11→10, exact census 10, ceiling remains 15. Removing completion seam killed all 3 C2 cases (exit 1); forcing workflow projection killed workflow C2 (exit 1). Focused Ruff/format/Pyrefly/mypy/diff-check exit 0. Restored CLI SHA256 `5040e00232fdc875a53d84f8b340f4ae4399f3c859db79d1b842035acf5fcfeb`. Separate workflow history bank still exit 1, 4 passed/1 failed: legacy standalone fixture lacks configured managed provisioner; tracked and not represented as fixed. Four functions still exceed 20. Strict full gate and live host ledger acceptance remain open.

### R13 child admission seam (2026-11-09)

Extracted typed `_admit_managed_child` from the handler; it preserves check order and error results before reservation/PIN, including UTF-8 bytes, flags, chat chain, noninteractive READ profile and parent DB. PIN → drive → STOP/terminality remains a single visibly owned lifecycle. Handler 27→19, enclosing factory 31→23; both waivers remain load-bearing against threshold 15 and are not claimed retired. Repository-wide >20 entries now three: coder loop 125, R13 factory 23, stats parser 45. Added C1/C3 invalid-task matrix (including surrogate and multibyte overflow) and positive exact 16,000-byte boundary followed by supervisor denial; tests assert no PIN/reservation for invalid tasks, no STOP on denied PIN, and slot release.

`pytest -q tests/test_managed_subagent.py tests/test_execution_composition.py --disable-warnings`: exit 0, 86 passed/1 existing xfailed (also after mutations). Ruff/format/focused Pyrefly/mypy/diff-check exit 0; full complexity ratchet 11 passed. Ignoring admission failure killed flag/profile and provider tests (2 failed, exit 1); counting Unicode characters instead of encoded bytes killed overflow case (1 failed, exit 1). Source restored SHA256 `78b4a3336d08554576b539065e851fc79a825512234c85e6aeed4cb7369debac`. This is local composition proof, not live-host acceptance.

### Full immutable test refresh after C901 slices (2026-11-09)

`source .venv/bin/activate && just test`: exit 1, 37 failed/7252 passed/18 skipped/4 xfailed/11 errors, 2 warnings, coverage 86.52%, 917.92s. No source edits occurred during run. Current strict gate remains BLOCKING. Full output was `/tmp/q137-after-c901-just-test.log` (ephemeral); actual failure/error identifiers below; do not infer cause from summary without inspecting each trace. Live-host E2E remains open.

```text
ERROR tests/test_s10c_artifact_posture.py::test_s10c_no_artifact_is_group_or_world_accessible
ERROR tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[global_history.db]
ERROR tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[session-log/posture/events.jsonl]
ERROR tests/test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600[session-log/posture/llm_bodies.jsonl]
ERROR tests/test_s10c_artifact_posture.py::test_s10c_session_db_and_wal_sidecars_are_private
ERROR tests/test_s10c_artifact_posture.py::test_s10c_directories_are_0700 - A...
ERROR tests/test_s7_correlation.py::test_every_trace_row_carries_the_run_and_session_identity
ERROR tests/test_s7_correlation.py::test_event_ids_are_unique_and_ordered_within_the_run
ERROR tests/test_s7_correlation.py::test_logical_call_id_joins_the_trace_to_the_captured_body
ERROR tests/test_s7_correlation.py::test_one_provider_call_correlates_its_attempt_and_call_rows
ERROR tests/test_s7_correlation.py::test_documented_non_join_tool_call_id_is_empty_without_tool_calls
FAILED tests/test_iteration_cap.py::test_cmd_run_applies_config_per_role_limit_end_to_end
FAILED tests/test_readiness_announcement.py::test_drive_path_announces_ready_workspace
FAILED tests/test_readiness_announcement.py::test_drive_path_silent_without_venv
FAILED tests/test_s10a_cli_coverage.py::test_s10a_authoring_check_runs_on_a_real_workspace
FAILED tests/test_s10a_cli_coverage.py::test_s10a_run_proxy_mode_rewrites_the_chain
FAILED tests/test_s10a_cli_coverage.py::test_s10a_stats_renders_a_real_session
FAILED tests/test_s10a_cli_coverage.py::test_s10a_stats_aggregate_across_sessions
FAILED tests/test_s10a_cli_coverage.py::test_s10a_stats_console_render_and_dead_zones
FAILED tests/test_s10a_cli_coverage.py::test_s10a_stats_reports_source_errors_from_discovery
FAILED tests/test_s10a_cli_coverage.py::test_s10a_run_resume_reads_the_existing_draft
FAILED tests/test_s10a_cli_coverage.py::test_s10a_run_builds_compactor_chain_under_proxy
FAILED tests/test_s10b_cli_parity.py::test_s10b_parity_happy_path - assert 2 ...
FAILED tests/test_s10b_cli_parity.py::test_s10b_parity_quiet_mode_moves_status_off_stdout
FAILED tests/test_s10b_cli_parity.py::test_s10b_parity_proxy_mode - assert 2 ...
FAILED tests/test_s10b_cli_parity.py::test_s10b_parity_proxy_mode_builds_compactor_chain
FAILED tests/test_s10b_cli_parity.py::test_s10b_parity_outcome_sink_suppresses_global_history_export
FAILED tests/test_s10b_cli_parity.py::test_s10b_parity_without_sink_exports_global_history
FAILED tests/test_s10b_cli_parity.py::test_s10b_stats_parity_dead_zones_report
FAILED tests/test_s10b_cli_parity.py::test_s10b_stats_parity_single_session_json_shape
FAILED tests/test_s7_cli_run_paths.py::test_output_mode_never_suppresses_the_durable_trace[D-console]
FAILED tests/test_s7_cli_run_paths.py::test_output_mode_never_suppresses_the_durable_trace[D-quiet]
FAILED tests/test_s7_cli_run_paths.py::test_two_runs_in_one_process_do_not_leak_session_state
FAILED tests/test_s9_stats_projection.py::test_s9_authority_and_projection_agree
FAILED tests/test_s9_stats_projection.py::test_s9_discovery_rejects_manifest_pointing_elsewhere
FAILED tests/test_s9_stats_projection.py::test_s9_discovery_rejects_inactive_manifest
FAILED tests/test_s9_stats_projection.py::test_s9_run_id_reuse_is_refused_so_reexport_cannot_occur
FAILED tests/test_scope_hint_cache_key.py::test_live_hint_reaches_the_model
FAILED tests/test_scope_hint_cache_key.py::test_live_agents_map_is_identical_across_estimates
FAILED tests/test_verify_gate_live.py::test_plan_preflight_real_cli_uses_selected_workspace_not_cwd[False]
FAILED tests/test_verify_gate_live.py::test_plan_preflight_real_cli_uses_selected_workspace_not_cwd[True]
FAILED tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[None]
FAILED tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[coder]
FAILED tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[planner]
FAILED tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[planner,eval]
FAILED tests/test_verify_gate_live.py::test_acquisition_unavailable_live_chat_and_noncoder_child_binding[eval]
FAILED tests/test_workflow_global_history.py::test_standalone_run_still_exports_its_own_row
FAILED tests/test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication
```

### I-52 / S13.2 — authoritative conversation restoration seam

Extracted `_restore_conversation_history` from `_drive_session_inner`; chronological replay remains after last stage-3 compaction and before appending the current task, with original draft+summary merge and stdout/summary selection. Existing best-effort warning/partial fallback on read/reconstruction exception was preserved, not asserted to be fail-closed. New C1 uses real EventLog/SQLite and provider double to verify two compaction boundaries, task, ordered tool pair and stdout; C0 checks read error keeps the supplied draft and logs warning; existing C1 dangling-tool refusal proves provider not reached. This is not live-host E2E.

`pytest -q tests/test_coder_loop.py tests/test_s13_replay.py tests/test_pr2_wiring.py tests/test_pr5_wiring.py tests/test_s13_ordering_fix.py tests/test_s13_strict_transport.py tests/test_s6_stop_paths.py tests/test_iteration_cap.py -k 'not test_cmd_run_applies_config_per_role_limit_end_to_end' --disable-warnings`: exit 0, 81 passed/1 deselected (known CLI managed provisioning case). Focused restored bank exit 0, 32 passed. Ruff, format, Pyrefly, focused mypy, diff-check exit 0. Replacing driver restoration call with empty history killed two C1 tests; using first instead of last compaction killed new C1 test (both mutant runs exit 1). Restored source SHA256 `454b2b260b5f1c3535a41c0f99035c5b3350b02250a040dfea17b844ac5e7943`. Ruff `--ignore-noqa` exit 1 as expected: `_drive_session_inner` 125→115, still waived; no claim of complete audit or full gate.

### ADR-7 §10 / S6-F4 — synthetic tool-result padding seam

Extracted `_pad_unexecuted_tool_results` while preserving current-turn stop attribution, original `SessionRun.stop`, retryability, ordered producer-side call/result events and no writes for an already complete batch. C1 asserts provider messages and actual authority IDs/error fields; C0 asserts stale stop ignored, stop identity preserved, and no extra rows for completed batch. Existing S6 and iteration-cap tests cover in-band stop decisions and continuation. No claim of live-host ledger append acceptance.

Main bank: `pytest -q tests/test_coder_loop.py tests/test_s6_stop_paths.py tests/test_iteration_cap.py tests/test_inner_loop_runtime.py tests/test_inner_loop_loop_guard.py tests/test_s13_replay.py -k 'not test_cmd_run_applies_config_per_role_limit_end_to_end' --disable-warnings` exit 0, 77 passed/1 deselected. Restored focused bank exit 0, 21 passed/1 deselected. Ruff, format, focused Pyrefly/mypy and `git diff --check` exit 0. Initial targeted runs exit 1 due to missing test-only ToolCall import and then an over-strict expectation that ignored existing telemetry event; corrected oracle to select the actual paired event kinds. Removing padding call killed C1; dropping StopInfo and reading stale rows each killed targeted C0 (all mutant runs exit 1). Restored source SHA256 `0e6a6e21e56981f372cc98709999814e28b3abf9c3524f5ae3255980f7a01719`. Ruff `--ignore-noqa`: driver 115→109, waiver remains; this is not a complete audit.

### ADR-9 / S22 — per-turn provider cooldown retry seam

Extracted `_request_with_cooldown_retries` with the original per-turn limit, same request, ordering of provider_attempt rows / retry output / sleep, pytest-only sleep shim, and outward exception propagation unchanged. Session-level retry and termination remain in driver. New C1 uses real ProviderChain and EventLog, fake external provider and controlled clock to prove 503→300s cooldown→same request→200, correlated rows, retry display and one summary; exhaustion C1 now counts three same-identity requests. Not a live-host timing test. Existing terminal-exhaustion behavior writes the final exhaustion attempts both in the inner and outer handlers when nonempty; this seam extraction intentionally did not change it and it merits separate event-contract analysis before any behavior change.

`pytest -q tests/test_coder_loop.py tests/test_s22_max_chain_retries.py tests/test_providers_chain.py tests/test_s13_replay.py tests/test_s6_stop_paths.py --disable-warnings`: exit 0, 100 passed, repeated after mutations. Ruff/format/Pyrefly/focused mypy/diff-check exit 0; full C901 ratchet 11 passed. Initial Ruff check reported unsorted new import (I001), fixed before final checks. Bypassing retry seam killed the C1 recovery test; lowering retry count to 2 killed the C1 exhaustion test (both mutant exit 1). Restored source SHA256 `826699aa881e6c50527382e56a781bad4815434e0796f56a3079664e189fa5e5`. Ruff `--ignore-noqa` exit 1: driver 109→101, still waived. Strict full gate and live-host acceptance remain open.

### ADR-9 — duplicate exhausted provider attempts

Fixed duplicate `provider_attempt` rows on the last exhausted per-turn call: retry seam already records every returned attempt, so the outer handler no longer records the same attempt a second time. The real `fa.stats` consumer counts these rows, so duplication inflated provider error counts. New C1 exercises real ProviderChain, EventLog and stats with three actual transient failures and controlled external clock: exactly three provider_attempt rows / stats total 3, three logical IDs and one existing `run_stopped` outcome. Red test before fix was 4 rows vs 3. An initial post-fix assertion erroneously expected an `llm_chain_exhausted` event; source inspection confirmed runtime currently emits `run_stopped` instead, so assertion was corrected without inventing a producer. ADR-9 §4 Tier-2 `llm_chain_exhausted` appears unimplemented in src/fa and is a separate unresolved observability contract issue, not fixed or waived by this slice.

Bank `pytest -q tests/test_coder_loop.py tests/test_s22_max_chain_retries.py tests/test_providers_chain.py tests/test_stats.py tests/test_s19_stats_parsers.py tests/test_s6_stop_paths.py --disable-warnings`: exit 0, 128 passed. Ruff/format/Pyrefly/focused mypy/diff-check exit 0. Removing inner attempt producer and restoring outer duplicate each killed new C1 (exit 1). Restored focused tests exit 0, 3 passed; source SHA256 `66a60fa0827f611beaf17c1b6cd4c124241db3ac994d627bef2404f7d27da899`. Live-host evidence not claimed.

### S6-F4 / S12.7 CT1 / S14b.2 CT2 — terminal tool-stop responsibility

Extracted `_handle_terminal_tool_stop`: AFTER_TOOL_EXEC and BETWEEN_ROUNDS LoopGuard prefix remain terminal, emit identical hook_deny and append observation before breaking; ordinary BETWEEN_ROUNDS and iteration-cap continue to existing padding. No stop semantics or EventBus placement changed. C0 matrix covers terminal/continuation cases, no effects for non-terminal, None; C1 exercises real guard/driver call counts, observations, LoopGuard trip and cap continuation. This is not C2/C3 or live-host proof.

`pytest -q tests/test_coder_loop.py tests/test_s6_stop_paths.py tests/test_s127_guard.py tests/test_iteration_cap.py tests/test_observability_fix_p1.py tests/test_inner_loop_loop_guard.py tests/test_inner_loop_runtime.py tests/test_s13_replay.py -k 'not test_cmd_run_applies_config_per_role_limit_end_to_end' --disable-warnings`: exit 0, 99 passed/1 deselected. Restored focused bank 38 passed/1 deselected, exit 0. Ruff/format/focused Pyrefly/mypy/diff-check exit 0. Caller bypass mutant killed by AFTER_TOOL_EXEC C1; widened BETWEEN_ROUNDS terminal mutant killed by continuation C1 (exit 1 each). Restored SHA256 `d13afd84f3afbbde806aa059a5975fbd163c5ede24a74b713deadc2cca42fb18`. Ruff `--ignore-noqa` exit 1: driver 100→97, existing waiver retained; no complete audit or gate claim.

### ADR-9 / S17 LOGIC-10 / Q98 — no-tool response completion seam (P5 narrowed)

Architecture proposals audited in `coder-loop-architecture-map-2026-11-09.md` §16. Extracted `_finish_no_tool_response` to own no-tool clean/abnormal outcome and abnormal warning/stop event, called after existing model_msg and before existing `finish`; no new type, result/finish codes/text, collected results, sink order and exception handling preserved. C1 matrix covers stop/end_turn/empty/length/content_filter/unexpected, EventLog authority, output and summary; two-turn case checks real tool execution before later abnormal response and preserved results. No new security/C2/live-host acceptance claimed.

Environment `scripts/arena-env-build.sh` exit 0, CPython 3.13.16. Initial targeted command exit 4 because of a guessed nonexistent AFTER hook test name; no tests ran. Corrected targeted bank exit 0, 11 passed. `pytest -q tests/test_coder_loop.py tests/test_s13_replay.py tests/test_s13_error_surfacing.py tests/test_s6_stop_paths.py tests/test_compaction_c1_wiring.py tests/test_s14_compaction_ssot.py tests/test_s9_guardrail_metrics.py tests/test_s23_circuit_breaker_loop_warn.py tests/test_observability_fix_p4.py --disable-warnings` exit 0, 89 passed, repeated after mutations. Ruff/format/Pyrefly/focused mypy/diff-check exit 0; ratchet 11 passed. Suppressing abnormal stop log, bypassing caller seam, suppressing output emit each killed by C1 matrix (mutants exit 1, 3 failed/3 passed). Restored source SHA256 `8d2ed317cc5623fd89ecaeba7bc2dfdb3d85870845d40f024a2ceeed217b532c`. Ruff `--ignore-noqa` exit 1, driver 97→93; helper C901 5 under diagnostic threshold 0. Strict full gate and live-host acceptance remain open.

### S13.2/I-52 — conversation replay module boundary

Moved the already-extracted replay seam and its summary merge to `src/fa/inner_loop/conversation_history.py`; `coder_loop` calls the new owner before appending the user row, warning keeps the original logger name, and public `drive_session`/`SessionOutcome` remain untouched. Existing read/partial failure policy preserved. AST comparison against pre-slice saved source `/tmp/q137-notool-good`: both moved function bodies identical. New C1 checks repeated prior user rows remain duplicated in provider request; existing C1 latest compaction, no-compaction and dangling-tool, C0 read failure/logger. This is not a live-host or managed-isolation claim. Live ledger-append cases L-RCPT-2/L-RCPT-6 and L-ENTRY-4 remain planned, not executed.

`pytest -q tests/test_s13_replay.py tests/test_s13_ordering_fix.py tests/test_s13_strict_transport.py tests/test_s13_error_surfacing.py tests/test_coder_loop.py tests/test_pr2_wiring.py tests/test_pr5_wiring.py tests/test_compaction_c1_wiring.py tests/test_s6_stop_paths.py --disable-warnings`: exit 0, 100 passed, repeated after mutations. Focused `test_s13_replay.py`: exit 0, 5 passed; complexity ratchet 11 passed. Ruff/format/Pyrefly/mypy/diff-check and two import orders (history-first and CLI-first) exit 0. Removing user replay producer killed 2 C1 tests; replacing caller seam with empty history killed 2 C1 tests (mutant exit 1). Restored SHA256 driver `1205326ed45f339a8ab5d2d81d251f77e764ba524b9b8d17a968582e672e87e3`, owner `2ef627a4a3c5a67816be5d51fe0b64c3e3001ada2e9d2a085ba3228d3e797f05`; main module 2198→2136 lines, new owner 78, driver complexity unchanged. Import order does not prove global absence of cycles.

Additional checks: `python scripts/check_log_kind_contract.py` exit 0; `python scripts/check_producer_consumer_contract.py` exit 1 because hook_deny literal-site floor 4 vs actual 3. Pre-slice `/tmp/q137-notool-good` SHA `8d2ed317cc5623fd89ecaeba7bc2dfdb3d85870845d40f024a2ceeed217b532c` and current source both count 3 by the checker's regex, showing this was introduced by earlier terminal-stop consolidation, not replay move. It was missed by the earlier targeted report. The checker counts sites rather than paths; investigate and fix separately without lowering path coverage or suppressing the check. Full gate remains BLOCKING.

### 2026-11-09 — protocol/tool-turn ten-unit extraction

See architecture map §17.7 for boundaries, rationale and non-claims. Restored targeted banks: 155 passed/1 deselected and 42 passed; undeselected bank 155 passed/1 failed (`test_cmd_run_applies_config_per_role_limit_end_to_end`: existing managed execution unavailable). Producer/consumer and LogKind scripts exit 0; Ruff, format, Pyrefly, mypy, diff-check exit 0. Eight producer/EDGE mutations killed (protocol ID, padding, terminal stop, redaction); two independent terminal emitter deletions killed by checker tests. The earlier red hook_deny floor regression is repaired without reducing floor. Hashes: driver a85ce8d79054835ae0eff8319dd988af7d77c02fa1fa910831114be74ed40dc6; history 76f59bca4898c65ca168b62e21895843b9d851a91004fed7512a8f5e74b50f94; tool turn b2c9a6af453ddbc398bb1dc9e3602b5a7b9ec383b9209a7475a873f0a459c3d1. Full gate and planned L-RCPT-2/6, L-ENTRY-4 live-host E2E not rerun.

### 2026-11-09 — P5/P6 response and continuing tool-turn phases

See map §17.8. Driver function 1325→1260 lines, diagnostic C901 93→81; orchestration and side-effect order retained. Targeted banks after restoring mutants: 144 passed/1 deselected, 56 passed, 106 passed (exit 0). Broad run including `tests/test_s7_correlation.py`: 144 passed/1 deselected/5 setup errors, all existing CLI fixture `managed_execution_unavailable`; no managed bypass. Earlier initial checks found missing `effective_limits` after extraction and mypy narrowing error in the test; both corrected, final Ruff/format/Pyrefly/mypy, both producer checkers, import-order checks and diff-check exit 0. Eleven producer/EDGE mutants killed (model audit/history/caller, cap signal/caller, exhaustion dual-write/latch, tool event/caller, session-end). S6 proximity false positive for final cap replaced with narrow structural check plus C1 durable row/session-end assertion; broader heuristic limitations remain. SHA256: driver dc7f073940e59b974a4dec40f71392b27109b4f599285bc4a27471834b157cd7, history d86acd586167c3c1d25f3dea5dd4443939de1d8e3d1b6767daeb5ab6e9afe3eb, tool-turn 78c5b874faafa055c94874981512ce75b47853511c7f6c21d85cb735035b528b. No full-gate or live-host acceptance claim.

### 2026-11-09 — Agent-legibility target and sub-goals

Historical note: the proposed numeric advisory band has been withdrawn by the user; current requirement is the qualitative instruction in AGENTS.md and map §18. AL1–AL6 prioritize bounded task working sets, real cohesive ownership, navigation, measured representative paths, safety and producer/EDGE tests; plan keeps full Q137 gate and live-host ledger evidence open. `AGENTS.md` now carries the concise project-wide principle without replacing existing safeguards. Next: source-check scope-expansion ownership and choose a proven phase extraction.

### 2026-11-09 — AL2 scope-turn runtime phase

See map §18.3 for explicit ownership, scope-task path measurements and tradeoffs. Driver file 1866→1726 lines, driver function 1260→1154, C901 81→74; runtime owner `scope_turn.py` 200 lines / evaluator C901 8. Moved statements AST-identical under local renaming, excluding returned render/caller-owned append. New C1 L1→L2→L3 after failed verification and missing-skill warning; copied-tree checker emitter deletion detected. Final banks 181 passed and 133 passed; 8 producer/EDGE mutants killed; scanner contracts, targeted Ruff/format/Pyrefly/mypy, doc links, two import orders, diff-check exit 0. Initial invalid scope event string detected by typing and fixed; existing literal append check exposed variable rename, restored real append expression. SHA driver be264b33401f45a7c674ae20f7baf1fd789d7897956fa0a01213c5c8e06aa42b, scope owner 6405ccb4b9513fda14287de1125ecd40f27545cdb759fc14a5ad2d175a29d78e. No full gate or live-host acceptance.

### 2026-11-09 — qualitative agent-legibility requirement and P1 payload owner

User withdrew numerical LOC heuristic entirely: `AGENTS.md` now gives two-sentence cohesive-working-set instruction, and map §18 has no size threshold, trigger, goal or floor. P1 execution is in map §18.4: existing composer now owns family-specific payload assembly; per-turn binding and three driver rebuild call sites remain. C1 Stage2 and Stage3 provider-message assertions, C0 final-role guard, source AST/edge test; restored banks 98 and 159 passed. Eight producer/EDGE mutants killed. Initial guessed skill-test node and an adjacent bank's nonexistent file each exited 4 and ran no tests; corrected invocations passed/killed as applicable. Both observability checkers, Ruff, format, Pyrefly, mypy, docs, imports and diff-check exit 0. SHA driver 41cb2ccb71f40d6a68d6dc9eda7d45ef514b571fed2378d400d7bb488f1aa6d6; composer f5f3dbeb2b4c8460fc7c43867f4c8896b49d386774526572cea942def213eb6a. Full gate and live ledger-host cases remain open.

### 2026-11-09 — documentation and pre-push verification

Updated `AGENTS.md`, architecture map, Q137 triage/current status, Q137 question, documentation index and handoff to reflect completed slices, qualitative agent-legibility goal, unresolved full gate and unexecuted live-host evidence. Before committing, fetched the session's existing remote tip `be1fdc3` and aligned the local branch metadata to that ancestor without modifying workspace files; SHA256 manifest for all 139 changed/untracked workspace files matched before/after, preserving the remote feature commits. Focused pre-push run (`test_pr3_wiring`, `test_compaction_c1_wiring`, `test_scope_expansion_wiring`, `test_s13_replay`, `test_s6_stop_paths`, `test_s6_checker_contracts`) exit 0: 66 passed. Producer/consumer, LogKind, doc-links and diff checks exit 0. No full gate or live-host E2E was rerun.
