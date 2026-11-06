# W0 read-only audit — R01, R03, R14–R28 (2026-11-04)




**Status:** READ-ONLY AUDIT — no runtime/test code changed. No tests were run.
The results below are from the current source, the inventory, the ledger, and
the test files; they are not new test evidence. R12/Q125 is audited separately
(`notes/q125-r12-audit-2026-11-04.md`). R02, R04–R11 are recorded as having
local oracles; R13 is recorded as locally closed. This note does not close any
row.




**Method:** for each row, read the current producer and the reachable production
caller, inspect the named/actual tests and their fixtures, and compare the
negative oracle/no-effect criteria to the source. The inventory line numbers are
from an earlier commit and are refreshed where checked. "Component" means a
unit/helper test with a fake port/runner; "production-caller" means the test
drives `fa.cli.main`/`_cmd_run`/`drive_session`/the real registry; "local UDS"
means a real local `SupervisorService`/`WorkspaceAuthority` with provider I/O
mocked.




---




## 1. R01 — wrapper route / isolated controller entry




**Contract/gap.** The wrapper must start the installed controller from a trusted
CWD with explicit project selection; poisoned CWD/PYTHONPATH must not alter
controller imports. Ordinary product dispatch still runs `fa.cli:main`
(`pyproject.toml:98`), not the isolated `fa.controller_entry`
(`Dockerfile.fa:97–98`). Q119-A selected full command/workspace coverage; Q120
classified `fa egress-proxy` as Compose-owned. The wrapper→installed-controller
composition is still OPEN.




**Source→caller map.**




- `scripts/fa:36–45` reads `.active`; `:58–82` rejects wrapper help; `:89–181`
 dispatches host/product commands.
- `pyproject.toml:98` `fa = "fa.cli:main"`.
- `Dockerfile.fa:97–98` build-smoke-tests `controller_entry`.
- `scripts/fa-entrypoint.sh` publishes `.active`; `cli._session_manager_for_args`
 selects the workspace/session; `SessionManager.resolve_active_session_for_workspace`
 is a read-only resolver with no CLI/wrapper caller.




**Existing tests/nodeids.** `tests/test_deploy_scripts.py` wrapper help/dispatch
tests (component/script-level); `tests/test_controller_installed.py::test_actual_installed_cli_help_ignores_project_cwd_pythonpath_and_venv`
(direct installed-CLI proof, not wrapper composition). The named
`test_fa_wrapper_*` tests exist and are script-level; they do not prove the
wrapper→installed-controller composition.




**Minimal files/seams.** `scripts/fa`, `scripts/fa-entrypoint.sh`,
`src/fa/cli.py::_session_manager_for_args`,
`src/fa/session/manager.py::resolve_active_session_for_workspace`,
`pyproject.toml`, `Dockerfile.fa`.




**Proposed tests/mutations.** Wrapper→installed-controller composition test with
poisoned CWD/PYTHONPATH; assert the installed controller imports from the trusted
CWD and the project selection is explicit. Mutation: remove the isolated
controller entry; remove the trusted-CWD validation; remove the explicit project
selection.




**Q#.** No new Q#; Q119-A/Q120 provide the policy. R01 remains OPEN.




---




## 2. R03 — bootstrap wrapper / poisoned checkout




**Contract/gap.** `scripts/bootstrap/workspace.py:13–17` prepends the checked-out
`src` before readiness import. The managed provisioning cell must run the
project-side wrapper inside the cell or use the installed trusted dispatcher; a
poisoned checkout must not execute on the controller. The managed provisioning
cell is the target; the host bootstrap wrapper remains a TCB host path.




**Source→caller map.** `scripts/bootstrap/workspace.py:13–17` → `src/fa/workspace_bootstrap.py`
readiness import; `scripts/bootstrap/host_bootstrap.py` operator path;
`justfile:112` `agent-bootstrap`.




