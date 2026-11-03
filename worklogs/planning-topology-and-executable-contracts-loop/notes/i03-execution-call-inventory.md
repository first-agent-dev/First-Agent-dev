# I03 execution call inventory — source-grounded initial version

Date: 2026-10-15; E230 refresh 2026-10-16; **E285 coverage baseline 2026-10-23 at `969fa06`** (coverage
re-scanned, every `src/fa` process/import route classified; see [§E285](#e285-refresh-2026-10-23--every-srcfa-processimport-route-classified-at-969fa06)
below the historical tables); **E414 R26**; **E423–E424 R02 refresh**; and **E425–E426 deployment-boundary reconciliation; E427–E428 R01 help fail-closed refresh, E429/Q119 workspace-route blocker, E430 host-help argument-scan closure, and E431 Q119 target-contract audit 2026-11-03** (addenda below). The initial
d910 line table below is historical; refreshed exact symbol ranges follow it. **State: OPEN — E285 remains the
frozen coverage baseline; R02 and R20–R28 have targeted source refreshes, and no S4P1 row is closed.** E402–E404
record local readiness/writer and publisher-caller evidence; E406/E407 record R25 determinate/uncertain PUBLISH
findings under Q114-A; E414 corrects the R26 caller trace; E423–E424 update R02's managed auto-run path and
local CLI proof; E425–E426 clarify that W3's approved `fa update` builds/starts the candidate image as a
deployment prerequisite, while W4 alone owns live I01–I03 acceptance. This deployment prerequisite closes
no inventory row and supplies no live negative-oracle result. The E285 scan accounts for 28 launcher/dynamic-import call sites in 16 files, each mapped to one row. W0's
Q113 exit is every row's observed local negative oracle; host/deployed acceptance remains a separate W4 gate.
The inventory review itself does not change runtime source. E402 separately records a narrow runtime fail-closed guard change and its tests; this note remains a static route inventory and no row is thereby closed. Static search is evidence of candidates, not a
proof that a route is reachable or safe. 'Read-only' and fixed Git argv do not exempt project Git.

| Actual producer / source lines | Inspected caller/dependency | Required route / concrete negative oracle (future) |
| --- | --- | --- |
| `scripts/fa:36–45,58–82,84–182` | `.active` supplies Compose `-w` for ordinary product commands. All wrapper help forms fail closed. Ordinary product dispatch still runs `first-agent fa` (`pyproject.toml`: `fa=fa.cli:main`), not `/opt/fa-venv/bin/python -I -m fa.controller_entry`. | Help has no project/backend effect until the isolated help seam exists. The remaining wrapper route must use the installed controller from a trusted CWD and carry project selection explicitly; poisoned CWD/PYTHONPATH must not alter controller imports. |
| `scripts/fa-entrypoint.sh:153–171,231–248,266–273` | configure/provision/readiness before auto-run; command override | Isolated controller + provisioning cell; no project command override in controller; backend unavailable executes no hook/import |
| `scripts/bootstrap/workspace.py:13–17` | stdlib wrapper prepends checked-out src before readiness import | Run project-side wrapper inside provisioning cell or use installed trusted dispatcher; poisoned checkout cannot execute on controller |
| `src/fa/session/manager.py:211–239,292–295` | create-session provisions Git/source and invokes workspace_preparer | Supervisor-owned provisioning view/publication; absent backend means no clone/checkout/hook on controller, existing reuse does not reconfigure canonical root |
| `src/fa/session/workspace.py:170–204,290–360,394–525` | manager provision_git_workspace; entrypoint configure-existing | Project Git operations in provisioning cell; approved source/network policy, no controller deploy/proxy credentials copied to cell |
| `src/fa/cli.py:147–156` | _prepare_managed_workspace → ensure_workspace_ready | Managed provisioning operation, no fail-open warning followed by execution; absent backend/unknown receipt blocks |
| `src/fa/workspace_bootstrap.py:263–289` | readiness _run_process executes project sync/hooks/import checks | Managed noninteractive provisioning; spawned project script cannot reach controller sentinel/control sockets; missing result never READY |
| `src/fa/cli.py:1931–1959` | _cmd_run builds local PtyPool; failure returns None | Managed executor required; failed initialization cannot select host subprocess |
| `src/fa/inner_loop/tools/run_bash.py:93–149,152–216,219–247,329–347` | actual fs_run_bash handler/context/executor/fallback | Cell PTY only, operation reservation; injected timeout/disconnect executes side-effect command at most once; no executor yields unavailable |
| `src/fa/runtime/pty_pool.py:140–167,580–609,625–641` | tmux/pexpect and fallback setup; PTY close cleanup | Same cell namespaces/cgroup and private tmp/socket; double-fork/setsid survives shell close but prevents terminal seal until confirmed stopped |
| `src/fa/runtime/server.py:62–81`; `runtime/bash_executor.py:98–118` | optional HTTP PTY server/client projection | Optional cell-internal only; response preserves timed_out/identity or rejects as unknown; HTTP health/close cannot certify descendant barrier |
| `src/fa/inner_loop/subagent_runner.py:293–358` | run_stateless uses subprocess and adds X_FA_PROXY_TOKEN | Managed project-command cell with no proxy credential; unsupported credential-dependent command blocks. Coder-profile absence does not close chat route |
| `src/fa/inner_loop/tools/__init__.py:281–300` | chat registry's exception fallback still registers run_bash | Fallback registry cannot bypass managed capability; profile-construction failure executes zero project commands, never host shell |
| `src/fa/inner_loop/tools/write_file.py:15–58`; `edit_file.py:99–156` | actual role registry handlers write local paths | Supervisor rooted shared-view IO; file↔PTY edits visible, active-plan/control/symlink/hard-link/parent-rename export denied |
| `src/fa/inner_loop/workflow_controller.py:774–803,909–911` | eval Git diff/status context | Supervised private Git or sealed filesystem diff; no controller project Git; unavailable advisory diff must not erase verifier evidence |
| `src/fa/inner_loop/tools/pair_tools.py:28–36,39–310` | checkpoint/undo/diff tools | Same writer/view or read pin; busy workspace denies another actor's mutating Git, no canonical index writes |
| `src/fa/inner_loop/tools/run_bash.py:56–65,166,273` | transaction write-set Git status, including after command | Supervised private metadata or supervisor computed filesystem diff; no hidden post-command controller Git |
| `src/fa/inner_loop/tools/mutation_guard.py:51–69,115` | _base_commit for version-dependency stamp | Use protected revision identity or managed metadata, not canonical Git; denied lookup cannot turn mandatory mutation admission advisory |
| `src/fa/inner_loop/hooks/intent_guard.py:272–280,304–316` | BEFORE_TOOL_EXEC default staged-diff runner | Supervised metadata; preserve intent policy separately, but its Git-unavailable allow must never bypass mandatory execution/view admission |
| `src/fa/memory/_safe_walk.py:130–167,267–268`; `memory/search_index.py:1086` | file enumeration used by memory/search indexing | Approved snapshot manifest/data walk or supervised metadata; read-only search must not run project Git on controller |
| `src/fa/inner_loop/tools/_common.py:22–53` | exported git_ls_files; no call found in bounded tool/memory search | Confirm reachability with full audit; delete if genuinely dead, otherwise managed metadata. Do not build a new adapter solely for dead code |
| `src/fa/hygiene/pr_intent.py:817–829`; `hygiene/hooks/_util.py:91–118` | project hook CLI and readiness hook-path resolution | Project hook/Git runs inside cell. Pure path parser is data IO; do not execute canonical hooks on host |
| `src/fa/workspace/worktree_manager.py:166–264` | isolated-worktree compatibility implementation | Current workflow stages must not activate it as a host escape; future subagent enablement requires inherited boundary. No parallel worktree platform in I03 |
| `src/fa/inner_loop/slice_verification.py:332–358,416–453,975,1410–1429` | command runner; JUnit, provenance import probe and mutated pytest | Managed operation bound to pinned source/PlanRef/profile, private scratch/report; stale/skip/collection/launch/timeout/identity mismatch ERROR, not kill |
| `src/fa/inner_loop/workflow_controller.py:1057–1081,1093–1104,1161–1165` | baseline/verifier and eval-plan reread | I02 immutable snapshot/T0 plus managed revision receipt; no stale eval IDs or success after integrity/storage error in either mode |
| `src/fa/inner_loop/tools/workflow_tool.py:463–484`; `cli.py:1687–1706` | nested controller receives parent's context and no PlanRef | Proper child begin_run/namespace and approved acquisition; parent file/PTY writers suspended/terminal before handing over same workspace owner |
| `scripts/bootstrap/host_bootstrap.py:23–40`; operator update/deploy scripts | developer/administrator host preparation, not model tool execution | Explicit TCB maintenance only, quiescent workspace; no model-accessible backdoor. Inspect transitive command list before declaring outside product target |

## E285 refresh (2026-10-23) — every `src/fa` process/import route classified at `969fa06`

**Why the refresh.** E284 (A1) closed the checkpoint gap and left A4 next in the plan's dependency order, so this is
the inventory the cutover must close. Its E230-era anchors were 7 weeks stale, several had drifted
(`session/manager.begin_run` moved `441–478` → `537–574`; `cli._cmd_run` is `2166–2515`, not the `1931–1959`
carried in the older note), and the scan behind it was not re-run, so "no newly found route is silently exempted"
could not be checked.

**Method (bounded, repeatable, not a repo gate).** An AST scan over `src/fa/**/*.py` for: module-qualified **and**
from-imported `subprocess` / `pty` / `pexpect` / `libtmux` / `multiprocessing` / `asyncio.subprocess` / `importlib` /
`runpy` calls; `os.system|popen|fork|forkpty|exec*|spawn*|posix_spawn*`; and `shutil.which` capability gates. The
E230 note's warning was tested rather than trusted: the from-import and pexpect/libtmux aliases *do* exist and a
name-only scan misses them. Result at `969fa06`: **22 files with findings, 52 call sites — 28 launcher/import sites in
16 files, 21 in-process `shutil` cleanup calls, 3 `which` gates.** Every one is classified below or in the
"classified out" list; there are no unclassified findings.

**Boundaries.** "host" = the controller PID running an unsandboxed project command today; "cell" = the managed
execution cell; "TCB" = operator/developer host preparation that is not model tool execution. No row is managed yet:
every project-facing route below still runs on the host or degrades to it, which is A5's subject. **Profile and view
are therefore "none" by construction on every project-facing row** — a host subprocess has no execution profile and no
view — and that absence is the gap the column records, not an unrecorded field. The two rows that already run inside
a cell (R09's cell half, R12) name the profile they use (`interactive` / one-shot) and the view they hold (none: a
cell runs against its own sandbox, not a workspace view).

### Process / import routes

| # | Route (producer @ `969fa06`) | Reachable from | Boundary today | Existing evidence (verified present) | Named negative oracle (planned unless marked EXISTING) |
| --- | --- | --- | --- | --- | --- |
| R01 | `scripts/fa:36–45` reads `.active` for Compose `-w`; `:58–82` rejects wrapper help; `:89–181` dispatches host commands and ordinary product commands. `pyproject.toml:97–100` maps `fa` to `fa.cli:main`; isolated `controller_entry` is only build-smoke-tested in `Dockerfile.fa:97–98`. | operator shell | Host infrastructure commands remain TCB host; all wrapper help is disabled. Ordinary product dispatch still does not use the required isolated controller entry. | `tests/test_deploy_scripts.py::test_fa_wrapper_uses_arrays_for_compose_and_flags`; separate direct installed-CLI proof: `tests/test_controller_installed.py::test_actual_installed_cli_help_ignores_project_cwd_pythonpath_and_venv` | `tests/test_deploy_scripts.py::test_fa_wrapper_help_fails_closed_without_project_import`; `::test_fa_wrapper_host_command_help_fails_closed_before_dispatch`; `::test_fa_wrapper_host_help_flags_at_later_positions_fail_closed_before_dispatch`; `::test_fa_wrapper_product_help_fails_closed_without_project_import`; `::test_fa_wrapper_nonhelp_product_command_still_delegates_to_container`. Immediate and later-position host help switches refuse before dispatch; product task data and normal routes remain unchanged. The target requires trusted-CWD controller startup plus explicit project selection; Q119's recommended command-aware adapter is acceptable only with full command/workspace coverage, not permanent refusal of required product routes. The wrapper→installed-controller composition and authorized active-workspace semantics remain OPEN pending **Q119**. |
| R02 | `scripts/fa-entrypoint.sh:200–209` selects managed auto-run only for self-repo/no-`FA_WORKSPACE` startup with no command override and truthy auto-run; `:263–265` clears inherited `PYTHONPATH`; `:280–305` calls manager provision without `--workspace` and publishes `.active` only on success; legacy override/standby stays at `:210–255,308–312`. `src/fa/session/manager.py::provision_entrypoint_session:460–477` owns the default root; `_main:596–639` binds the configured provisioner/readiness. | operator/container entry | managed provision/readiness for this auto-run branch; TCB-host legacy adapter remains for explicit override/standby | `tests/test_fa_entrypoint.py::test_managed_auto_run_provisions_before_publication_and_keeps_controller_import_pinned`; `tests/test_session_lifecycle.py::test_entrypoint_manager_uses_injected_provisioner_for_success` | local manager refusal: `tests/test_session_lifecycle.py::test_entrypoint_manager_refuses_missing_managed_provisioner_before_state_changes`; CLI-input refusal: `::test_entrypoint_manager_cli_rejects_missing_required_arguments_before_backend_lookup`; shell failure ordering: `tests/test_fa_entrypoint.py::test_entrypoint_auto_run_refuses_after_managed_readiness_failure_before_active_or_run` (manager is stubbed, so this is not the real backend-unavailable composition). Full deployed-entrypoint/no-backend oracle remains planned/absent; live acceptance is not run. |
| R03 | `scripts/bootstrap/workspace.py:13–17` prepends the checked-out `src` before readiness import | bootstrap wrapper | TCB host | `tests/test_workspace_bootstrap_aliases.py::test_just_bootstrap_aliases_converge_and_doctor_is_read_only` | same as R01 (poisoned checkout/PYTHONPATH) |
| R04 | `session/manager.py::_new_session:335–426` → `_provision_workspace:230–262` (callers `:377`); `begin_run:537–574` reserves a run, spawns nothing | explicit, chat, nested | host | `tests/test_session_workspace_provisioning.py` | `tests/test_managed_workspace.py::test_a_new_run_provisions_through_the_supervisor_and_never_clones_on_the_host` |
| R05 | `session/workspace.py::provision_git_workspace:290–360`, `configure_existing_workspace:394–524`, `_run_git:170–204` (`subprocess.run`@182) | R04 | host (project Git) | `tests/test_session_workspace_provisioning.py` | same as R04 + `…::test_missing_backend_creates_no_clone_and_no_hook` |
| R06 | `cli.py::_prepare_managed_workspace:150–159` (warns, then continues) | explicit `_cmd_run` prologue | host, fail-open | `tests/test_cli.py::test_prepare_managed_workspace_warns_only_for_degraded_state` | `tests/test_managed_workspace.py::test_degraded_readiness_blocks_instead_of_warning` |
| R07 | `workspace_bootstrap.py::_run_process:263–290` (`subprocess.run`@274), `_uv_executable:293–306` (`which`@294); callers `:297,332,424,587,595` | readiness | host (project sync/hooks/import probes) | `tests/test_workspace_bootstrap.py::test_process_runner_uses_bounded_captured_noninteractive_environment` | `…::test_readiness_probes_run_in_the_provisioning_cell` |
| R08 | `cli.py::_build_pty_pool:1923–1951` → `_PtyPool(...)`@1948; caller `_cmd_run:2166–2515` | explicit | host | `tests/test_cli.py` | `tests/test_managed_workspace.py::test_backend_down_run_builds_no_pty_pool` |
| R09 | `runtime/pty_pool.py::__init__:116–233` (`pexpect.spawn`@156) and `:562–622` (`shutil.which("tmux")`@582, `libtmux.Server`@589/599) | R08, `inner_loop/state.py:557`, `execution/cell_worker.py:243` (cell), `runtime/server.py:53` | host PTY today; already correct inside the cell | `tests/test_execution_cell_worker.py::test_noninteractive_one_shot_accepts_null_session_and_returns_no_reusable_session` (cell half) | `…::test_no_host_tmux_or_pexpect_when_the_backend_is_down` |
| R10 | `inner_loop/tools/run_bash.py::build_run_bash_tool:321–390` (`fs_run_bash`@350) → `_run_pty_executor:152–216`; write-set Git `_get_write_set_from_git_status:56–83` (`subprocess.run`@59) | explicit, chat, coder, nested | host shell/PTY | `tests/test_chat_escalation_gate.py`, `tests/test_coder_loop.py` | `tests/test_execution_project_tools.py::test_bash_runs_only_in_a_cell_and_reserves_one_operation` |
| R11 | `…::_run_subprocess_fallback:219–318` (`subprocess.run`@238) — the stateless fallback | R10 when no PTY | host, silent fail-open | `tests/test_venv_path_wiring.py::test_subprocess_fallback_resolves_venv_tools_live` | `…::test_no_executor_yields_unavailable_not_a_host_shell` |
| R12 | `runtime/server.py:29–30` optional `importlib` (FastAPI), `runtime/bash_executor.py:98–118` HTTP projection | optional runtime server | cell-internal / optional | `tests/test_runtime_server_open_stand.py::test_server_imports_without_fastapi` | `…::test_http_health_never_certifies_terminality` |
| R13 | `inner_loop/subagent_runner.py::run_stateless:293–410` (`subprocess.run`@343), caller `tools/spawn_subagent.py:222` | explicit, chat | host (adds `X_FA_PROXY_TOKEN`) | `tests/test_s6_subagent_fidelity.py` | `…::test_subagent_commands_carry_no_proxy_credential` |
| R14 | `inner_loop/tools/__init__.py::build_baseline_registry:169`, `build_planner_registry:213`, `build_eval_registry:251`, `build_chat_registry:287` — exception fallback still registers bash | all three | host registry | `tests/test_execution_tool_index.py::test_a_managed_registry_ships_no_host_git_tools` **EXISTING** | `…::test_profile_construction_failure_registers_no_project_command` |
| R15 | `inner_loop/tools/write_file.py:70–110,113–150`; `edit_file.py:99–193` | all three | host filesystem | `tests/test_execution_tool_port.py::test_tools_built_with_the_port_read_write_and_edit_through_it` (port half) | `tests/test_managed_workspace.py::test_file_handlers_write_through_the_view_only` |
| R16 | `workflow_controller.py::_git_output:835–864` (aliases `subprocess.run` to a local callable) | stage loop | host project Git | `tests/test_slice_verification_runner.py` | `…::test_stage_diff_never_runs_controller_git` |
| R17 | `inner_loop/tools/pair_tools.py::_run_git:28–36` (`subprocess.run`@30), callers `:100,116,172,180` | chat/coder | host project Git | `tests/test_subagent_termination_wiring.py` (wiring only) | `…::test_pair_tools_use_the_writer_view_and_never_the_canonical_index` |
| R18 | `inner_loop/tools/mutation_guard.py::_base_commit:51–69` (`subprocess.run`@58), caller `:115` | coder | host project Git | `tests/test_s5_blackboard_contract.py::test_same_base_commit_conflict_denied` | `…::test_denied_base_commit_lookup_blocks_admission` |
| R19 | `inner_loop/hooks/intent_guard.py::_default_git_runner:272–281` (`subprocess.run`@273) | every gated tool call | host project Git | `tests/test_intent_guard.py` | `…::test_intent_git_failure_never_bypasses_view_admission` |
| R20 | `memory/_safe_walk.py::_git_ls_files:130–175` (`which`@146, `subprocess.run`@151) | memory/search indexing | host project Git | `tests/test_safe_walk.py` | `tests/test_execution_tool_index.py::test_a_managed_search_runs_no_host_git_subprocess` **EXISTING** |
| R21 | `inner_loop/tools/_common.py::git_ls_files:22–53` (`subprocess.run`@40) | memory/search | host project Git | `tests/test_tools_common.py` | same as R20 (EXISTING) |
| R22 | `hygiene/pr_intent.py::_run_git:817–829` (`subprocess.run`@822); `hygiene/hooks/_util.py::resolve_hooks_dir:91–120` (`subprocess.run`@102) | chat `pr_prepare`, readiness hook lookup | host project Git | `tests/test_pr_intent_snapshot.py` | `…::test_pr_prepare_reads_only_a_managed_revision` |
| R23 | `workspace/worktree_manager.py::create_subagent_workspace:196–248` (`subprocess.run`@211/218/231), `cleanup:251–270` (@253/264), `_resolve_base_branch:181–193`, `_is_branch_checked_out_elsewhere:165–179` | subagent spawn | host project Git | `tests/test_s5_isolation_boundary.py` | `…::test_subagent_isolation_never_touches_the_canonical_root` |
| R24 | `inner_loop/slice_verification.py::_run_one:330–357` (`subprocess.run`@334), `mutation_overlay:980–1004`, `_run_kill_check:1439–1537`, `capture_test_nodeids:539–581` | verify, kill-check, eval | host pytest | `tests/test_mutation_overlay.py`, `tests/test_verify_slice.py` | `tests/test_e2e_artifact_contract.py::test_kill_proof_requires_a_fresh_operation_and_source_binding` |
| R25 | `cli.py::_cmd_workflow:1496–1537`; `workflow_controller.py::_require_managed_publisher:2281–2294`, `_promote_validated_plan:2297–2328`, admission loop `:2586–2597` | explicit, nested | host workflow stages; validated candidate-to-PLAN promotion is delegated to `BoundPlanPublisher`; missing authority refuses repair | local controls: `tests/test_verify_gate_live.py` CT94 cases, `tests/test_execution_composition.py`; required managed-backend negative oracle: determinate pre-commit refusal leaves canonical PLAN unchanged and never falls back to host write; uncertain outcome is one-shot and requires Q114-A managed-path implementation (legacy `fa workflow` remains unchanged; do not assert old PLAN bytes after uncertainty) |
| R26 | `cli.py::_make_workflow_ctx_provider:1746–1827`, `_build_run_tool_registry:1879–1940`; `workflow_tool.py::_child_run_context:387–403`, handler `:469–534`; `SessionManager.begin_run:537–574` | live chat → nested workflow | child gets a run-log ID but shares the session workspace; direct `run_workflow` call has no child `PlanRef`/`plan_publisher`; coder-containing requests refuse before child allocation | local controls: `tests/test_invoke_workflow_tool.py`, `tests/test_handoff_payload.py`; required negative oracle: parent writer is suspended/pinned before handoff, child cannot access parent authority, and backend denial creates no child project write |
| R27 | `cli.py::_cmd_run:2483` → `_run_cli_stage:1505` → `_drive_stage_with_managed_workspace:1422`; reuse or compose one writer, open `WRITE/PROJECT`, bind `ClientWorkspacePort` + `ManagedBashExecutor`, settle then release only a directly owned writer; callback builds the view-bound role registry before `drive_session` | explicit, chat, workflow stage | local UDS supervisor; managed IO/Bash are bound; Blackboard stamps use admitted `base_revision` plus complete view-read `knowledge/llms.txt`; managed `LearningObserver` is omitted to prevent host-path writes | `tests/test_execution_composition.py::test_direct_chat_keeps_canonical_tree_unchanged_until_stage_publication` (direct acquisition and existing-owner reuse; project-file snapshot unchanged while live, then write appears after publication) plus `tests/test_managed_mutation_metadata.py`, `tests/test_managed_mutation_guard.py`, `tests/test_managed_registry_binding.py` | Local positive and negative CLI oracles pass; R27 remains OPEN under broader S4P1 row closure and final deployed-host acceptance remains `NOT RUN`. |
| R28 | `host_bootstrap.py::_run:24–39`, `main:95–115`; direct production caller `justfile:113` (`agent-bootstrap`), no Python production caller | operator | TCB host; arbitrary current host Bash is not shown to exclude this script | `tests/test_workspace_bootstrap_aliases.py::test_host_bootstrap_delegates_current_just_to_wrapper_and_emits_ready`; `…::test_host_bootstrap_missing_uv_is_stable_and_does_not_call_wrapper` | `…::test_no_model_tool_can_reach_the_host_bootstrap` (planned, absent; requires W1 managed Bash cutover) |

### R20 working-tree refresh (2026-11-01; remains OPEN)

- Current producer: `memory/_safe_walk.py::_git_ls_files:452–497`; the no-`.git` short circuit is at
  `:461–467`, before `shutil.which` or `subprocess.run`. `iter_searchable_files:596–655` calls this helper
  before its fallback walk.
- Current readers/callers: `memory/search_index.py::_walk_and_index:489–527` and
  `_search_python_walk:1048–1140`; the structural-index path is `memory/structural_index.py::_build:390–430`.
  The helper entry is `execution/project_tools.py::_dispatch:33–50`; it builds `fs_search` at `:44–45`.
  No production EXEC/supervisor caller was established by this refresh.
- The existing `tests/test_execution_tool_index.py::test_a_managed_search_runs_no_host_git_subprocess`
  covers the `workspace_io` fail-closed route in `fs_search.py:1003–1018`; it does not exercise a successful
  cell-local helper search. Added `tests/test_execution_project_tools.py::test_cell_local_search_without_git_metadata_does_not_spawn_git`
  as a helper-level C3 local oracle (not C1 production-path proof): it dispatches through the real helper/registry against a temporary view without
  `.git`, requires the positive `chain.py` hit, records `subprocess.run`, and requires zero invocations.
  `test_real_search_and_reach_stay_on_each_distinct_view` remains a separate positive helper-route check.
  On CPython 3.13.16, the focused bank (`test_execution_project_tools.py`, the named managed refusal test, and
  `test_safe_walk.py`) passed **56 tests with 2 existing Q106 xfails**. Ruff, the 324-file doc-link checker,
  and `git diff --check` passed. Disabling the no-`.git` producer guard killed the positive-hit test; removing
  the helper's `fs_search` registry binding killed it with `project_tool_failed`; both mutants were restored.
- This is local helper evidence only, not a managed backend, supervisor/EXEC, or live-host result. It also
  does **not** close Q109: `fs_search` is still not wired to `strict_rooted_reads`, while `fs_reach` is.

### R21 working-tree refresh (2026-11-01; remains OPEN)

- Current producer: `inner_loop/tools/_common.py::git_ls_files:22–53` uses bare `git` in `subprocess.run`.
  A source search of `src/fa` finds only the definition, its doc/example and `__all__`; no production caller
  remains. Current `fs_search` uses its separate `_safe_walk._git_ls_files` producer (R20), not this helper.
- `tests/test_tools_common.py::TestGitLsFiles` directly invokes/tests this helper, including real temporary Git
  repos. The managed-search refusal test names `_safe_walk.subprocess.run`; it does not cover this unused helper.
  The complete `tests/test_tools_common.py` bank passed **31 tests** on CPython 3.13.16 (exit 0).
- Current disposition is **dormant / no product edge established**, not a claim that a managed path is safe.
  Keep the historical R21 candidate visible; do not delete/retire it as part of R20/Q109. It cannot be closed
  as a managed route without a real caller and the required managed-backend oracle.

### R22 working-tree refresh (2026-11-01; remains OPEN)

- `pr_intent.py::_run_git:817–829` is called by `_cli_prepare:909–910` and by `_cli_validate:946–984`
  (only after generated-message/header gates); `main:997–1008` routes to them. Installed
  `hygiene/hooks/prepare-commit-msg` and `commit-msg` wrappers invoke `python -m fa.hygiene prepare/validate`
  after their bootstrap preamble. These are operator Git-hook paths, not a `pr_prepare` model-tool caller.
- The `pr_prepare` tool in `inner_loop/tools/prepare_pr.py:229–246` calls the pure validator with
  `staged=[]`; comments assign staged citation resolution to the later commit-msg hook. This route does not
  reach `_run_git`. The earlier planned nodeid
  `tests/test_pr_intent_snapshot.py::test_pr_prepare_reads_only_a_managed_revision` is **not present**.
- `_util.resolve_hooks_dir:91–120` is called by hooks `install_hooks:102–114` and `check_hooks:45–46`, and by
  `workspace_bootstrap._hooks_current:402–419` / `_assert_managed_hook_ownership:509–525`. It runs
  `git rev-parse --git-path hooks` then falls back to pure-Python Git-dir resolution. The hook shell preamble
  also invokes `git rev-parse --show-toplevel` before workspace bootstrap; current wrapper files are
  `src/fa/hygiene/hooks/prepare-commit-msg` and `commit-msg`.
- Local current-route evidence: `tests/test_prepare_pr.py`, `tests/test_pr_intent_snapshot.py`, the two named
  `test_resolve_hooks_dir_*` tests, and two named workspace-bootstrap tests passed **91 tests** on CPython
  3.13.16. This is local hook/tool coverage, not a managed-backend negative oracle or host acceptance. Keep
  R22 OPEN; preserve the `pr_prepare` versus hook-CLI distinction in any later oracle mapping.

### R23 working-tree refresh (2026-11-01; remains OPEN)

- `workspace/worktree_manager.py::IsolatedWorktreeManager.create_subagent_workspace:196–248` and
  `cleanup:251–270` contain the Git worktree subprocesses. Current `SessionState.__init__:521–548` may build
  the manager, but `SessionState.create_subagent_workspace:678–709` calls `ensure_subagent_artifact_root`
  directly; `cleanup_subagent_workspace:711–741` uses `shutil.rmtree`. `spawn_subagent.py:165–179` calls those
  state methods, not the manager's Git methods. The isolated mode is currently rejected at config load.
- No production caller of `IsolatedWorktreeManager.create_subagent_workspace`, its branch probes, or its
  cleanup was found. `tests/test_worktree_defensive.py` invokes the manager directly on temporary Git repos;
  `tests/test_s5_isolation_boundary.py::test_spawn_tool_uses_the_artifact_root_end_to_end` covers the
  different current artifact-root route. The old planned `test_subagent_isolation_never_touches_the_canonical_root`
  nodeid is absent.
- The two-file local bank passed **22 tests, 1 existing Q19 xfail** on CPython 3.13.16. The xfail preserves
  the known Q19 boundary: no OS-level writable-mount isolation. R23's Git producer is currently dormant/no
  product edge established; do not delete it or claim the current artifact-root test exercises it. Row stays OPEN.

### R24 working-tree refresh (2026-11-01; remains OPEN)

- Current live route: `workflow_controller._capture_nodeids_by_slice:343–365` calls
  `capture_test_nodeids:539–581`; `_run_stage` invokes it for T0 at `:415` and for post-coder T1 at `:1317`.
  After successful coder completion, `_run_stage:1319–1325` calls `verify_plan`, which launches plan/slice
  commands and `_run_kill_check`; `run_commands` reaches `_run_one:330–357` (`subprocess.run`). This remains
  a host pytest route, not a managed EXEC route. `mutation_overlay:980–1049` is source-copy/provenance setup;
  the actual test/kill commands still flow through `run_commands`.
- The table's planned nodeid
  `tests/test_e2e_artifact_contract.py::test_kill_proof_requires_a_fresh_operation_and_source_binding` is
  absent (pytest collection returned exit 4, no tests run). Current local evidence includes
  `tests/test_verify_slice.py::test_ct66_report_is_fresh_bound_and_cleaned_even_when_a_previous_report_is_replayed`
  and the `test_mutation_overlay.py` provenance/overlay bank; these do not replace a managed-backend oracle.
- With `.venv/bin` prepended to `PATH` so nested `python` subprocesses use CPython 3.13, the bank
  `tests/test_verify_slice.py tests/test_mutation_overlay.py tests/test_e2e_artifact_contract.py` passed
  **203 tests**. Without that PATH, two child-process tests used system Python 3.11 and failed; the corrected
  rerun is the reported proof. R24 remains OPEN; no backend or live result is inferred.

### R25 working-tree refresh (2026-11-01; remains OPEN)

- The historical table's claim that `_promote_validated_plan` still calls
  `plan_promotion.publish_plan_buffer` is stale: current `_promote_validated_plan:2297–2325` delegates to
  injected `CandidatePlanPublisher.publish_candidate`; `rg publish_plan_buffer src/fa` finds no occurrence.
  `workflow_controller.run_workflow` carries `plan_publisher` into `WorkflowContext`; the admission loop at
  `:2586` calls `_require_managed_publisher` before reserving/dispatching the planner attempt, then passes the
  port into `_run_admission_repair`, which publishes validated snapshot bytes through it.
- Current CLI caller: `cli._cmd_workflow:1487–1537` resolves lifecycle/workspace, builds
  `BoundPlanPublisher` from `managed_execution_for_run`, and passes it into `run_workflow`. An unmanaged run
  can still admit an already-valid plan; a repair without the port fails closed. This is a real composition
  edge but not deployed/managed-backend acceptance.
- The table's planned `test_the_plan_write_goes_through_the_authority_and_the_legacy_writer_is_gone` nodeid
  is absent. Current local controls are `test_ct94_missing_publisher_fails_closed_without_canonical_write`
  and `test_ct94_promotion_port_receives_only_the_pinned_destination`; composition bank also covers the
  supervisor/client binding. Those plus `tests/test_execution_composition.py` passed **20 tests with 1
  expected xfail** on CPython 3.13.16. The xfail
  `test_the_runs_own_second_publication_survives_a_host_side_write` explicitly retains the SLICE4 STEP2
  host-write gap. R25 stays OPEN; no row closure or live evidence.
- **E406 local negative composition oracle (2026-11-02).** `tests/test_execution_composition.py::test_workflow_root_keeps_plan_unchanged_when_local_authority_refuses_publication`
  enters the real `_cmd_workflow` CLI caller and local UDS `SupervisorService`, binds the real
  `BoundPlanPublisher`, runs the real `_promote_validated_plan`, and reaches the real candidate PUBLISH
  route. The test injects a deterministic `INPUT_POLICY` refusal at `WorkspaceAuthority.publish_candidate_plan`
  before the commit boundary; the valid candidate differs from the canonical PLAN. It asserts one refusal
  operation, controller `prepare-failed` (`replaced=False`), byte-identical canonical PLAN, and released
  workspace state. The `run_workflow` orchestration itself is a narrow test callback here, so this is not
  a full admission-loop or deployed-host result. It complements—not replaces—the client saga tests for
  determinate refusal/release and uncertain reply/view retention. Uncertain commit outcomes are deliberately
  not asserted to leave the old PLAN in place. R25 remains OPEN pending the full S4P1 nodeid/mutation proof,
  reviewed live-host acceptance and independent review.
- **E407 / Q114 uncertainty boundary (2026-11-02).** A real local-service probe showed that an uncertain CANDIDATE `Access.READ` view remains `STOPPING` with its private buffer, but `_has_unsettled_views` does not prevent owner release for READ views. The CLI then leaves the workspace `AVAILABLE`; the client has unwound without retaining the view handle, and the old view cannot publish once the binding is no longer `OWNED`. The exploration test was removed rather than encoding this unresolved lifecycle as acceptable. R25 uncertainty closure remains OPEN pending Q114-A managed-path implementation; legacy `fa workflow` stays unchanged, and old PLAN bytes must not be asserted after an uncertain PUBLISH.

### R26 working-tree refresh (2026-11-01; remains OPEN; trace-only)

- **Intent / allowed files / behavior delta:** refresh the stale R26 producer, caller, and oracle mapping only in
  this inventory and the ledger. No runtime source or test changed; there is no implementation behavior delta.
  The required future boundary remains an attested child execution context plus parent-writer suspension/pinning,
  not a weaker run-id-only namespace.
- **Production caller:** `cli._cmd_run:2448–2471` builds the live chat registry with
  `_make_workflow_ctx_provider:1746–1827`, binding the current `SessionContext`, parent `RunContext`, session DB,
  and workspace. `_build_run_tool_registry:1933–1939` registers `invoke_workflow` only for role `chat`.
- **Child allocation and stage route:** `workflow_tool._child_run_context:387–403` checks parent/session bindings,
  then `SessionManager.begin_run`; the resulting `RunContext` gets a distinct run log directory and ID but copies
  `session.workspace_path` unchanged (`session/manager.py:567–573`). The handler passes that child context to the
  injected `run_workflow` at `workflow_tool.py:513–534`, while forwarding the same session context/database and
  workspace. It does not pass a child `PlanRef`, `plan_path`, or `plan_publisher`; `run_workflow` defaults the
  latter two to `None`. Its stage callback is `_cmd_run`, not the `_cmd_workflow` composition that currently
  binds `BoundPlanPublisher`.
- **Current safeguards and failure semantics:** role registration is chat-only, the scheduler does not batch
  this workspace-permission tool with parallel calls, and the thread-local guard refuses recursive invocation.
  More importantly, `_requires_acquisition` rejects every coder-containing nested request at `:469–474` before
  child allocation and handoff (`test_acquisition_unavailable_before_child_or_handoff`). Parent/session mismatch
  also returns `workflow_context_error` before a child run is created. These controls do not establish a no-parent-
  writer guarantee for the planner/eval-only nested route; separate run-log IDs are not workspace namespaces.
- **Oracle refresh:** planned nodeid `test_nested_child_gets_an_attested_namespace_and_no_parent_writer` is absent.
  Existing session-authority tests exercise rejection of missing/mismatched parent context, while the ordinary
  successful handler fixture has no session authority and therefore is not a production child-allocation proof.
  `tests/test_handoff_payload.py` checks advisory context transfer, not isolation. The current pair
  `tests/test_invoke_workflow_tool.py tests/test_handoff_payload.py` passed **112 tests, exit 0** on CPython
  3.13.16. R26 remains OPEN: no attested child namespace, no parent-writer suspension proof, no managed-backend
  negative oracle, and no live-host acceptance were established. Do not interpret this local bank as W1 readiness.

### E414 R26 caller refresh (2026-11-02; source-only review, remains OPEN)

This addendum supersedes only the stale R26 caller statements above; the earlier source trace remains useful as a
snapshot but is no longer current about HANDOFF. No runtime source or tests changed in this review.

- **Production caller now exists for the non-coder route.** `workflow_tool.handler` invokes
  `_execute_child_with_managed_lifecycle` at `src/fa/inner_loop/tools/workflow_tool.py:737–745`. The helper at
  `:534–577` orders parent-stage suspension, HANDOFF, child `run_workflow`, reverse HANDOFF, and parent resume.
  `_begin_managed_child` (`:452–486`) calls `ParentStageLease.suspend`, then `ManagedExecution.handoff_to`, and
  validates the exact child namespace before dispatch. `_return_managed_child_to_parent` (`:489–507`) performs the
  reverse transfer and resumes only after the parent binding is restored. `_ManagedStageLease.suspend/resume`
  (`src/fa/cli.py:1479–1530`) settles/disarms the current parent view and opens/rebinds a fresh WRITE view at the
  returned revision. These source paths correct the prior statement that no controller caller sends HANDOFF.
- **The caller is not yet the coder-acquisition route.** `_prepare_invocation` still rejects every
  coder-containing request at `workflow_tool.py:611–616`, before child allocation/HANDOFF; the existing guard is
  covered by `tests/test_invoke_workflow_tool.py::test_acquisition_unavailable_before_child_or_handoff`. The
  active lifecycle therefore proves only accepted non-coder invocations. The current workflow kwargs have no
  acquired `PlanSnapshot`; `run_workflow` still requires `plan_path` for coder and reads via the host workspace at
  `src/fa/inner_loop/workflow_controller.py:2731–2736`. No production call from this handler to
  `inventory_project_artifacts` (`src/fa/inner_loop/managed_inventory.py:78`) or `LIST_PROJECT_ARTIFACTS` was found.
- **Proof level and remaining oracle.** `tests/test_invoke_workflow_tool.py::test_managed_noncoder_handoff_returns_fresh_parent_view_before_success`
  and adjacent refusal/uncertainty tests (`:803–913`) assert event ordering with recording test doubles. They do not
  drive the same handler through the real supervisor/UDS, pinned READ/PROJECT inventory, acquisition decision,
  PlanSnapshot admission, and `drive_session`. `tests/test_execution_handoff_return.py` proves authority/client
  behavior over a real local socket, but not this handler-to-workflow composition. Therefore R26 and S5P2 remain
  OPEN; no live-host or W0/W1/W2 closure is implied. Keep Q114's no-retry/pending-proof/quarantine rules and the
  mandatory plan-before-coder admission. Do not change legacy direct `fa workflow`.

### Q109 `fs_search` source → caller → reader/guard trace (2026-11-01; pre-code)

- **Caller chain:** `project_tools.main:106–111` → `_dispatch:33–50` → `ToolRegistry.dispatch`; line `:44–45`
  registers `build_fs_search_tool(Path(":memory:"), source, cleanup=cleanup)` without a strict-read option.
  No caller of this CLI/helper was found elsewhere under `src/fa`; this source trace does not establish a
  production EXEC/supervisor route. The builder's `workspace_io` path at `fs_search.py:1003–1018` refuses.
- **Path admission:** `_handle:822–960` parses `path`, then `_resolve_subdir:311–337` resolves and checks
  containment. This is a path-based pre-read check; a later replacement is not pinned by it.
- **Outline:** `_do_outline:639–726` → `_load_outline_rows:595–636` uses `Path.stat()` then
  `Path.read_text()` directly.
- **No-query files listing:** `_do_files_listing:741–801` checks `subdir.exists()`, then
  `walk_scope_listing:229–269` enumerates using `iter_searchable_files` with default `strict_paths=False`;
  `files_stat_rows:202–226` uses direct `stat()` and `SearchIndex._read_text_for_match()` for line counts.
- **Indexed query:** `_ensure_index:374–424` → `SearchIndex.ensure_indexed:529–594` →
  `_walk_and_index:489–527` → `_index_one_file:421–467` → `_read_text_for_index:711–729` →
  `_read_bytes:701–708` → `Path.open()`. Enumeration uses default `strict_paths=False`.
  Index lifecycle also has path-based metadata checks: `_stat_canaries:381–399` stats root and `.git` canary
  paths; `_cleanup_stale_files:469–487` calls `is_file()` on paths from the index DB.
- **Fallback query:** `_do_fallback_search:450–476` → `_search_python_walk:1048–1165` does another ordinary
  walk, path-based `resolve()/is_relative_to()`, then `_read_text_for_match()`. Errors are caught and appended
  as warnings, so this path can return a partial result.
- **FTS result formatting:** `_collect_matches:1270–1339` path-resolves and checks `is_file()`, then reads via
  `_read_text_for_match`; `_build_matches_output:1190–1254` reads again for snippets;
  `_compute_total_bytes:748–755` stats paths; files mode calls `walk_scope_listing` and `files_stat_rows` again.
  Thus indexing success alone does not cover query-time or output-format reads/checks.
- **Existing rooted seam:** `_safe_walk.RootedFileReader:84–391` provides bounded, descriptor-relative
  `read_bytes_with_path`; `iter_searchable_files(strict_paths=True):596–655` produces lexical candidates and
  placeholder metadata, requiring the consumer to perform the authoritative rooted read. `StructuralIndex`
  already opts in; `SearchIndex` and `fs_search` do not.
- **Required strict-mode delta:** in the cell helper only, route every outline/list/index/fallback/format source
  read through the existing rooted reader and strict candidate mode. A rooted refusal must escape the current
  fail-degraded fallback/warning paths as a non-success with no partial result. Keep the current host builder's
  default unchanged; retain existing file/output schemas and per-file size filtering. No whole-view snapshot,
  new numeric ceiling, or production EXEC claim is included. Q111's separate output-cap work remains open.
- **Proposed future allowed files after W0:** `src/fa/execution/project_tools.py`,
  `src/fa/inner_loop/tools/fs_search.py`, `src/fa/memory/search_index.py`,
  `tests/test_execution_project_tools.py`, and `tests/test_fs_search.py`. Reuse `_safe_walk.RootedFileReader`
  and `strict_paths`; do not change `_safe_walk.py` unless implementation proves its existing API insufficient.
- **Verification handoff:** Python 3.13 focused bank across those tests plus `tests/test_safe_walk.py`; Ruff,
  mypy/compileall, doc links and `git diff --check`; mutations must kill both a path-based producer/read branch
  and the `project_tools` strict-builder binding. Add producer+edge race tests for outline, files listing,
  indexed query and fallback query, asserting refusal and absence of outside bytes. Managed-backend negative
  oracle and live-host acceptance remain separately required; S4P1/R20 and W0 remain OPEN.

### R18: локальная коррекция guard (E362–E363; строка остаётся OPEN)

`mutation_guard.py:130–172` при managed session с активным/недоступным board
отказывает до host metadata; `write_file.py:120` и `edit_file.py:205–240`
передают этот режим, post-record не вызывает host metadata. Наблюдаемый путь
`tests/test_managed_mutation_guard.py::test_managed_guard_does_not_read_host_metadata_or_silently_drop_enabled_board`
использует реальный session → role registry → UDS/view и проверяет оба инструмента;
контекстные сбои отдельно. Это отрицательный local oracle, не закрытие R18:
управляемые version stamps и allow/conflict при enabled board ещё отсутствуют,
production caller и host evidence не подтверждены. Legacy host mode намеренно
пока имеет прежний `_base_commit` до действующего cutover.

### Classified out (and why), so nothing is exempt by name

| Finding | Class | Reason |
| --- | --- | --- |
| `execution/workspace.py` ×9, `session/manager.py` ×3, `session/workspace.py::_remove_created_target`, `slice_verification.py::_copy_src/mutation_overlay` ×3, `hygiene/hooks/install.py::_install_one` ×2, `providers/live_runner.py::cleanup`, `inner_loop/state.py::cleanup_subagent_workspace`, `worktree_manager.py::cleanup` ×1 | in-process filesystem (`shutil.rmtree/copytree/copy2/ignore_patterns`) | no process, no dynamic import: owned scratch/cleanup and hook installation, covered by their own banks (recovery, isolation) |
| `workspace_bootstrap.py::_uv_executable:294`, `memory/_safe_walk.py::_git_ls_files:146`, `runtime/pty_pool.py::__init__:582` | capability gate (`shutil.which`) | they *change which route runs* when a binary is missing (R07, R20, R09), which is exactly why the managed route must not depend on them |
| `inner_loop/tools/read_file.py::_read_pdf_text:37,58,71` | approved-library data import (`pymupdf`) | parses a bounded file; no project execution. Plugins stay unsupported (spec §6) |
| `runtime/server.py:29–30` | optional installed import | R12; absent FastAPI must degrade to "no server", never to a host runner |

**Coverage statement (the STEP1 exit).** All three workflow entrypoints are accounted for:
**explicit** = `cli._cmd_run` → R08/R10/R11/R16/R24/R25/R27; **chat** = `build_chat_registry` → R10/R14/R15/R17/R22;
**nested** = `build_invoke_workflow_tool` → R26 → R04/R05/R23/R25. Every launcher or import a project instruction can
reach is one of R01–R28; the four findings outside that set are process-free (classified out above). This is a
*coverage* claim, not a closure claim: no row closes until its named negative oracle runs against a managed backend
(SLICE4 STEP2), and the oracle names above are therefore **planned nodeids** unless marked `EXISTING`.

## Closure checklist for each implementation row

1. Actual production caller(s), profile, namespace/lease/view and new source file:line recorded.
2. First project instruction happens after backend/view admission, including setup/import probes.
3. Failure/timeout/disconnect cannot start an alternate host runner or duplicate operation.
4. Negative test exercises real composition/cell or explicitly labels unit-only/fake transport.
5. Required execution_host run fails rather than all-skipping when its backend/profile is absent.
6. Receiver checks receipt/tree/PlanRef identity and terminality; old/unknown evidence cannot pass.
7. All code/state/source cleanup is bounded, owned and observable; no live user tree destruction.

No row is checked or closed in this planning review. Additional aliases/libtmux/pexpect/dependency
launchers and dynamically selected project integrations need traced coverage during implementation.


## E230 current-source anchors — OPEN, no closure assigned

*(Historical ranges as of E230. The R01–R28 anchors in the E285 ledger above are authoritative at `969fa06`;
two of these drifted: `session/manager.begin_run` is now `537–574` (was `441–478`) and the `_cmd_run` PTY
construction is now `cli._build_pty_pool:1923–1951`, called from `_cmd_run:2166–2515`.)*

| File | Current actual producer ranges | I03 handoff |
| --- | --- | --- |
| `src/fa/cli.py` | `_cmd_run:2166–2515`, `_make_workflow_ctx_provider:1616–1697`, `_build_pty_pool:1923–1951`, `_prepare_managed_workspace:150–159` | Extend current seam; managed IO/execution and preserved invariants per spec §§2.1–7.1 |
| `src/fa/session/manager.py` | `_new_session:262–330`, `_provision_workspace:208–240`, `_check_reverse_workspace_ownership:193–206`, `begin_run:441–478` | Provisioner BEFORE create; reference reuse; preserve run reservation; never delete supervisor-owned committed root |
| `src/fa/inner_loop/tools/workflow_tool.py` | `_child_run_context:387–403`, `_requires_acquisition:382–384`, `build_invoke_workflow_tool:406–587` | Existing non-coder child allocation is already real; reuse it, replace coder-only unavailable branch under E231 selected acquisition design |
| `src/fa/inner_loop/workflow_controller.py` | `_run_stage:1181–1383`, `_effective_controller_route:613–645`, `_git_output:835–864`, `_stage_task:1164–1178` | Extend current seam; managed IO/execution and preserved invariants per spec §§2.1–7.1 |
| `src/fa/inner_loop/coder_loop.py` | `_drive_session_inner:535–2111` | Live local conversation snapshot callback at pre-tool dispatch; preserve existing experimental escalation/injection, NO strict-route final-outcome guard |
| `src/fa/inner_loop/tools/write_file.py` | `build_write_file_tool:70–110`, `build_scoped_write_file_tool:113–150` | Extend current seam; managed IO/execution and preserved invariants per spec §§2.1–7.1 |
| `src/fa/inner_loop/tools/edit_file.py` | `_find_fuzzy:26–79`, `build_edit_file_tool:99–193` | Extend current seam; managed IO/execution and preserved invariants per spec §§2.1–7.1 |
| `src/fa/inner_loop/slice_verification.py` | `_run_one:330–357`, `capture_test_nodeids:539–581`, `_pytest_report_status_error:530–536`, `_run_kill_check:1439–1537` | Extend current seam; managed IO/execution and preserved invariants per spec §§2.1–7.1 |
| `src/fa/inner_loop/subagent_runner.py` | `run_stateless:293–410` | Extend current seam; managed IO/execution and preserved invariants per spec §§2.1–7.1 |

Current bounded AST scan inspected all src/fa Python calls to subprocess/os shell/async subprocess,
importlib module/file loading and runpy. It found the existing direct subprocess/import families;
workflow_controller._git_output aliases subprocess.run to a local callable and therefore proves why
static call-name matching alone is incomplete. Trace injected runners and libtmux/pexpect too.
Read_file PDF parsers and runtime optional installed imports are approved-library data/TCB paths,
not evidence of project import closure; bound file parsing and reject unsupported plugin execution.
No newly found source route is silently exempted; future implementation closes rows only with the
actual caller/profile/view/negative nodeid evidence in the checklist above.

## E231 source-grounded Q59/Q60 closure (planning only)

- Existing `expansion.py:10–23`, `routing.py:3–13`, `cli.py:2408–2437` support mid-chat advice and
  current injection plumbing. Preserve both; no new forced workflow mode or duplicate injection.
- Existing `planner_dispatch.py:17–55`, `plan_admission.py:133–168`,
  `workflow_controller.py:1181–1383,2231–2270,2370–2428` and `coder_loop.py:379–408` are the ONE
  machine/type/snapshot/outcome/validator/repair seams. New managed_acquisition helpers are pure
  choice/metadata/resolve/render functions, not a second orchestration layer. Spec §7.0 owns joins.
- Actual `pr_prepare` is `tools/prepare_pr.py:186–283`; registration at `cli.py:1788` occurs AFTER
  role-profile assembly, store at `cli.py:2285–2290` and `pr_draft.py:45–118` has current-session
  digest trust. Filter it for read-only acquisition; preserve constrained ordinary/scoped usage
  and Q68 sticky failed-tool behavior. No `tools/pr_prepare.py` exists.
- Reserved admission values in `admission_schema.py:93–104,154–182` are NOT acquisition producers.
  v1 hash path `:129–151` would require a promoted hash for ACQUISITION ADMITTED; spec §7 supplies
  explicit v2 selected-source vs installed-bundle cases rather than inventing a false promotion.
- Q59/Q60/Q63/Q74 resolved in E231; implementation inventory rows remain OPEN, not closed by docs.

#### Q109 implementation result (2026-11-01; local cell-helper slice only)

- Changed only the selected `fs_search` helper seam: `project_tools._dispatch` now opts the existing builder into
  `strict_rooted_reads=True`; the builder owns a pinned `RootedFileReader` through its `ExitStack` cleanup and
  injects it into `SearchIndex`. Legacy host builders keep the default `False`.
- Strict rooted reads now cover outline; unqueried listing and row/line formatting; full per-call FTS indexing;
  Python fallback scanning; indexed-hit reads, matches/snippet construction, and byte accounting. Strict candidate
  enumeration uses `iter_searchable_files(strict_paths=True)`. Strict indexing rebuilds its in-memory tables from
  rooted bytes and does not use path canaries or stale-path `is_file()` probes. `RootedReadError` propagates through
  index/list/fallback catches to a non-success; no rooted refusal degrades to fallback, warning-only, partial result,
  or external bytes. Outline retains its existing explicit too-large invalid-params response.
- Files changed for this slice: `src/fa/execution/project_tools.py`, `src/fa/inner_loop/tools/fs_search.py`,
  `src/fa/memory/search_index.py`, and `tests/test_execution_project_tools.py`. `_safe_walk.py` was reused unchanged;
  `tests/test_fs_search.py` was unchanged. No public schema/result shape, new numeric ceiling, whole-view snapshot,
  or production EXEC claim was added.
- Added tests for the cell builder's strict binding and legacy host default, plus symlink-replacement refusal across
  outline, listing, indexed query, and forced Python fallback. Baseline before edits: 102 passed, 2 xfailed.
  Final focused bank (`tests/test_execution_project_tools.py tests/test_fs_search.py tests/test_safe_walk.py
  tests/test_fs_reach.py tests/test_structural_index.py`): **140 passed, 2 xfailed**, exit 0. The two xfails are the
  existing Q106 outline/reach envelope cases.
- Static verification: `ruff check` on the four changed Python files — pass, exit 0; `pyrefly check` on those files —
  `0 errors (1 suppressed, 2 warnings not shown)`, exit 0; `compileall` for the three source modules — exit 0;
  `git diff --check` — exit 0.
- Targeted mutation checks were killed (expected red, both sources restored): (1) replaced
  `RootedFileReader.read_bytes_with_path` with a path-based `root / rel` open; the outline race test failed because
  outside `escaped_secret` content was returned (pytest exit 1); (2) changed the `project_tools` fs_search binding
  from strict `True` to `False`; the binding test failed on `[False] != [True]` (pytest exit 1).
- This closes only the Q109 local cell-helper rooted-read slice. The production managed execution route, broader
  S4P1/S4P2 oracles, Docker/host acceptance, and live-host `fa update` E2E remain open and are not inferred from
  these local results.
- Supplemental compatibility check: `tests/test_s127_fs_surface.py` — **18 passed**, exit 0. The combined
  `tests/test_s127_fs_surface.py tests/test_s127_outline.py` run had 33 passed and one unrelated failure:
  `test_s127_fold_cli_py_matches_ast_truth` expects 78 symbols in `src/fa/cli.py` but observes 79; `cli.py` is
  outside this slice and already has unrelated worktree changes, so the stale oracle was not edited. Combined-run
  exit was 1.

### E393 — R02/Q112 local entrypoint readiness cut (2026-11-02)

`fa-entrypoint.sh:169–183` now treats a failed `workspace_bootstrap ensure` as a managed auto-run refusal while preserving the explicit command override path. The caller at `:231–243` removes only a newly created clone, writes `status=FAILED`, and enters standby before publishing `/sessions/.active`; resumed workspaces are retained. The provision gate at `:282–290` excludes command overrides, and the explicit override still executes at `:292–295`.

Local proof: `tests/test_fa_entrypoint.py` — **20 passed, exit 0** on CPython 3.13.16; Ruff, `bash -n`, `compileall`, and `git diff --check` passed. Producer mutation disabling the readiness refusal was killed: the test observed `status=SUCCESS` after `fa run` executed (pytest exit 1). Edge mutation removing the command-override exclusion was killed by the provision-call sentinel assertion (pytest exit 1). Both mutations were restored.

Scope stays narrow: the test seam forces the existing bootstrap command to fail; it does not prove that successful bootstrap implies a managed EXEC backend. The separate managed-backend negative oracle, Docker/live-host result, R02/S4P1 rows, and W0 remain open. See Q112 and the proposed ledger-aware host cases in `notes/i03-live-e2e-test-plan-2026-10-22.md`.

### E394 — R27/R28 current source, caller, and oracle refresh (2026-11-02; no row closed)

**R27 — local managed composition implemented; row remains OPEN for broader acceptance.** The direct `cli._cmd_run` path now reuses a workflow-supplied `ManagedExecution` or creates the direct-run owner, opens a `WRITE/PROJECT` view at its authority-reported base revision, and binds the admitted `ClientWorkspacePort` and managed Bash executor into the run registry. `write_file` and `edit_file` derive Blackboard stamps from the port's pinned revision plus a complete `knowledge/llms.txt` read; refused, incomplete, or inconsistent metadata denies before mutation, and post-write Blackboard records use the same stamps. Managed runs omit the host-path `LearningObserver`. `tests/test_execution_composition.py::test_direct_chat_keeps_canonical_tree_unchanged_until_stage_publication` now exercises a real local SupervisorService, session manager/DB, parsed direct chat CLI path, and mocked provider request: project bytes remain unchanged during the live stage, a successful view write becomes canonical only after stage publication, and direct ownership releases while a workflow-supplied owner remains owned. `tests/test_managed_mutation_metadata.py` pins refusal/incomplete-read behavior and active overlap checking. This is local component/composition evidence only; the live-host E2E index remains NOT RUN and R27 remains OPEN under the broader S4P1/strict row-closure rule.

**R28.** `scripts/bootstrap/host_bootstrap.py::_run:24–39` owns direct subprocess execution; `main:95–115` finds `uv`, conditionally installs `just`, runs the workspace readiness wrapper and emits `FA_AGENT_READY=1` only on success. `git grep` finds its only direct production caller at `justfile:113` (`agent-bootstrap`); the VS Code convenience command delegates to that alias. Existing `tests/test_workspace_bootstrap_aliases.py` covers the operator bootstrap, current/wrong `just`, missing `uv`, wrapper degradation, and alias consistency. The direct `_cmd_run` route now binds managed Bash when a managed execution is configured, and `tests/test_managed_registry_binding.py` verifies managed Bash does not become a host subprocess. The dedicated `test_no_model_tool_can_reach_the_host_bootstrap` oracle is still absent, so R28 remains OPEN pending that path-specific negative and broader acceptance.

No runtime/test file changed and no pytest result is claimed in this refresh. `.venv` is absent in this turn; only source, callers, `git grep`, test names, and the inventory were inspected. The absence of the planned negative oracles is recorded explicitly rather than treated as evidence of exclusion.

### E422 — managed new-root/readiness caller map (2026-11-02; local, no inventory rows closed)

**Current production path.** `cli._session_manager_for_args:265–290` chooses the default `/repo` seed, an explicitly configured source, or clean empty seed when `FA_SESSION_SOURCE` is set to empty. `SessionManager._new_session:312–390` admits a provisioning `RunContext`; `_provision_managed:246–278` passes that exact identity and source choice to the managed provisioner; `_prepare_workspace:232–244` passes it to the readiness producer. `ClientWorkspaceProvisioner:544+` sends `REGISTER_WORKSPACE{create:true}` for a new root; `ExecutionService._register_workspace:612+` routes that operation to `WorkspaceAuthority.register_new:1434+`. The authority's `_environment_identity:514+` resolves exact root locks or a unique approved First-Agent baseline for a lockless clean root. `managed_environment_readiness:484–541` uses the same run's PROVISIONING view for both required tool probes and only releases after confirmed terminality.

**Named local proof.** Materializer and baseline: `tests/test_execution_workspace.py::test_register_new_materializes_approved_source_and_keeps_partial_bytes_on_failure`, `::test_authority_baseline_discovery_requires_one_approved_first_agent_root`, `::test_lockless_clean_seed_uses_only_operator_approved_baseline_artifact`; caller/service: `tests/test_execution_service.py::test_register_create_true_materializes_approved_or_empty_seed`, `tests/test_execution_composition.py::test_the_client_provisioner_materializes_a_root_from_an_approved_source`; same-run/Q118/readiness: `tests/test_session_lifecycle.py::test_managed_provisioner_owns_workspace_bytes_and_readiness_receives_same_run_context`, `::test_new_root_provisioning_refusal_retains_q118_tombstone_and_run_binding`, `tests/test_execution_composition.py::test_managed_readiness_probes_both_required_tools_and_settles_same_run`, `::test_unconfirmed_readiness_view_end_withholds_writer_release`, and `tests/test_cli.py::test_managed_readiness_failure_leaves_tombstone_before_provider_or_workflow_events`; empty-source selection: `tests/test_cli.py::test_empty_session_source_selects_clean_seed_before_managed_provisioning`.

This is local test/source evidence only. Live `fa-entrypoint` `.active` behavior, actual Docker prewarm/artifact mounting, profile UID/GID compatibility, process trace, authoritative host DB/event ledger and L-ENTRY-6 remain NOT RUN. No R02/S4P1 row, W0/W1/W2, or I03 closure is claimed.

### E423 — R02 managed auto-run source → manager → readiness → active pointer (2026-11-03; OPEN)

**Current call path (working tree).** `scripts/fa-entrypoint.sh:200–209` enters the managed path only for auto-run without command override and skips host clone/configure/readiness there. `:263–265` unsets inherited `PYTHONPATH`; `:280–305` calls the module CLI without `--workspace`, publishes `/sessions/.active` only after manager success, and otherwise reports `FAILED` and enters standby before `fa run`. Explicit command override and standby remain on the legacy branch (`:210–255`, `:308–312`). The path still depends on the existing `/repo/.git` entrypoint gate at `:200`; this cut does not generalize container startup outside that self-repository mode.

`src/fa/session/manager.py::provision_entrypoint_session:460–477` makes `workspace_root / session_id` the manager-owned default when no override is supplied. `_main:596–639` requires the existing configured `client_workspace_provisioner`, injects `_managed_workspace_preparer`, and uses the CLI source policy: configured nonempty `FA_SESSION_SOURCE` wins; explicitly empty means clean seed; absent means `/repo` if it is a directory. The `SessionManager` lifecycle and managed composition own reservation, manifest/DB, materialization/attach and same-run readiness; no host fallback was reintroduced. A readiness refusal preserves Q118's non-active tombstone and uncertain/resumed workspace bytes; it does not publish/replace `.active`, reach `fa run`, or emit workflow events.

**Named local oracles.** `tests/test_fa_entrypoint.py::test_managed_auto_run_provisions_before_publication_and_keeps_controller_import_pinned` asserts the call boundary, manager arguments, active-pointer ordering and controller import pin; `tests/test_session_lifecycle.py::test_entrypoint_provisioning_uses_manager_owned_default_root_without_workspace`, `::test_entrypoint_manager_refuses_missing_managed_provisioner_before_state_changes`, `::test_entrypoint_cli_provisions_manager_default_root_without_workspace_argument`, `::test_entrypoint_cli_explicit_source_overrides_default_repo_seed`, and `::test_entrypoint_cli_explicit_empty_source_selects_clean_seed` pin the manager CLI/root/source policy; the lifecycle readiness/tombstone tests assert refusal effects. `tests/test_session_manifest_guards.py::test_every_error_code_is_named_in_some_test` now resolves manager source from mutmut's immutable staged tree where applicable; its injected provisioner/readiness fixture only enables guard/lifecycle tests and is not a substitute for managed-composition proof.

**Mutation/verification status.** Targeted bank: 67 passed; configured mutation-selected bank: 414 passed; Ruff and shell syntax: pass. Focused mutations: provision adapter 14/14 killed; source-policy/optional-workspace subset 13/13 killed; shell edge mutations 4/4 killed. The configured three-module mutmut run completed classification of 2,200 mutants but its wrapper was stopped during slow diff-report generation; raw stats are 700 killed, 208 survived, 72 no-tests, 1,220 type-invalid, while wrapper exit/artifact is unavailable. No row is closed on this basis.

**Still required.** Independent review; complete configured mutmut artifact/report handling and survivor triage as required by the mutation gate; exact R02 whole-system negative oracle through the approved deployed entrypoint; approved live-host `fa update` process trace and authoritative session DB/event-ledger comparison; prebuilt-environment fast-path/L-ENTRY-6; then strict W0/W1/W2 dependency and row review. No live-host run was performed. R02, S4P1, W0/W1/W2, and I03 remain OPEN.
