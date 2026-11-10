# Реестр diff review — 2026-11-09

База: `98ca1a7`; сравниваемый commit: `be1fdc3`, плюс незакоммиченный узкий Q97 срез (он отдельно упомянут в предварительном отчёте). Перечень генерирован из `git diff --name-only 98ca1a7 HEAD -- src tests`: 172 файлов. Цель пользователя — все оставшиеся файлы; полная adversarial проверка не завершена.

Статусы намеренно консервативны: **D** — прочитан целиком текст изменённых hunks, первичная оценка, но не полная проверка интеграции/всех edge cases; **P** — только отдельные hunks или сценарии; **—** — не проверено. Ни D, ни P не означают, что файл утверждён, что все тесты сильны или что соответствующие контракты закрыты. Не выбирать лёгкие файлы вместо связанных критических путей. D: 109; P: 31; —: 32. Для завершения общего задания требуется углубить эти записи и продолжить незаконченные подсистемы.

Подтверждены Q98 stats, переполнение serialized cell frame, утечка worker gate на deadline и разбор quoted service_config; свидетельства в отдельном предварительном отчёте. Для файлов D это не исчерпывающее заключение.

Батч транспорта: 148 passed, 1 failed в 9 тестовых файлах; повторный отдельный батч из 5 файлов worker/frame — 85 passed; failure в `test_workspace_authorize.py` (в перечне нет DIFF_REVISIONS) ранее содержится в Q137. Исследованы реальный helper → cell frame → socketpair WorkerClient и boundary истечения deadline. Полный gate и Docker/live-host не запускались.

Последний обзорный батч: port/purposes/readers/index diff прочитан; до исправления 116 passed, 1 failed в 5 файлах — известный Q137 stale readonly-enum oracle (отсутствует DIFF_REVISIONS). Затем тестовый срез по Q129-A: явный readonly set исправлен; service-wire negative capability тест добавлен. Расширенный набор 7 файлов: 244 passed (exit 0); Ruff, format, focused Pyrefly и diff-check exit 0. Producer mutant исключения DIFF_REVISIONS убит (pytest exit 1); EDGE mutant отключения dispatcher → handler убит (exit 1); supervisor.py восстановлен SHA-256 aaf8c9404f38006eb4109fcdc691ff85a3a189c4cc5b990c0dbd49716580b2a1; после восстановления 2 passed. Это не повтор полного gate и не live-host acceptance. Замена managed индексных positive-тестов на host positive и managed refusal не доказывает managed C1; этот пробел остаётся. Это конец обзорного батча, не завершение review всех файлов.

Eval/legacy: 40 passed в 3 файлах; при удалении старых Git tests legacy workflow потерял diff evidence, нужно сопоставить Q129-A и сохранение legacy контракта; подробности в отчёте.

Planner/registry: 76 passed в пяти файлах; воспроизведено влияние host canonical paths на решение managed planner writer; production-authority проверка ещё нужна. Полный diff workflow_controller и registry/plan-promotion файлов прочитан, дополнительное интеграционное рассмотрение остаётся.

Новый батч: journal/protocol/service — 201 passed; PTY/runtime — 48 passed, 6 skipped (runtime extra deferred); safe-walk/index/discovery — 146 passed. Прочитаны полные diff journal/profiles/receipts/service/supervisor, safe walk/search/structural index, PTY и соответствующих отмеченных тестов; tests subagent используют fake client/executor и не доказывают live isolation. Тесты с одними только запусками отмечены P.

Managed mutation/subagent/lease: 42 passed в 6 файлах; воспроизведены пропуск enabled guard и post-entry в чужой board при валидных stamps и неверном board root; см. отчёт. Частичный просмотр subagent/lease не означает завершённый review.

Managed discovery: 122 passed в 6 файлах; отдельно подтверждён отказ широкого in-budget дерева при RLIMIT_NOFILE=256, подробности в отчёте.