**Existing tests/nodeids.** `tests/test_workspace_bootstrap_aliases.py::test_just_bootstrap_aliases_converge_and_doctor_is_read_only`
(component/script-level); `tests/test_workspace_bootstrap.py` readiness/process
tests (component). No production managed-cell bootstrap test.




**Minimal files/seams.** `scripts/bootstrap/workspace.py`,
`src/fa/workspace_bootstrap.py`, `src/fa/session/manager.py`,
`src/fa/execution/provisioning.py`, `scripts/fa-entrypoint.sh`.




**Proposed tests/mutations.** Run the bootstrap wrapper inside the provisioning
cell; assert a poisoned checkout cannot execute on the controller. Mutation:
remove the `src` prepend; remove the cell-local execution; allow host bootstrap.




**Q#.** No new Q#; Q112/Q118 provide the readiness/provisioning policy. R03
remains OPEN.




---




## 3. R14 — tool registry exception fallback




**Contract/gap.** `build_baseline_registry`/`build_planner_registry`/`build_eval_registry`/`build_chat_registry`
(`src/fa/inner_loop/tools/__init__.py:175,230,285,337`) still register bash in an
exception fallback. The managed registry must fail closed; a profile construction
failure must register zero project commands, never host shell.




**Source→caller map.** `tools/__init.py` build_*_registry → `profiles.py::build_registry_for_role`
→ `cli.py::_build_run_tool_registry` → `drive_session`.




**Existing tests/nodeids.** `tests/test_execution_tool_index.py::test_a_managed_registry_ships_no_host_git_tools`
(component: `build_baseline_registry` with a fake port); the named
`test_profile_construction_failure_registers_no_project_command` is **absent**.




**Minimal files/seams.** `src/fa/inner_loop/tools/__init__.py`,
`src/fa/inner_loop/profiles.py`, `src/fa/cli.py::_build_run_tool_registry`.




**Proposed tests/mutations.** Production `_cmd_run`/`drive_session` with a profile
construction failure; assert zero project-command tools and zero host shell.
Mutation: remove the exception fallback; remove the managed fail-closed branch.




**Q#.** No new Q#; R14 remains OPEN.




---




## 4. R15 — file tools / host filesystem




**Contract/gap.** `fs_write_file`/`fs_edit_file` must write through the admitted
view port, not the host filesystem. The current handlers use `workspace_io` when
present; the production managed registry binds the port. The named
`tests/test_managed_workspace.py::test_file_handlers_write_through_the_view_only`
is **absent** (the file does not exist).




**Source→caller map.** `tools/write_file.py:102`, `tools/edit_file.py:160` →
`profiles.py` builders → `cli.py::_build_run_tool_registry` → `drive_session`.




**Existing tests/nodeids.** `tests/test_execution_tool_port.py::test_tools_built_with_the_port_read_write_and_edit_through_it`
(component: real `WorkspaceAuthority` + PROJECT view, no container/PTY);
`test_baseline_registry_forwards_the_port_to_the_write_tool` (component). No
production-caller test.




**Minimal files/seams.** `src/fa/inner_loop/tools/write_file.py`,
`src/fa/inner_loop/tools/edit_file.py`, `src/fa/inner_loop/profiles.py`,
`src/fa/cli.py::_build_run_tool_registry`.




**Proposed tests/mutations.** Production `fa run`/`drive_session` with a fake
provider calling `fs_write_file`/`fs_edit_file`; assert the write goes through the
port and the canonical tree is unchanged until publication. Mutation: remove the
`workspace_io` binding; remove the port write path.




**Q#.** No new Q#; R15 remains OPEN.




---




## 5. R16–R19 — host Git in the controller




**Contract/gap.** The controller must not run project Git. Each producer uses
`subprocess.run` with a host `git` binary. The managed metadata/view is the
target.




