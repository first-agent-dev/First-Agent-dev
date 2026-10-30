# I03 execution call inventory — source-grounded initial version

Date: 2026-10-15; E230 refresh 2026-10-16; **E285 refresh 2026-10-23 at `969fa06`** (coverage re-scanned, every
`src/fa` process/import route classified; see [§E285](#e285-refresh-2026-10-23--every-srcfa-processimport-route-classified-at-969fa06)
below the historical tables). The initial d910 line table below is historical; refreshed exact symbol ranges follow it.
**State: OPEN — coverage complete at `969fa06`, no row closed.** The E285 scan accounts for every launcher and
dynamic-import call site in `src/fa` (28 call sites in 16 files, each mapped to exactly one row) and every row now
carries its exact current anchor, a real caller trace and a named negative oracle. What is still missing is the thing
a document cannot supply: the negative oracle *running* against a managed backend, which is SLICE4 STEP2's work (A5).
No runtime source is changed by this inventory review.
No runtime source is changed by this inventory review. Static search is evidence of candidates, not a
proof that a route is reachable or safe. 'Read-only' and fixed Git argv do not exempt project Git.

| Actual producer / source lines | Inspected caller/dependency | Required route / concrete negative oracle (future) |
| --- | --- | --- |
| `scripts/fa:36–45,58–74` | .active supplies project CWD to compose exec; host help prepends repo/src | Installed isolated controller/help; poison workspace fa.py/PYTHONPATH/editable pth cannot change imported module or make help a no-op |
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
| R01 | `scripts/fa:36–45,58–74` compose wrapper; `.active` supplies project CWD | operator shell | TCB host | `tests/test_deploy_scripts.py::test_fa_wrapper_uses_arrays_for_compose_and_flags` | `tests/test_e2e_artifact_contract.py::test_installed_controller_help_ignores_poisoned_workspace` |
| R02 | `scripts/fa-entrypoint.sh:153–171,231–248,266–273` configure/provision/readiness, then auto-run | operator/container entry | TCB host | `tests/test_fa_update_script.py::test_fa_update_script_tracks_actual_build_inputs` | `…::test_entrypoint_runs_no_project_command_without_backend` |
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
| R25 | `workflow_controller.py::_run_stage:1181–1383`, `_effective_controller_route:613–645`, `_validate_plan_admission:2231–2270`, `_promote_validated_plan:2273–2280` (still calls `plan_promotion.publish_plan_buffer`) | explicit, nested | host loop + the second plan writer R3 forbids | `tests/test_verify_gate_live.py` | `…::test_the_plan_write_goes_through_the_authority_and_the_legacy_writer_is_gone` |
| R26 | `inner_loop/tools/workflow_tool.py::_child_run_context:387–403`, `build_invoke_workflow_tool:406–587` | nested workflow | host child controller with no `PlanRef` | `tests/test_invoke_workflow_tool.py`, `tests/test_handoff_payload.py` | `…::test_nested_child_gets_an_attested_namespace_and_no_parent_writer` |
| R27 | `coder_loop.py::_drive_session_inner:535–2111` (live-session callback, no route of its own) | explicit, chat | controller process | `tests/test_coder_loop.py` | `…::test_a_live_chat_session_cannot_mutate_the_canonical_tree` |
| R28 | `scripts/bootstrap/host_bootstrap.py:23–40` | operator | TCB host | `tests/test_workspace_bootstrap_aliases.py::test_host_bootstrap_missing_uv_is_stable_and_does_not_call_wrapper` | `…::test_no_model_tool_can_reach_the_host_bootstrap` |

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