По Q98 найден дефект в `src/fa/stats.py`; свидетельства в отдельном предварительном отчёте. Контракты Q126/Q130 сняли прежнюю product-регистрацию host subagent и runtime IntentGuard; удалённые тесты не автоматически считаются потерей действующего контракта. Но регистрация managed child после escalation gate и тесты только unmanaged fixture требуют отдельной проверки поведения и политики: child в R13 read-only, поэтому обход write-гейта не следует объявлять подтверждённой записью или дефектом без дальнейшей проверки. `tests/test_workspace_bootstrap.py` заменяет старый manager-root oracle прямым вызовом bootstrap; managed readiness caller coverage следует проверять в `test_cli.py`/`test_execution_composition.py`, а не считать этот тест C1 для manager.

В этом батче запускались 10 выбранных файлов: `test_stats`, `test_execution_handoff`, `test_execution_receipts`, `test_execution_provisioning`, `test_execution_context`, `test_execution_supervisor`, `test_s5_isolation_boundary`, `test_workspace_bootstrap_aliases`, `test_structural_index`, `test_chat_escalation_gate`: 256 passed, 1 xfailed (известная legacy Q19). Это не полная проверка оставшихся файлов и не live-host acceptance.

| № | Файл | Статус |
|---:|---|:---:|
| 1 | `src/fa/cli.py` | P |
| 2 | `src/fa/config.py` | D |
| 3 | `src/fa/execution/backend.py` | P |
| 4 | `src/fa/execution/cell_protocol.py` | D |
| 5 | `src/fa/execution/cell_worker.py` | P |
| 6 | `src/fa/execution/client.py` | P |
| 7 | `src/fa/execution/composition.py` | — |
| 8 | `src/fa/execution/docker.py` | D |
| 9 | `src/fa/execution/environment_artifact.py` | P |
| 10 | `src/fa/execution/journal.py` | D |
| 11 | `src/fa/execution/primitives.py` | D |
| 12 | `src/fa/execution/profiles.py` | D |
| 13 | `src/fa/execution/project_tools.py` | P |
| 14 | `src/fa/execution/protocol.py` | P |
| 15 | `src/fa/execution/provisioning.py` | D |
| 16 | `src/fa/execution/publication.py` | D |
| 17 | `src/fa/execution/receipts.py` | D |
| 18 | `src/fa/execution/service.py` | D |
| 19 | `src/fa/execution/supervisor.py` | D |
| 20 | `src/fa/execution/termination.py` | D |
| 21 | `src/fa/execution/tool_port.py` | D |
| 22 | `src/fa/execution/types.py` | D |
| 23 | `src/fa/execution/worker_client.py` | D |
| 24 | `src/fa/execution/workspace.py` | P |
| 25 | `src/fa/feature_flags.py` | D |
| 26 | `src/fa/hygiene/pr_intent.py` | D |
| 27 | `src/fa/inner_loop/admission_schema.py` | — |
| 28 | `src/fa/inner_loop/coder_loop.py` | P |
| 29 | `src/fa/inner_loop/hooks/builtin.py` | D |
| 30 | `src/fa/inner_loop/hooks/intent_guard.py` | D |
| 31 | `src/fa/inner_loop/injections.py` | D |
| 32 | `src/fa/inner_loop/loop.py` | P |
| 33 | `src/fa/inner_loop/managed_acquisition.py` | P |
| 34 | `src/fa/inner_loop/managed_inventory.py` | D |
| 35 | `src/fa/inner_loop/plan_promotion.py` | D |
| 36 | `src/fa/inner_loop/pr_draft.py` | D |
| 37 | `src/fa/inner_loop/profiles.py` | D |
| 38 | `src/fa/inner_loop/prompt.py` | D |
| 39 | `src/fa/inner_loop/routing.py` | D |
| 40 | `src/fa/inner_loop/state.py` | D |
| 41 | `src/fa/inner_loop/tools/__init__.py` | D |
| 42 | `src/fa/inner_loop/tools/_common.py` | D |
| 43 | `src/fa/inner_loop/tools/edit_file.py` | D |
| 44 | `src/fa/inner_loop/tools/fs_reach.py` | P |
| 45 | `src/fa/inner_loop/tools/fs_search.py` | P |
| 46 | `src/fa/inner_loop/tools/managed_project_tool.py` | D |
| 47 | `src/fa/inner_loop/tools/managed_subagent.py` | D |
| 48 | `src/fa/inner_loop/tools/mutation_guard.py` | D |
| 49 | `src/fa/inner_loop/tools/prepare_pr.py` | D |
| 50 | `src/fa/inner_loop/tools/run_bash.py` | D |
| 51 | `src/fa/inner_loop/tools/workflow_tool.py` | — |
| 52 | `src/fa/inner_loop/tools/workspace_port.py` | D |
| 53 | `src/fa/inner_loop/tools/write_file.py` | D |
| 54 | `src/fa/inner_loop/workflow_artifacts.py` | D |
| 55 | `src/fa/inner_loop/workflow_controller.py` | D |
| 56 | `src/fa/memory/_safe_walk.py` | D |
| 57 | `src/fa/memory/managed_discovery.py` | D |
| 58 | `src/fa/memory/search_index.py` | D |
| 59 | `src/fa/memory/structural_index.py` | D |
| 60 | `src/fa/runtime/bash_executor.py` | D |
| 61 | `src/fa/runtime/pty_pool.py` | D |
| 62 | `src/fa/runtime/server.py` | D |
| 63 | `src/fa/session/manager.py` | — |
| 64 | `src/fa/session/provisioning.py` | D |
| 65 | `src/fa/stats.py` | D |
| 66 | `src/fa/workspace/__init__.py` | D |
| 67 | `src/fa/workspace/worktree_manager.py` | D |
| 68 | `src/fa/workspace_bootstrap.py` | D |
| 69 | `tests/_chat_registry_fixture.py` | D |
| 70 | `tests/conformance/test_live_executor.py` | D |
| 71 | `tests/test_arena_env_build.py` | — |
| 72 | `tests/test_cell_worker_output_budget.py` | D |
| 73 | `tests/test_chat_escalation_gate.py` | D |
| 74 | `tests/test_chat_role.py` | D |
| 75 | `tests/test_cli.py` | — |
| 76 | `tests/test_cli_ergonomics.py` | — |
| 77 | `tests/test_coder_loop.py` | — |
| 78 | `tests/test_config.py` | D |
| 79 | `tests/test_controller_installed.py` | — |
| 80 | `tests/test_coverage_failure_paths.py` | D |
| 81 | `tests/test_dead_flags.py` | D |
| 82 | `tests/test_delivery_law_conformance.py` | — |
| 83 | `tests/test_deploy_scripts.py` | — |
| 84 | `tests/test_e2e_artifact_contract.py` | D |
| 85 | `tests/test_eval_evidence_block.py` | D |
| 86 | `tests/test_execution_admission.py` | D |
| 87 | `tests/test_execution_attach_budget.py` | D |
| 88 | `tests/test_execution_backend.py` | — |
| 89 | `tests/test_execution_cell_worker.py` | P |
| 90 | `tests/test_execution_client.py` | — |
| 91 | `tests/test_execution_client_port.py` | — |
| 92 | `tests/test_execution_client_stage.py` | — |
| 93 | `tests/test_execution_composition.py` | — |
| 94 | `tests/test_execution_context.py` | D |
| 95 | `tests/test_execution_dispatch.py` | D |
| 96 | `tests/test_execution_docker.py` | — |
| 97 | `tests/test_execution_environment_artifact.py` | — |
| 98 | `tests/test_execution_frame_bounds.py` | D |
| 99 | `tests/test_execution_handoff.py` | D |
| 100 | `tests/test_execution_handoff_return.py` | — |
| 101 | `tests/test_execution_journal.py` | D |
| 102 | `tests/test_execution_plans.py` | D |
| 103 | `tests/test_execution_project_request_json.py` | P |
| 104 | `tests/test_execution_project_tools.py` | P |
| 105 | `tests/test_execution_protocol.py` | D |
| 106 | `tests/test_execution_provisioning.py` | D |
| 107 | `tests/test_execution_purposes.py` | D |
| 108 | `tests/test_execution_readers.py` | D |
| 109 | `tests/test_execution_receipts.py` | D |
| 110 | `tests/test_execution_reply_cache_budget.py` | D |
| 111 | `tests/test_execution_service.py` | D |
| 112 | `tests/test_execution_supervisor.py` | D |
| 113 | `tests/test_execution_tool_index.py` | D |
| 114 | `tests/test_execution_tool_port.py` | D |
| 115 | `tests/test_execution_views.py` | D |
| 116 | `tests/test_execution_worker_reply_budget.py` | P |
| 117 | `tests/test_execution_workspace.py` | — |
| 118 | `tests/test_fa_entrypoint.py` | — |
| 119 | `tests/test_fs_reach.py` | P |
| 120 | `tests/test_fs_search.py` | P |
| 121 | `tests/test_hygiene_hooks_self_bootstrap.py` | — |
| 122 | `tests/test_intent_guard_mode.py` | — |
| 123 | `tests/test_invoke_workflow_tool.py` | — |
| 124 | `tests/test_live_check_script.py` | D |
| 125 | `tests/test_managed_acquisition.py` | P |
| 126 | `tests/test_managed_bash_tool.py` | P |
| 127 | `tests/test_managed_discovery_budget.py` | D |
| 128 | `tests/test_managed_discovery_refusal.py` | P |
| 129 | `tests/test_managed_edit_completeness.py` | P |
| 130 | `tests/test_managed_mutation_guard.py` | D |
| 131 | `tests/test_managed_mutation_metadata.py` | D |
| 132 | `tests/test_managed_project_tool.py` | D |
| 133 | `tests/test_managed_project_tool_paths.py` | D |
| 134 | `tests/test_managed_read_windows_port.py` | — |
| 135 | `tests/test_managed_registry_binding.py` | P |
| 136 | `tests/test_managed_stage_lease.py` | P |
| 137 | `tests/test_managed_subagent.py` | D |
| 138 | `tests/test_managed_write_uncertainty.py` | D |
| 139 | `tests/test_observability_edge_cases.py` | D |
| 140 | `tests/test_observability_fix_p2.py` | D |
| 141 | `tests/test_plan_candidate_retention.py` | P |
| 142 | `tests/test_prepare_pr.py` | D |
| 143 | `tests/test_prompt_registry_coherence.py` | P |
| 144 | `tests/test_pty_bounded_pexpect.py` | D |
| 145 | `tests/test_pty_capture_limits.py` | D |
| 146 | `tests/test_quality_slice_coverage.py` | D |
| 147 | `tests/test_readiness_announcement.py` | D |
| 148 | `tests/test_runtime_server_c1.py` | P |
| 149 | `tests/test_runtime_server_open_stand.py` | P |
| 150 | `tests/test_s10b_cli_parity.py` | P |
| 151 | `tests/test_s10c_workflow_exit_contract.py` | — |
| 152 | `tests/test_s13_fail_closed_open.py` | D |
| 153 | `tests/test_s5_isolation_boundary.py` | D |
| 154 | `tests/test_s8_workflow_controller.py` | P |
| 155 | `tests/test_safe_walk.py` | D |
| 156 | `tests/test_session_lifecycle.py` | — |
| 157 | `tests/test_session_manifest_guards.py` | — |
| 158 | `tests/test_session_workspace_provisioning.py` | — |
| 159 | `tests/test_skill_conformance.py` | — |
| 160 | `tests/test_slice5_6_7_wiring.py` | D |
| 161 | `tests/test_stage_checkpoints.py` | D |
| 162 | `tests/test_stats.py` | D |
| 163 | `tests/test_structural_index.py` | D |
| 164 | `tests/test_subagent_termination_wiring.py` | D |
| 165 | `tests/test_tool_batching.py` | D |
| 166 | `tests/test_tools_common.py` | D |
| 167 | `tests/test_verify_gate_live.py` | — |
| 168 | `tests/test_workspace_authorize.py` | D |
| 169 | `tests/test_workspace_bootstrap.py` | D |
| 170 | `tests/test_workspace_bootstrap_aliases.py` | D |
| 171 | `tests/test_workspace_publication.py` | — |
| 172 | `tests/test_workspace_recovery.py` | D |