| Row | Producer | Current line | Production caller | Existing test | Gap |
|---|---|---|---|---|---|
| R16 | `workflow_controller._git_output` | `:848` | stage loop / eval context | `tests/test_slice_verification_runner.py` (component; no `_git_output` test) | named `test_stage_diff_never_runs_controller_git` absent |
| R17 | `pair_tools._run_git` | `:28–30` | chat/coder pair tools | `tests/test_subagent_termination_wiring.py` (subagent timeout/ctrl_c; not pair_tools) | named `test_pair_tools_use_the_writer_view_and_never_the_canonical_index` absent |
| R18 | `mutation_guard._base_commit` | `:60–67` | coder admission | `tests/test_s5_blackboard_contract.py::test_same_base_commit_conflict_denied` (blackboard conflict, not `_base_commit`) | named `test_denied_base_commit_lookup_blocks_admission` absent |
| R19 | `intent_guard._default_git_runner` | `:272–273` | every gated tool call | `tests/test_intent_guard.py::test_intent_guard_silently_allows_when_git_fails` (injected failing runner; component) | named `test_intent_git_failure_never_bypasses_view_admission` absent |




**Minimal files/seams.** `workflow_controller._git_output`, `pair_tools._run_git`,
`mutation_guard._base_commit`, `intent_guard._default_git_runner`; the managed
metadata/view port is the replacement.




**Proposed tests/mutations.** For each producer: production stage/chat/coder call
with a fake managed metadata source; assert zero host Git and the managed
metadata is used. Mutation: remove the managed binding; remove the fail-closed
path.




**Q#.** No new Q#; R16–R19 remain OPEN.




---




## 6. R20/R21 — memory/search host Git




**Contract/gap.** R20: `memory/_safe_walk.py::_git_ls_files` (`:452–473`) uses
`subprocess.run`; the managed search must use the view-local index, not host Git.
R21: `tools/_common.py::git_ls_files` (`:22–40`) has no production caller; it is
dormant/dead code.




**Source→caller map.** R20: `_safe_walk` → `search_index`/`structural_index` →
`execution/project_tools.py::_dispatch` → `fs_search`/`fs_reach`. R21: no
production caller.




**Existing tests/nodeids.** R20:
`tests/test_execution_tool_index.py::test_a_managed_search_runs_no_host_git_subprocess`
(component: `build_fs_search_tool` with a fake port; asserts zero host Git on the
managed refusal); `tests/test_safe_walk.py` (component). R21:
`tests/test_tools_common.py::TestGitLsFiles` (unit).




**Minimal files/seams.** R20: `memory/_safe_walk.py`, `tools/fs_search.py`,
`execution/project_tools.py`. R21: `tools/_common.py` (delete or keep dormant).




**Proposed tests/mutations.** R20: production `fa run`/`drive_session` with a
managed search; assert zero host Git. Mutation: remove the no-`.git` guard; remove
the managed refusal. R21: no production test; disposition dormant/dead code.




**Q#.** No new Q#; R20 remains OPEN; R21 is dormant/no product edge.




---




## 7. R22 — PR intent / hooks host Git




**Contract/gap.** `hygiene/pr_intent.py::_run_git` (`:817–822`) and
`hygiene/hooks/_util.py::resolve_hooks_dir` (`:91–102`) use host Git. The managed
revision/view is the target. The named
`test_pr_prepare_reads_only_a_managed_revision` is **absent**.




**Source→caller map.** `pr_intent._run_git` → `_cli_prepare`/`_cli_validate` →
chat `pr_prepare`; `resolve_hooks_dir` → readiness hook lookup.




**Existing tests/nodeids.** `tests/test_pr_intent_snapshot.py` (classifier/intent
component; no `_run_git` host Git test); `tests/test_hygiene_hooks_install.py`
(component).




**Minimal files/seams.** `src/fa/hygiene/pr_intent.py`,
`src/fa/hygiene/hooks/_util.py`.




**Proposed tests/mutations.** Production chat `pr_prepare` with a managed
revision; assert zero host Git and the managed revision is used. Mutation: remove
the managed revision binding; remove the fail-closed path.




**Q#.** No new Q#; R22 remains OPEN.




---




## 8. R23 — legacy worktree manager


# Q126 / R23 — handoff: managed subagents, вариант A

**Назначение:** краткий справочник следующему агенту для согласованного закрытия Q126/R23. Это не разрешение закрыть весь W0 или начать W1.

## Направление

Оператор склоняется к полному переходу поддерживаемых subagent-сценариев на **managed R13**. По Q126 выбранное направление — **A: вывести R23 из managed W0 как legacy worktree-кандидат**. Рекомендация для R23: после проверки call graph удалить не только dormant Git-worktree runtime, но и старый host-runner subagent-маршрут из поддерживаемых product registries. Это два разных участка; не удалять их вслепую одним broad cleanup.


## Контракт R13

```text
родитель — единственный writer
  -> PIN_READER: child привязывается к опубликованной revision
  -> supervisor даёт READ-view
  -> child: read-only проект + stateless Bash + private /scratch
  -> bounded report родителю
  -> родитель применяет изменения
```

Никакого второго writer и никакого host fallback при отказе supervisor. Это подходящая граница для AI harness: Git worktree разделяет каталоги/ветки, но не полномочия процесса; READ-view и supervisor контролируют полномочия. Child исследует, родитель изменяет.

## Фактический call graph — не смешивать три пути

1. **Dormant R23 Git-код:** `IsolatedWorktreeManager.create_subagent_workspace()` вызывает host `git worktree` (`src/fa/workspace/worktree_manager.py:145–248`), cleanup — Git (`:250–270`). Фабрика разрешает только `shared`, isolated mode отвергает (`:273–304`). Production caller isolated producer не найден; прямые тесты не доказывают production-путь.
2. **Старый host-runner:** при `workspace_io is None` старый `fs_spawn_subagent` вызывает `SessionState.create_subagent_workspace()` и затем `SubagentRunner`. Но `SessionState` создаёт `.fa/subagents/<task>` через `ensure_subagent_artifact_root()` (`src/fa/inner_loop/state.py:710–741`), а не Git worktree; runner запускает host subprocess (`src/fa/inner_loop/tools/spawn_subagent.py:165–179, 210–228`). Legacy feature flag по умолчанию выключен, но этот путь ещё есть.
3. **Managed R13:** отдельный builder, pinned READ-view, `ClientWorkspacePort` и `ReadOnlyManagedBashExecutor`; ограниченная child registry в `src/fa/inner_loop/tools/managed_subagent.py`. Managed registry не должен переключаться на старый builder при отсутствии backend.

Инвентарь уже точнее описывает отсутствие R23 production caller в `notes/i03-execution-call-inventory.md` §R23 refresh (`:189–203`), но ранняя таблица (`:97`) и proposed Q126 source map могут ей противоречить. Исправить их; не считать artifact-root тест Git-worktree или managed-child доказательством.

## План закрытия

1. **Канонически записать Q126-A** и исправить R23 producer/caller row и устаревший nodeid `test_subagent_isolation_never_touches_the_canonical_root` (он отсутствует). Индекс `notes/README.md` должен ссылаться на новую запись.
2. **Согласовать Q113/W0 явно:** R23 пометить `RETIRED / NOT APPLICABLE TO MANAGED W0`, не `PASS`. Если retired row исключается из W0 active set, обновить правило/счётчик открыто, не молча. Остальные W0 строки остаются gate.
3. **Проверить ссылки и удалить legacy узко:** отдельный поиск всех imports/callers/tests/config flags. Удалить dormant `IsolatedWorktreeManager` и старый `spawn_subagent.py`/`SubagentRunner` из поддерживаемых product routes только если нет утверждённого unmanaged use case. Не удалять весь `worktree_manager.py`: сохранить `SharedDirWorktreeManager` и `ensure_subagent_artifact_root`/artifact safeguards там, где есть реальные callers. Общие feature flags удалять только после проверки их использования R13.
4. **Сохранить R13 и fail-closed поведение:** каждый поддерживаемый chat/planner/coder caller идёт только через R13; backend absent/denied/uncertain не вызывает host runner/worktree. Старый код, если оператор решит оставить его для ручной разработки, явно вне product/managed guarantees — не fallback.
5. **Не завысить acceptance:** E446 отмечает локальный R13 row DoD CLOSED; глобальный Q113 W0 остаётся OPEN до остальных строк. W1 и live-host acceptance этим решением не закрываются.

## DoD / проверка

- Q126, R23 inventory и Q113/W0 не противоречат друг другу: retirement — disposition, не тестовый PASS.
- Если runtime удаляется: managed production-caller positive/negative tests остаются зелёными; негатив доказывает отказ без host subprocess, `SubagentRunner`, Git worktree, proxy credential и project write. Mutation/EDGE kill-check: возврат legacy registration/fallback должен ломать этот oracle; удаление managed producer/caller edge тоже должно ломать positive test.
- Сохранены shared/artifact функции с действующими callers; удалены только подтверждённо ненужные legacy producers.
- Для текущего документа: markdown-link checker и whitespace/diff check. Runtime-тесты нужны только при последующем изменении кода.

**Не делать:** не включать worktrees ради R23; не оставлять fallback под видом compatibility; не удалять общую workspace-инфраструктуру без caller audit; не объявлять общий W0/W1 или deployed-host acceptance закрытыми.

---




## 9. R24 — verification / kill-check / eval host pytest




**Contract/gap.** `slice_verification._run_one` (`:330–334`),
`mutation_overlay` (`:980`), `_run_kill_check` (`:1439`), `capture_test_nodeids`
(`:539`) use host pytest. The managed verification scratch/receipt/report parsing
through managed `exec` is the target. The named
`test_kill_proof_requires_a_fresh_operation_and_source_binding` is **absent**.




**Source→caller map.** `slice_verification._run_one` → verify/kill-check/eval
stage loop; `workflow_controller` stage loop.




**Existing tests/nodeids.** `tests/test_mutation_overlay.py`,
`tests/test_verify_slice.py` (component: overlay/kill-check logic); no
production-caller managed verification test.




**Minimal files/seams.** `src/fa/inner_loop/slice_verification.py::_run_one`,
`mutation_overlay`, `_run_kill_check`, `capture_test_nodeids`; the managed
executor is the replacement.




**Proposed tests/mutations.** Production verify gate with a managed executor;
assert no host pytest and the receipt/report is bound to the pinned
source/PlanRef/profile. Mutation: remove the managed binding; remove the host
subprocess.




**Q#.** No new Q#; R24 remains OPEN (managed verification is S4P3/W2).




---




## 10. R25 — workflow plan promotion / publisher




**Contract/gap.** `_cmd_workflow` (`:1742`), `_require_managed_publisher`
(`:2288`), `_promote_validated_plan` (`:2304`), admission loop. Validated
candidate-to-PLAN promotion must be delegated to `BoundPlanPublisher`; missing
authority refuses repair. The managed plan promotion is not fully wired; Q114-A
covers indeterminate candidate PUBLISH; Q90/CT108 covers nested handoff.




**Source→caller map.** `cli._cmd_workflow` → `workflow_controller` admission →
`_require_managed_publisher` → `_promote_validated_plan` →
`BoundPlanPublisher`/`ManagedExecution.publish_plan`.




**Existing tests/nodeids.** `tests/test_verify_gate_live.py` CT94 cases
(component/local); `tests/test_execution_composition.py` (local UDS composition);
`tests/test_plan_candidate_retention.py` (component). No production `fa workflow`
managed-publisher negative oracle.




**Minimal files/seams.** `src/fa/cli.py::_cmd_workflow`,
`src/fa/inner_loop/workflow_controller.py::_require_managed_publisher`,
`_promote_validated_plan`, `src/fa/execution/composition.py::BoundPlanPublisher`.




**Proposed tests/mutations.** Production `fa workflow` with a managed publisher;
determinate pre-commit refusal leaves canonical PLAN unchanged and never falls
back to host write; uncertain outcome is one-shot. Mutation: remove the managed
publisher; remove the fail-closed refusal.




**Q#.** No new Q#; R25 remains OPEN (managed plan promotion is S5P2/W2; Q114/Q90
provide the policy).




---




## 11. R26 — nested workflow / child run context




**Contract/gap.** `_make_workflow_ctx_provider` (`:2088`), `_build_run_tool_registry`
(`:2230`), `workflow_tool._child_run_context` (`:405`), `SessionManager.begin_run`
(`:590`). The child gets a run-log ID but shares the session workspace; the parent
writer must be suspended/pinned before handoff; the child cannot access parent
authority; backend denial creates no child project write. The nested workflow is
not fully wired; Q90/CT108 covers the handoff.




**Source→caller map.** `fa run --role chat` → `invoke_workflow` →
`_make_workflow_ctx_provider` → `_child_run_context` → `SessionManager.begin_run`
→ child `run_workflow` → `_cmd_run` stages.




**Existing tests/nodeids.** `tests/test_invoke_workflow_tool.py` (tool handler;
component); `tests/test_handoff_payload.py` (handoff payload; component). No
production nested-workflow negative oracle.




**Minimal files/seams.** `src/fa/cli.py::_make_workflow_ctx_provider`,
`_build_run_tool_registry`, `src/fa/inner_loop/tools/workflow_tool.py::_child_run_context`,
`_begin_managed_child`, `_return_managed_child_to_parent`,
`src/fa/session/manager.py::begin_run`.




**Proposed tests/mutations.** Production `fa run --role chat` with
`invoke_workflow` and a real local supervisor; assert parent writer
suspended/pinned, child cannot access parent authority, backend denial creates no
child project write. Mutation: remove the parent suspend/HANDOFF; remove the
child namespace binding.




**Q#.** No new Q#; R26 remains OPEN (nested workflow is S5P2/W2; Q90/CT108
provide the policy).




---




## 12. R27 — direct chat managed workspace / one writer




**Contract/gap.** `_cmd_run` (`:2713`) → `_run_cli_stage` (`:1682`) →
`_drive_stage_with_managed_workspace` (`:1582`); reuse or compose one writer, open
`WRITE/PROJECT`, bind `ClientWorkspacePort` + `ManagedBashExecutor`, settle then
release only a directly owned writer. The local positive/negative CLI oracles
pass; R27 remains OPEN under broader S4P1 row closure and final deployed-host
acceptance.




**Source→caller map.** `fa run --role chat` → `_cmd_run` → `_run_cli_stage` →
`_drive_stage_with_managed_workspace` → `ManagedBashExecutor` → supervisor EXEC.




**Existing tests/nodeids.** `tests/test_execution_composition.py::test_direct_chat_keeps_canonical_tree_unchanged_until_stage_publication`
(production CLI with real local UDS; provider I/O mocked); `tests/test_managed_mutation_metadata.py`,
`tests/test_managed_mutation_guard.py`, `tests/test_managed_registry_binding.py`
(component/local). This is the strongest local evidence among the audited rows.




**Minimal files/seams.** `src/fa/cli.py::_drive_stage_with_managed_workspace`,
`_run_cli_stage`, `_cmd_run`; `src/fa/execution/composition.py::ManagedExecution`.




**Proposed tests/mutations.** Already largely covered by the local CLI oracle;
the remaining gap is the broader S4P1 row closure and final deployed-host
acceptance. Mutation: remove the one-writer binding; remove the settle/release.




**Q#.** No new Q#; R27 remains OPEN under the broader row closure and final
deployed-host acceptance.




---




## 13. R28 — host bootstrap / operator TCB




**Contract/gap.** `scripts/bootstrap/host_bootstrap.py::_run` (`:24`), `main`
(`:95`); direct production caller `justfile:112` (`agent-bootstrap`); no Python
production caller. Arbitrary current host Bash is not shown to exclude this
script. The named `test_no_model_tool_can_reach_the_host_bootstrap` is planned and
**absent**; it requires W1 managed Bash cutover.




**Source→caller map.** `justfile:112` → `host_bootstrap.py` → `scripts/fa`
wrapper; operator/Compose path, not model tool.




**Existing tests/nodeids.** `tests/test_workspace_bootstrap_aliases.py::test_host_bootstrap_delegates_current_just_to_wrapper_and_emits_ready`,
`::test_host_bootstrap_missing_uv_is_stable_and_does_not_call_wrapper`
(component/script-level).




**Minimal files/seams.** `scripts/bootstrap/host_bootstrap.py`, `justfile`,
`src/fa/cli.py` managed Bash cutover.




**Proposed tests/mutations.** Production managed Bash with a model tool that
tries to reach `host_bootstrap`; assert no model tool can reach it. Mutation:
remove the host bootstrap alias; remove the managed Bash cutover.




**Q#.** No new Q#; R28 remains OPEN pending W1 managed Bash cutover.




---




## 14. Cross-cutting findings




1. **The inventory's named nodeids for R15–R28 are stale.** Only
  `test_a_managed_search_runs_no_host_git_subprocess` was found; the other named
  nodeids are absent. The actual test names are different. The inventory must be
  refreshed with current nodeids before any row closure.
2. **Most audited tests are component/local, not production-caller.** The
  production-caller evidence exists for R10/R11/R13/R27 and the actual CLI
  tests; R14–R26, R28 are component/local or absent. The W0 strict row closure
  requires a production-caller negative oracle for each row; the current tests
  do not satisfy that for most audited rows.
3. **The managed child (R13) is locally closed; R23 is legacy.** The managed child
  is `inner_loop/tools/managed_subagent.py`; R23 is the legacy worktree manager.
  R23 should be retired as legacy or kept as a historical candidate; it is not
  the managed child.
4. **R21 is dormant/dead code.** No production caller; it can be retired or kept
  as a historical candidate; it cannot be closed as a managed route without a
  real caller.
5. **R12/Q125 is unresolved.** The optional runtime server has no production
  caller; the absence oracle is a narrowing; see the Q125 audit.
6. **No new Q# is required for R01, R03, R14–R22, R24–R28.** The unresolved
  dependencies are already tracked in Q113/Q125/Q119/Q120/Q114/Q90. **Q126 is
  proposed for the R23 legacy worktree disposition** (retire vs keep as a
  historical candidate).




## 15. Proposed Q126




**Q126 — What is the disposition of the legacy R23 worktree row?**




**Status: OPEN — R23 is a legacy host-Git row; the managed child is R13.** The
managed child (`inner_loop/tools/managed_subagent.py`) does not use the worktree
manager. R23 remains OPEN as a separate S4P1 row.




**Options.**




A. **Retire R23 as legacy.** Record that the managed child is R13; R23 is a
historical host-worktree candidate, not a managed route; close/retire the row
with a disposition note. No host-Git oracle is required for the managed path.




B. **Keep R23 as a historical candidate.** Keep the row OPEN; require a separate
host-Git negative oracle if the operator wants to preserve the legacy worktree
path. It is not the managed child and does not block R13.




**Recommendation (not a decision).** A. The managed child is R13; R23 is legacy;
retiring it avoids a false dependency and a host-Git oracle for a path the managed
product does not use. If the operator wants to preserve the legacy worktree path,
B is the safer historical record.




**Acceptance boundary.** Q126 does not close R23, R13, W0, or W1. No runtime/test
code is changed by this audit.




## 16. Verified 2026-11-04 — step-by-step re-check




The findings above were re-checked against the current source at `0f15a12`:




- **R01:** `pyproject.toml:98` `fa = "fa.cli:main"`; `Dockerfile.fa:97–98`
 `controller_entry`; `SessionManager.resolve_active_session_for_workspace:220`.
 Wrapper→installed-controller composition absent.
- **R03:** `scripts/bootstrap/workspace.py:16–17` `sys.path.insert(0, str(source))`;
 `justfile:112` `agent-bootstrap`. Managed-cell bootstrap absent.
- **R14:** `tools/__init.py:175,230,285,337`; `test_a_managed_registry_ships_no_host_git_tools`
 component (fake port); named `test_profile_construction_failure_registers_no_project_command`
 absent.
- **R15:** `write_file.py:102`; `edit_file.py:160`; `tests/test_managed_workspace.py`
 absent; named `test_file_handlers_write_through_the_view_only` absent.
- **R16:** `workflow_controller._git_output:848`; no `_git_output` test; named
 `test_stage_diff_never_runs_controller_git` absent.
- **R17:** `pair_tools._run_git:28`; `test_subagent_termination_wiring.py` imports
 `build_send_ctrl_c_tool` but not `_run_git`; named
 `test_pair_tools_use_the_writer_view_and_never_the_canonical_index` absent.
- **R18:** `mutation_guard._base_commit:60`; `test_s5_blackboard_contract.py` has
 `test_same_base_commit_conflict_denied` (blackboard conflict), not `_base_commit`;
 named `test_denied_base_commit_lookup_blocks_admission` absent.
- **R19:** `intent_guard._default_git_runner:272`; no `_default_git_runner` test;
 named `test_intent_git_failure_never_bypasses_view_admission` absent.
- **R20:** `_safe_walk._git_ls_files:452`;
 `test_a_managed_search_runs_no_host_git_subprocess:389` component (fake port);
 production managed search absent.
- **R21:** `_common.git_ls_files:22`; no production caller; dormant/dead code.
- **R22:** `pr_intent._run_git:817`; `hooks/_util.resolve_hooks_dir:91`; no
 `test_pr_prepare_reads_only_a_managed_revision`; named test absent.
- **R23:** `worktree_manager.create_subagent_workspace:196`; no
 `test_subagent_isolation_never_touches_the_canonical_root`; named test absent;
 legacy worktree, managed child is R13.
- **R24:** `slice_verification._run_one:330`; no
 `test_kill_proof_requires_a_fresh_operation_and_source_binding`; named test absent.
- **R25:** `cli._cmd_workflow:1742`; `workflow_controller._require_managed_publisher:2288`;
 `_promote_validated_plan:2304`; component/local tests; production `fa workflow`
 managed-publisher negative oracle absent.
- **R26:** `cli._make_workflow_ctx_provider:2088`; `workflow_tool._child_run_context:405`;
 `SessionManager.begin_run:590`; component tests; production nested-workflow
 negative oracle absent.
- **R27:** `cli._cmd_run:2713`; `_run_cli_stage:1682`;
 `_drive_stage_with_managed_workspace:1582`;
 `test_direct_chat_keeps_canonical_tree_unchanged_until_stage_publication`
 production CLI + real local UDS; broader row closure + final deployed-host
 acceptance.
- **R28:** `host_bootstrap._run:24`; `main:95`; `justfile:112`; no
 `test_no_model_tool_can_reach_the_host_bootstrap`; named test absent; depends on
 W1 managed Bash cutover.




**Conclusion.** The audit findings are confirmed. The named nodeids in the
inventory are stale; the actual test names are in the refresh table. Most audited
tests are component/local, not production-caller. R21 is dormant/dead code; R23 is
legacy (managed child is R13); R12/Q125 is unresolved. Q126 is proposed for R23.
No new Q# is required for the other rows. R01, R03, R14–R28 remain OPEN; W0 remains
OPEN.