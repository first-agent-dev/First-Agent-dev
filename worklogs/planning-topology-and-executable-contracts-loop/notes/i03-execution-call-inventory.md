# I03 execution call inventory — source-grounded initial version

Date: 2026-10-15; E230 refresh 2026-10-16; **E285 coverage baseline 2026-10-23 at `969fa06`** (coverage
re-scanned, every `src/fa` process/import route classified; see [§E285](#e285-refresh-2026-10-23--every-srcfa-processimport-route-classified-at-969fa06)
below the historical tables); **E414 R26**; **E423–E424 R02 refresh**; and **E425–E426 deployment-boundary reconciliation; E427–E428 R01 help fail-closed refresh, E429/Q119 workspace-route blocker, E430 host-help argument-scan closure, E431 Q119 target-contract audit, E432 Q119-A selection/source audit, E433 read-only workspace/session resolver primitive, E434 CLI command/path inventory, E435 Q120 proxy-route blocker, E436 Q120-A wrapper refusal, E437 R02 real-entrypoint backend refusal, and E438 R04/R05/R08 real-CLI backend refusal 2026-11-03**; **E447–E448 R12/Q125 resolution, E451 R14, E462–E463 R01/R03, and E464 R15 local W0 closeouts 2026-11-05** (addenda below). The initial
d910 line table below is historical; refreshed exact symbol ranges follow it. **State: OPEN — E285 remains the
frozen coverage baseline; R02 and R20–R28 have targeted source refreshes; R01, R03, R12, R13, R14, and R15 have their scoped Arena-local W0 rows CLOSED; other row dispositions remain recorded individually, and global W0 is OPEN.** E402–E404
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
| `src/fa/runtime/server.py:62–83`; `src/fa/runtime/bash_executor.py:80–139` | optional HTTP PTY server/client projection | Optional cell-internal only; response preserves timed_out/identity or rejects as unknown; HTTP health/close cannot certify descendant barrier |
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
| R01 | `scripts/fa:36–45` reads `.active`; `:98–112` has isolated-controller helpers; `:219–255` explicitly dispatches `run`, `workflow`, `stats`, `authoring-check`, `inner-loop-smoke`, and `chunk`, while the generic product-command default now invokes the installed controller. `src/fa/cli.py::_apply_wrapper_session_workspace` maps active `run`/`workflow`; `::_resolve_wrapper_explicit_workspace` owner-maps or preflights a disjoint new path; `::_apply_wrapper_stats_workspace` maps stats workspace without changing session filters; `::_apply_wrapper_authoring_workspace` maps authoring workspace/manifest; `::_apply_wrapper_config_path` maps ordinary relative config inputs; `::_apply_wrapper_chunk_workspace` anchors relative chunk paths; `::_disposable_smoke_workspace` constrains dev-only smoke. `SessionManager.validate_new_workspace_disjoint` rejects active/provisioning ancestor/descendant overlap before lifecycle allocation; WorkspaceAuthority remains final physical-root gate. | Operator shell. `run`, `workflow`, `stats`, `authoring-check`, and ordinary product commands use installed controller at trusted CWD; active `chunk` uses it with `.active`; smoke refuses before Compose whenever `.active` is non-empty and otherwise uses the installed controller only with explicit `--workspace`; host verbs, proxy, `clean`, and unknown/rejected routes keep their explicit boundaries. | `run`/`workflow` resolve manifest/DB identity and revalidate lifecycle; explicit run paths reuse owners or allow only approved disjoint new roots, preserving explicit IDs; `chunk` anchors relative paths. Stats does not inject/replace `--session-id`; authoring preserves active-root manifest CWD; ordinary relative `--config` paths map through owner resolver, without changing defaults. | C1 argv: `tests/test_deploy_scripts.py` workflow/stats/authoring/generic wrapper matrix; installed-wheel C2/C3: `tests/test_controller_installed.py::test_wrapper_product_command_uses_installed_controller_with_hostile_project_env`; production C2: `tests/test_execution_composition.py::test_r01_wrapper_run_resolves_active_workspace_and_revalidates_session`; invalid selectors, Q128 mismatch/overlap and no-effect oracles. Smoke boundary is E456. | R01 Arena-local W0 row CLOSED by E462: full command/workspace matrix, hostile-CWD/PYTHONPATH wrapper-to-installed-controller composition, CPython 3.13.16 verification, and producer/EDGE mutations passed. R23 is RETIRED / NOT APPLICABLE TO MANAGED W0 under Q126-A/E469, not PASS; global Q113 W0 remains OPEN with 27 active rows. No live-host acceptance. |
| R02 | `scripts/fa-entrypoint.sh:200–209` selects managed auto-run only for self-repo/no-`FA_WORKSPACE` startup with no command override and truthy auto-run; `:263–265` clears inherited `PYTHONPATH`; `:280–305` calls manager provision without `--workspace` and publishes `.active` only on success; legacy override/standby stays at `:210–255,308–312`. `src/fa/session/manager.py::provision_entrypoint_session:460–477` owns the default root; `_main:596–639` binds the configured provisioner/readiness. | operator/container entry | managed provision/readiness for this auto-run branch; TCB-host legacy adapter remains for explicit override/standby | `tests/test_fa_entrypoint.py::test_managed_auto_run_provisions_before_publication_and_keeps_controller_import_pinned`; `tests/test_session_lifecycle.py::test_entrypoint_manager_uses_injected_provisioner_for_success` | local manager refusal: `tests/test_session_lifecycle.py::test_entrypoint_manager_refuses_missing_managed_provisioner_before_state_changes`; CLI-input refusal: `::test_entrypoint_manager_cli_rejects_missing_required_arguments_before_backend_lookup`; shell failure ordering: `tests/test_fa_entrypoint.py::test_entrypoint_auto_run_refuses_after_managed_readiness_failure_before_active_or_run` (manager is stubbed, so this is not the real backend-unavailable composition). `tests/test_fa_entrypoint.py::test_entrypoint_real_manager_refuses_when_configured_supervisor_is_unavailable` now exercises the actual entrypoint with the real `SessionManager`/`ExecutionClient` and a configured, absent UDS endpoint: it observes `BACKEND_UNAVAILABLE`, no session workspace, `.active`, host Git, or `fa run`, and the expected Q118 provisioning tombstone. The Arena-local R02 W0 negative oracle passes; live/host acceptance remains NOT RUN. |
| R03 | `scripts/bootstrap/workspace.py:13–17` prepends the checked-out `src` before readiness import | bootstrap wrapper | TCB host | `tests/test_workspace_bootstrap_aliases.py::test_just_bootstrap_aliases_converge_and_doctor_is_read_only` | same as R01 (poisoned checkout/PYTHONPATH) |
| R04 | `session/manager.py::_new_session:335–426` → `_provision_workspace:230–262` (callers `:377`); `begin_run:537–574` reserves a run, spawns nothing | explicit, chat, nested | host | `tests/test_session_workspace_provisioning.py` | `tests/test_cli.py::test_cli_new_run_refuses_unavailable_supervisor_before_host_git_provider_or_pty` (actual `fa.cli.main` with real SessionManager/ClientWorkspaceProvisioner/ExecutionClient; configured absent UDS returns `BACKEND_UNAVAILABLE`, without host Git or project materialization; Arena-local R04 oracle passes) |
| R05 | `session/workspace.py::provision_git_workspace:290–360`, `configure_existing_workspace:394–524`, `_run_git:170–204` (`subprocess.run`@182) | R04 | host (project Git) | `tests/test_session_workspace_provisioning.py` | same actual CLI oracle `tests/test_cli.py::test_cli_new_run_refuses_unavailable_supervisor_before_host_git_provider_or_pty`; its Git trace and immutable seed assertions show no host clone/configuration or hook path (Arena-local R05 oracle passes). |
| R06 | `cli.py::_prepare_managed_workspace` → `session/manager.py::_prepare_workspace:275–287` checks actual readiness before activation; degraded state raises `workspace_not_ready` | explicit new-session `_cmd_run` via real SessionManager | managed registration/readiness, fail-closed | `tests/test_cli.py::test_prepare_managed_workspace_warns_only_for_degraded_state` (warning helper behavior only) | `tests/test_cli.py::test_cli_blocks_degraded_managed_readiness_without_host_probe_fallback`: actual `fa.cli.main()` + real `SessionManager`/`ClientWorkspaceProvisioner` against live local UDS `SupervisorService`; probe refusal blocks provider/PTY and leaves no `.active`; Arena-local R06 oracle passes |
| R07 | `execution/composition.py::managed_environment_readiness:484–540` opens a managed provisioning view and runs `pytest --version && mutmut --version` through `ManagedBashExecutor`; it does not use host `workspace_bootstrap` process runner/`uv` discovery | R06 readiness on the production CLI caller path | managed cell, no host project sync/hooks/import probes | `tests/test_workspace_bootstrap.py::test_process_runner_uses_bounded_captured_noninteractive_environment` (legacy host runner contract only) | same actual CLI oracle asserts host `git`, `uv`, `pytest`, `mutmut` markers absent while managed probe returns degraded; Arena-local R07 oracle passes |
| R08 | `cli.py::_build_pty_pool:1923–1951` → `_PtyPool(...)`@1948; caller `_cmd_run:2166–2515` | explicit | host | `tests/test_cli.py` | `tests/test_cli.py::test_cli_new_run_refuses_unavailable_supervisor_before_host_git_provider_or_pty` (actual CLI handler refuses before provider transport and PTY construction; Arena-local R08 oracle passes) |
| R09 | `runtime/pty_pool.py::PtySession.__init__` (`pexpect.spawn`) and `PtyPool.__init__` (`shutil.which("tmux")`, `libtmux.Server`); production host caller `cli.py::_build_pty_pool` | explicit `_cmd_run` after R08; cell-local pool remains `execution/cell_worker.py::_cell_pool` | host PTY paths must remain unreachable when managed admission fails; cell uses its own pool | `tests/test_execution_cell_worker.py` local PTY/control coverage (cell adapter only; not a host-isolation proof) | `tests/test_cli.py::test_cli_new_run_refuses_unavailable_supervisor_before_host_git_provider_or_pty` now wraps the actual CLI PTY-pool caller and instruments module-local tmux lookup, `libtmux.Server`, and `pexpect.spawn`; configured absent UDS refuses with `BACKEND_UNAVAILABLE` and all host PTY markers remain zero. Arena-local R09 oracle passes |
| R10 | `inner_loop/tools/run_bash.py::build_run_bash_tool` handler → `_run_pty_executor` → `ManagedBashExecutor`; managed failures must not reach `_run_subprocess_fallback` or host Git tracking | direct chat/coder and nested registry path | one admitted managed EXEC; fail closed, no controller shell/PTY | `tests/test_managed_registry_binding.py::test_real_registry_role_binds_view_and_bash_without_host_effects[chat]` (registry proof) | `tests/test_execution_composition.py::test_direct_chat_keeps_canonical_tree_unchanged_until_stage_publication[False]` and `[True]`: production `_cmd_run`/`drive_session` builds the role registry; fake provider calls registered `fs_run_bash`; real local UDS `SupervisorService` has no cell backend and refuses EXEC; one real EXEC handler attempt yields recorded `execution_unavailable`, `retryable=False`, with zero module-local host `subprocess.run` calls. Both caller parameterizations pass; Arena-local R10 oracle passes |
| R11 | `src/fa/inner_loop/tools/run_bash.py::build_run_bash_tool.handler` — explicit `managed_executor=None` must return `execution_unavailable`, not enter legacy `_run_subprocess_fallback`; legacy sentinel routes remain unchanged | production `cli._build_run_tool_registry` → role registry → `drive_session`, with a live managed workspace port and no executor binding | managed route fails closed; no UDS EXEC or controller subprocess | `tests/test_venv_path_wiring.py::test_subprocess_fallback_resolves_venv_tools_live` (legacy fallback positive only) | `tests/test_managed_registry_binding.py::test_missing_executor_fails_closed_through_production_chat_session`: real local UDS supervisor/writer + PROJECT view/ClientWorkspacePort, production chat/run registry and real `drive_session`; scripted provider invokes registered `fs_run_bash`. Result is non-retryable `execution_unavailable`, with zero `Operation.EXEC`, zero host subprocess calls, and no marker file. Producer guard and `workspace_io` caller-edge mutants both killed/restored; Arena-local R11 oracle passes. |
| R12 | `runtime/__init__.py:12–18` public optional import; `runtime/server.py:29–30,62–83`; `runtime/bash_executor.py:80–139` HTTP projection | No production `RemoteRuntimeExecutor` caller; ordinary chat uses managed `run_bash` through `cli._cmd_run` → `_build_run_tool_registry` → `drive_session` | HTTP server/client remain cell-internal optional components; no claim that the future remote client is wired or is a security authority | `tests/test_runtime_server_open_stand.py::test_server_imports_without_fastapi` and R12 C1 component tests; HTTP transport is stubbed and six C1 cases remain skipped with the deferred runtime-server extra | **R12 Arena-local W0 row CLOSED (Q125 option A, 2026-11-05):** `tests/test_execution_composition.py::test_r12_production_managed_chat_never_uses_remote_runtime_when_server_unavailable` drives parsed `fa run --role chat` through real `SessionManager`, `_cmd_run`, run registry, `drive_session`, registered `fs_run_bash` and `ManagedBashExecutor` to a real local UDS `SupervisorService` with no backend and the optional server absent. The ledger reports non-retryable `execution_unavailable`; exactly one EXEC is refused as `BACKEND_UNAVAILABLE`. Exact no-effect counters: zero remote-runtime construction/run, FastAPI start, host subprocess fallback, host PTY, proxy credential, cell launch and project marker write. The producer selector and `_cmd_run` managed-executor caller-edge mutants were both killed by this nodeid; each temporary source file was restored with identical SHA-256. CPython 3.13.16, 14-module composition bank: 686 passed, 1 expected xfail; R12 component bank: 9 passed, 6 skipped. Live E2E is NOT RUN until the final wave after W3; no Docker is required for this W0 oracle. Global Q113 W0 remains OPEN; W1 has not started. See Q125 and increment E448. |
| R13 | Legacy `inner_loop/subagent_runner.py::run_stateless`/`tools/spawn_subagent.py` remains separate; managed producer `inner_loop/tools/managed_subagent.py::build_managed_subagent_tool` registered through `cli.py::_register_managed_subagent_tool` and `_cmd_run`; workflow caller `cli._cmd_workflow` planner/coder stages | ordinary chat and workflow planner/coder | Legacy runner is host-only and not the managed route; managed child uses task-only input, noninteractive per-view READ, stateless Bash, private scratch, parent-only project writer, bounded run-log report, no proxy credential or host fallback | `tests/test_managed_subagent.py`, `tests/test_managed_bash_tool.py`, `tests/test_managed_stage_lease.py`, `tests/test_managed_registry_binding.py`, `tests/test_execution_composition.py`, `tests/test_execution_docker.py`, Q122 reader/view/backend tests | **R13 local W0 row CLOSED:** `test_subagent_commands_carry_no_proxy_credential` covers chat and `test_workflow_stage_runs_managed_child_with_local_backend` covers planner/coder in unavailable, configured `UNAPPROVED_PROFILE`, and approved modes. All eight negative cases assert one EXEC, zero allowed/cell/Bash-fallback/legacy-runner/proxy-credential/project-write effects; approved paths prove managed execution, Q124 64 MiB scratch cap/report evidence, read-only mount and cleanup. Targeted producer, caller-edge and Q124 tmpfs producer mutants killed/restored; related 12-module suite **643 passed, 1 expected xfail**. Live-host Docker ENOSPC/mount-release and ledger-append E2E are `NOT RUN` until final wave; no Docker host is required for local W0. Global Q113 W0 remains OPEN until all other S4P1 rows pass; W1 has not started. See R13 plan §18 and increment E446. |
| R14 | `inner_loop/tools/__init__.py::build_baseline_registry`, `build_planner_registry`, `build_eval_registry`, `build_chat_registry`: on profile-builder failure, the managed `workspace_io` path must re-raise; the host-only compatibility fallback otherwise builds `fs_run_bash`. Production binding is `cli._cmd_run` → `_build_run_tool_registry` → `_build_role_registry`. | `fa run` for chat, coder, planner, eval | Managed profile-construction failure propagates before provider/`drive_session` dispatch; no host registry command, host PTY, or host subprocess | Existing component control: `tests/test_execution_tool_index.py::test_a_managed_registry_ships_no_host_git_tools`; production-caller oracle: `tests/test_execution_composition.py::test_r14_managed_profile_failure_never_reaches_host_tools` (4 role parameterizations) | **R14 Arena-local W0 row CLOSED:** real `SessionManager`, managed `ClientWorkspacePort`/executor, local UDS supervisor, and actual `cli._cmd_run`; injected role-profile failure propagates for all four roles. Exact no-effect evidence: zero provider calls, zero EXECs, zero host subprocess/PTY calls, zero cell launches, and no project marker. Producer and managed-registry caller-edge mutants both reached the trapped host fallback and were rejected. No Docker/live-host acceptance is claimed. See increment E451. |
| R15 | `inner_loop/tools/write_file.py:70–110,113–150`; `edit_file.py:99–193` | all three; `profiles.py` → `cli._cmd_run` → `_build_run_tool_registry` → `drive_session` | admitted managed view through `workspace_io`; canonical tree changes only on publication | Component: `tests/test_execution_tool_port.py::test_tools_built_with_the_port_read_write_and_edit_through_it`; **R15 Arena-local W0 row CLOSED (E464):** `tests/test_execution_composition.py::test_subagent_commands_carry_no_proxy_credential` drives actual chat `cli._cmd_run`/`drive_session` through local UDS authority; both file-tool results succeed, canonical bytes remain unchanged until publication, and the final published bytes reflect the edit. Six parameterizations passed; both producer kills and the registry-edge kill were rejected/restored. No Docker/live-host acceptance is claimed. |
| R16 | `workflow_controller._eval_evidence_block` no longer invokes project Git; coder base/current revisions flow through `ManagedExecution.revision_changes` → `ExecutionClient.diff_revisions` → v2 `DIFF_REVISIONS` → `WorkspaceAuthority.diff_revisions` | `cli._cmd_workflow` → `run_workflow` → `_run_stage`/`_stage_task` → eval evidence | read-only same-workspace sealed-manifest delta through pinned `READ/PROJECT`; paths/status only, bounded 128 entries; unavailable is not NONE; no host fallback | `tests/test_eval_evidence_block.py`; `tests/test_execution_service.py::test_v2_diff_compares_sealed_manifests_through_a_pinned_read_view`; `tests/test_execution_composition.py::test_workflow_stage_runs_managed_child_with_local_backend[available-unavailable-coder]` and `[refused-unavailable-coder]` | **R16 Arena-local W0 row CLOSED (E466):** production `fa workflow` reaches the v2 read-only diff via the real local UDS supervisor; positive path metadata and explicit refused/unavailable behavior are observed. Refusal oracle proves workspace bytes/current revision unchanged at the operation boundary and no journal record; eval receives unavailable, never false NONE. Controller has no Git runner. Producer and caller-edge mutants both failed their designated real oracles and were restored byte-for-byte. Related bank: 589 passed, 1 expected xfail. No Docker/live-host acceptance claimed; R23 is RETIRED / NOT APPLICABLE TO MANAGED W0 under Q126-A/E469, not PASS. Global Q113 W0 remains OPEN with 27 active rows; W1 has not started. See Q129/E466 and E469. |
| R17 | `inner_loop/tools/pair_tools.py::_run_git:28–36` (`subprocess.run`@30), reached by `build_baseline_registry` → `_register_extra_tools` only on unmanaged baseline; chat excludes pair tools | Managed production caller: `cli._cmd_run` → `_run_cli_stage` → `_drive_stage_with_managed_workspace` → `_build_run_tool_registry` → coder baseline | Pair Git remains legacy unmanaged behavior; with a managed `WorkspacePort`, `include_pair` is disabled and checkpoint/undo/diff are not offered; no host fallback | Historical component/wiring coverage is not the row oracle. Production-caller oracle: `tests/test_execution_composition.py::test_managed_coder_run_never_offers_pair_tools_or_calls_host_git` | **R17 Arena-local W0 row CLOSED (E470):** real local UDS supervisor/managed writer and PROJECT view through parsed `fa run --role coder`; the actual provider corpus contains none of the three Git tools, `_run_git` has zero calls, and canonical `.git/index` bytes are unchanged. Producer-guard and CLI→registry edge mutants both reach the trapped host-Git call and are killed/restored byte-for-byte. No Docker/live-host acceptance claimed. |
| R18 | `inner_loop/tools/mutation_guard.py::_base_commit:51–69` (`subprocess.run`@58), caller `:115` | coder | host project Git | `tests/test_s5_blackboard_contract.py::test_same_base_commit_conflict_denied` | `…::test_denied_base_commit_lookup_blocks_admission` |
| R19 | `inner_loop/hooks/intent_guard.py::_default_git_runner:272–281` (`subprocess.run`@273) | every gated tool call | host project Git | `tests/test_intent_guard.py` | `…::test_intent_git_failure_never_bypasses_view_admission` |
| R20 | `memory/_safe_walk.py::_git_ls_files:130–175` (`which`@146, `subprocess.run`@151) | memory/search indexing | host project Git | `tests/test_safe_walk.py` | `tests/test_execution_tool_index.py::test_a_managed_search_runs_no_host_git_subprocess` **EXISTING** |
| R21 | `inner_loop/tools/_common.py::git_ls_files:22–53` (`subprocess.run`@40) | memory/search | host project Git | `tests/test_tools_common.py` | same as R20 (EXISTING) |
| R22 | `hygiene/pr_intent.py::_run_git:817–829` (`subprocess.run`@822); `hygiene/hooks/_util.py::resolve_hooks_dir:91–120` (`subprocess.run`@102) | chat `pr_prepare`, readiness hook lookup | host project Git | `tests/test_pr_intent_snapshot.py` | `…::test_pr_prepare_reads_only_a_managed_revision` |
| R23 | `src/fa/workspace/worktree_manager.py::IsolatedWorktreeManager.create_subagent_workspace:196–248`, `cleanup:251–270`, branch probes `:165–193` (host Git producer) | No product caller; `SessionState` reaches only `WorktreeManagerFactory`, which refuses isolated mode. Legacy `spawn_subagent` reached `ensure_subagent_artifact_root` + host `SubagentRunner`, not the isolated manager; that builder is no longer registered by product role registries. Managed R13 remains separately registered at the stage lease edge. | Historical direct-test host-worktree candidate and direct legacy helper; neither is a supported product route or the managed R13 child | Product-edge negatives: `tests/test_managed_registry_binding.py::test_unmanaged_product_run_registries_omit_legacy_host_subagent` and `::test_session_state_rejects_isolated_worktree_without_git_effects`; R13 caller: `tests/test_execution_composition.py::test_subagent_commands_carry_no_proxy_credential`; direct characterization only: `tests/test_worktree_defensive.py`, `tests/test_slice5_6_7_wiring.py`, `tests/test_subagent_termination_wiring.py` | **RETIRED / NOT APPLICABLE TO MANAGED W0 (Q126-A/E469), not PASS.** R23 is removed from Q113's active set only by the explicit E469 scope update; managed R13 remains fail-closed. Shared/artifact safeguards are retained. See the indexed external snapshot and closeout note. |
| R24 | `inner_loop/slice_verification.py::_run_one:330–357` (`subprocess.run`@334), `mutation_overlay:980–1004`, `_run_kill_check:1439–1537`, `capture_test_nodeids:539–581` | verify, kill-check, eval | host pytest | `tests/test_mutation_overlay.py`, `tests/test_verify_slice.py` | `tests/test_e2e_artifact_contract.py::test_kill_proof_requires_a_fresh_operation_and_source_binding` |
| R25 | `cli.py::_cmd_workflow:1496–1537`; `workflow_controller.py::_require_managed_publisher:2281–2294`, `_promote_validated_plan:2297–2328`, admission loop `:2586–2597` | explicit, nested | host workflow stages; validated candidate-to-PLAN promotion is delegated to `BoundPlanPublisher`; missing authority refuses repair | local controls: `tests/test_verify_gate_live.py` CT94 cases, `tests/test_execution_composition.py`; required managed-backend negative oracle: determinate pre-commit refusal leaves canonical PLAN unchanged and never falls back to host write; uncertain outcome is one-shot and requires Q114-A managed-path implementation (legacy `fa workflow` remains unchanged; do not assert old PLAN bytes after uncertainty) |
| R26 | `cli.py::_make_workflow_ctx_provider:1746–1827`, `_build_run_tool_registry:1879–1940`; `workflow_tool.py::_child_run_context:387–403`, handler `:469–534`; `SessionManager.begin_run:537–574` | live chat → nested workflow | child gets a run-log ID but shares the session workspace; direct `run_workflow` call has no child `PlanRef`/`plan_publisher`; coder-containing requests refuse before child allocation | local controls: `tests/test_invoke_workflow_tool.py`, `tests/test_handoff_payload.py`; required negative oracle: parent writer is suspended/pinned before handoff, child cannot access parent authority, and backend denial creates no child project write |
| R27 | `cli.py::_cmd_run:2483` → `_run_cli_stage:1505` → `_drive_stage_with_managed_workspace:1422`; reuse or compose one writer, open `WRITE/PROJECT`, bind `ClientWorkspacePort` + `ManagedBashExecutor`, settle then release only a directly owned writer; callback builds the view-bound role registry before `drive_session` | explicit, chat, workflow stage | local UDS supervisor; managed IO/Bash are bound; Blackboard stamps use admitted `base_revision` plus complete view-read `knowledge/llms.txt`; managed `LearningObserver` is omitted to prevent host-path writes | `tests/test_execution_composition.py::test_direct_chat_keeps_canonical_tree_unchanged_until_stage_publication` (direct acquisition and existing-owner reuse; project-file snapshot unchanged while live, then write appears after publication) plus `tests/test_managed_mutation_metadata.py`, `tests/test_managed_mutation_guard.py`, `tests/test_managed_registry_binding.py` | Local positive and negative CLI oracles pass; R27 remains OPEN under broader S4P1 row closure and final deployed-host acceptance remains `NOT RUN`. |
| R28 | `host_bootstrap.py::_run:24–39`, `main:95–115`; direct production caller `justfile:113` (`agent-bootstrap`), no Python production caller | operator | TCB host; arbitrary current host Bash is not shown to exclude this script | `tests/test_workspace_bootstrap_aliases.py::test_host_bootstrap_delegates_current_just_to_wrapper_and_emits_ready`; `…::test_host_bootstrap_missing_uv_is_stable_and_does_not_call_wrapper` | `…::test_no_model_tool_can_reach_the_host_bootstrap` (planned, absent; requires W1 managed Bash cutover) |

### R13 managed subagent local row (2026-11-04; CLOSED for W0-local DoD)

The full read-only/scratch child is registered at the production chat and
planner/coder workflow callers. Q122 binds a distinct non-interactive READ
profile per child view; role flags remain default-off and independent. The
restricted registry is `fs_read_file` plus stateless `fs_run_bash`; input is
task-only, reports are bounded and written under the run log, and the parent
remains the sole project writer with no handoff or interactive executor reuse.

`tests/test_execution_composition.py::test_subagent_commands_carry_no_proxy_credential`
and `::test_workflow_stage_runs_managed_child_with_local_backend` exercise all
three callers in unavailable, configured-but-unapproved, and approved modes.
Both negative modes produce one real supervisor EXEC request and exact zero
allowed/cell/Bash-fallback/legacy-runner/proxy-credential/project-write effects. The configured
negative uses the real local backend/authority and fails closed with
`UNAPPROVED_PROFILE` before the test-local Docker peer or worker. Approved cases
exercise child execution and report; chat also verifies the 64 MiB quota request,
inner overflow failure evidence in the bounded report, and the private-scratch
write. Producer, caller-edge, and Q124 tmpfs producer mutants are killed and
restored byte-exactly. The 12-module related suite passes **643 passed, 1
expected xfail**. Full command, counters, mutation output and limitations are in
[R13 plan §18](r13-managed-subagent-plan-2026-11-04.md#18-r13w0-local-row-closeout-2026-11-04-arena-local)
and increment E446.

This closes **only the R13 local W0 row**. Global W0 remains OPEN until all
remaining Q113 S4P1 rows pass; W1 has not started. Actual Docker ENOSPC/tmpfs
release and live-host ledger appends remain NOT RUN until the final wave. The
Arena-local test peer/worker is not live-host evidence and no Docker host is a
W0 prerequisite.


### W0 audit refresh (2026-11-04) — R01, R03, R14–R28

**Read-only audit; no row closed.** The inventory's named nodeids for R15–R28 are stale; only `tests/test_execution_tool_index.py::test_a_managed_search_runs_no_host_git_subprocess` was found. The other named nodeids are absent. The actual test names and the production-caller vs component status are:

| Row | Current producer (verified) | Actual test(s) | Type | Gap |
|---|---|---|---|---|
| R01 | `scripts/fa:36–45,58–82,89–181,219–255`; `pyproject.toml:98`; `Dockerfile.fa:97–98`; `SessionManager.resolve_active_session_for_workspace:220`, `.validate_new_workspace_disjoint`; `src/fa/cli.py::_apply_wrapper_session_workspace`, `::_resolve_wrapper_explicit_workspace`, `::_apply_wrapper_stats_workspace`, `::_apply_wrapper_authoring_workspace`, `::_apply_wrapper_config_path` | `tests/test_deploy_scripts.py` installed-controller wrapper tests; `tests/test_execution_composition.py` production `run`/`workflow`/`stats`/`authoring-check`/relative-config/explicit-workspace composition and invalid-selector tests; `tests/test_session_manifest_guards.py`; `tests/test_controller_installed.py` installed-CLI/help | Arena-local W0 production composition CLOSED (E462) | Q128-B reuse/disjoint and command-specific path routing have C1/C2 coverage; installed-wheel wrapper product execution under hostile project CWD/PYTHONPATH is covered by `test_wrapper_product_command_uses_installed_controller_with_hostile_project_env`. CPython 3.13.16 related bank: 270 passed, 12 ShellCheck skips, 1 existing xfail; producer and EDGE mutants killed. Host/deployed acceptance remains NOT RUN. |
| R03 | `scripts/bootstrap/workspace.py:13–23`; `composition.managed_environment_readiness`; `SessionManager._prepare_workspace` → `_managed_workspace_preparer` | `tests/test_workspace_bootstrap_aliases.py::test_workspace_wrapper_imports_checkout_source_and_forwards_argv`; `tests/test_execution_composition.py::test_managed_readiness_probes_both_required_tools_and_settles_same_run`; `tests/test_cli.py::test_cli_blocks_degraded_managed_readiness_without_host_probe_fallback` | wrapper provenance component + actual CLI/SessionManager production caller + real local UDS SupervisorService/WorkspaceAuthority (EXEC backend absent) | **Arena-local W0 row CLOSED by E463.** Managed readiness uses the immutable artifact at `/workspace/.venv` only through the same-run PROVISIONING executor; the checked-out bootstrap wrapper remains TCB/developer-only. Poisoned wrapper/source and host tool markers stay untouched on backend refusal; no Docker/live-host acceptance claimed. |
| R14 | `tools/__init.py:175,230,285,337` | `tests/test_execution_tool_index.py::test_a_managed_registry_ships_no_host_git_tools` | component (fake port) | named `test_profile_construction_failure_registers_no_project_command` absent |
| R15 | `write_file.py:102`; `edit_file.py:160` | `tests/test_execution_tool_port.py::test_tools_built_with_the_port_read_write_and_edit_through_it` | component (real authority + PROJECT view) | named `test_file_handlers_write_through_the_view_only` absent; `tests/test_managed_workspace.py` absent |
| R16 | `workflow_controller._eval_evidence_block`; production caller captures/passes coder sealed revision pair to managed `DIFF_REVISIONS` | `tests/test_eval_evidence_block.py` (formatting/unavailable/component); `tests/test_execution_service.py::test_v2_diff_compares_sealed_manifests_through_a_pinned_read_view`; `tests/test_execution_composition.py::test_workflow_stage_runs_managed_child_with_local_backend[available-unavailable-coder]` and `[refused-unavailable-coder]` | C1 actual `cli._cmd_workflow` + local AF_UNIX `SupervisorService`/`WorkspaceAuthority`; not Docker/live host | **Arena-local W0 R16 CLOSED (E466).** No controller Git; metadata is sorted path/status only, max 128 plus count/truncation. Refusal reaches eval as unavailable and has byte/revision/no-journal no-effect proof. Authority producer mutant (suppress all delta rows) and `_stage_task` caller-edge mutant (omit eval evidence) each killed by the named positive production oracle and restored byte-for-byte. Local bank 589 passed, 1 expected xfail; Ruff/compileall/diff/docs checks recorded in E466. Q129 A is selected; global W0 and W1 boundary unchanged. No Docker/live-host acceptance. |
| R17 | `pair_tools._run_git:28` | `tests/test_subagent_termination_wiring.py` (subagent timeout/ctrl_c; not pair_tools) | component | named `test_pair_tools_use_the_writer_view_and_never_the_canonical_index` absent |
| R18 | `mutation_guard._base_commit:60` | `tests/test_s5_blackboard_contract.py::test_same_base_commit_conflict_denied` (blackboard conflict) | component | named `test_denied_base_commit_lookup_blocks_admission` absent |
| R19 | `intent_guard._default_git_runner:272` | `tests/test_intent_guard.py::test_intent_guard_silently_allows_when_git_fails` (injected failing runner) | component | named `test_intent_git_failure_never_bypasses_view_admission` absent |
| R20 | `_safe_walk._git_ls_files:452` | `tests/test_execution_tool_index.py::test_a_managed_search_runs_no_host_git_subprocess`; `tests/test_safe_walk.py` | component (fake port) | production managed search absent |
| R21 | `_common.git_ls_files:22` | `tests/test_tools_common.py::TestGitLsFiles` | unit | no production caller; dormant/dead code |
| R22 | `pr_intent._run_git:817`; `hooks/_util.resolve_hooks_dir:91` | `tests/test_pr_intent_snapshot.py` (classifier/intent) | component | named `test_pr_prepare_reads_only_a_managed_revision` absent |
| R23 | `worktree_manager.create_subagent_workspace:196` | `tests/test_worktree_defensive.py` (direct temp-repo manager tests); artifact-root tests cover a different route | **2026-11-04 audit snapshot:** no production caller found | **Current 2026-11-06 status:** Q126-A disposition and registry cleanup verified in E469; RETIRED / NOT APPLICABLE TO MANAGED W0, not PASS. Do not conflate the artifact-root helper with Git worktrees or managed R13. |
| R24 | `slice_verification._run_one:330` | `tests/test_mutation_overlay.py`; `tests/test_verify_slice.py` | component | named `test_kill_proof_requires_a_fresh_operation_and_source_binding` absent |
| R25 | `cli._cmd_workflow:1742`; `workflow_controller._require_managed_publisher:2288`; `_promote_validated_plan:2304` | `tests/test_verify_gate_live.py` CT94; `tests/test_execution_composition.py` | component/local | production `fa workflow` managed-publisher negative oracle absent |
| R26 | `cli._make_workflow_ctx_provider:2088`; `workflow_tool._child_run_context:405`; `SessionManager.begin_run:590` | `tests/test_invoke_workflow_tool.py`; `tests/test_handoff_payload.py` | component | production nested-workflow negative oracle absent |
| R27 | `cli._cmd_run:2713`; `_run_cli_stage:1682`; `_drive_stage_with_managed_workspace:1582` | `tests/test_execution_composition.py::test_direct_chat_keeps_canonical_tree_unchanged_until_stage_publication` | production CLI + real local UDS | broader S4P1 row closure + final deployed-host acceptance |
| R28 | `host_bootstrap._run:24`; `main:95`; `justfile:112` | `tests/test_workspace_bootstrap_aliases.py` | component/script-level | named `test_no_model_tool_can_reach_the_host_bootstrap` absent; depends on W1 managed Bash cutover |

**Verified findings (audit snapshot 2026-11-04; status refreshed 2026-11-06).** The named nodeids in the R15–R28 rows are stale; the actual test names are in the table. Most audited tests are component/local, not production-caller. The production-caller evidence exists for R10/R11/R13/R27 and the actual CLI tests; R14–R26 and R28 are component/local or absent. R21 is dormant/dead code. R23 is distinct from the managed R13 child; the 2026-11-04 audit found no caller for the isolated manager. R12/Q125 was resolved by option A and R12's local W0 row is CLOSED (E448); see the Q125 audit for the historical analysis. **Q126-A was selected on 2026-11-06 and its two-path audit/registry cleanup completed in E469: R23 is RETIRED / NOT APPLICABLE TO MANAGED W0, not PASS.** Q113 explicitly gates the remaining 27 applicable rows, R01–R22 and R24–R28; global W0 remains OPEN until all pass. No new Q# is required; other unresolved dependencies remain in Q113/Q119/Q120/Q114/Q90. The historical per-row audit is `notes/w0-r01-r03-r14-r28-audit-2026-11-04.md`; the received full snapshot/handoff is `notes/w0-external-audit-and-r23-handoff-2026-11-04.md`.

**Current acceptance boundary (2026-11-06; through E470).** R01, R03, R12, R13, R14, R15, R16, and R17's scoped Arena-local W0 rows are CLOSED (E462, E463, E448, E446, E451, E464, E466, and E470 respectively). R23 is RETIRED / NOT APPLICABLE TO MANAGED W0 under Q126-A/E469, not PASS; the Q113 active gate explicitly contains R01–R22 and R24–R28. Global W0 remains OPEN until those 27 required rows pass. These local closures/dispositions are not deployed-host acceptance; no Docker/live-host test was run.

### R03 working-tree closeout (2026-11-05; Arena-local W0 row CLOSED, E463)

**Caller and approved route.** The managed production chain is `fa.cli.main`/entrypoint → `SessionManager._prepare_workspace` → `_managed_workspace_preparer` → `composition.managed_environment_readiness` → same-run `ManagedBashExecutor` bound to an `Access.WRITE` `PROVISIONING` view. It probes the approved immutable environment artifact at `/workspace/.venv` using an absolute interpreter path and `-I`; it does not run checked-out `scripts/bootstrap/workspace.py`, `workspace_bootstrap._run_process`, `uv sync`, or hook installation on the controller. This is the trusted-artifact alternative to invoking the project-side wrapper in the cell. `scripts/bootstrap/workspace.py` remains the developer/TCB setup route; explicit-command/standby legacy behavior is unchanged.

**Named row oracle.** `tests/test_cli.py::test_cli_blocks_degraded_managed_readiness_without_host_probe_fallback` drives the actual CLI and SessionManager through a real local UDS `SupervisorService`/`WorkspaceAuthority` with EXEC backend absent. The approved seed contains the real wrapper and a poison `src/fa/workspace_bootstrap.py`; the test sets hostile `PYTHONPATH` and host tool markers. The backend refusal produces degraded readiness and Q118's non-active tombstone; assertions require no poison import, no controller `git`/`uv`/`pytest`/`mutmut`/`python3`, no `.active`, provider, or PTY effect, and unchanged registered source bytes. Supporting test `tests/test_execution_composition.py::test_managed_readiness_probes_both_required_tools_and_settles_same_run` pins the exact trusted artifact command, same namespace/view and settlement order; `::test_unconfirmed_readiness_view_end_withholds_writer_release` retains the fail-closed uncertainty rule. `tests/test_workspace_bootstrap_aliases.py::test_workspace_wrapper_imports_checkout_source_and_forwards_argv` pins the wrapper's explicit checkout-source provenance.

**Verification and mutations.** On CPython 3.13.16 with the rebuilt project environment, the focused three-file bank (`tests/test_execution_composition.py tests/test_cli.py tests/test_workspace_bootstrap_aliases.py`) passed **115 passed, 1 expected xfail**; the four-node direct slice passed **4 passed**. Ruff check/format, `py_compile`, and `git diff --check` passed. Four temporary mutants were individually killed and restored byte-exactly: removing the wrapper's `src` prepend failed the explicit provenance assertion; removing `-I` failed the exact executor-argv assertion; adding a host-side launch of the poisoned checkout wrapper failed the poison-marker assertion; and bypassing SessionManager's degraded-readiness refusal reached the forbidden provider transport. No mutant remains.

**Acceptance boundary.** This closes only R03's Arena-local W0 row. The local UDS test deliberately has no EXEC backend; it proves the production-caller refusal/no-effect route, not a Docker cell or deployed-host positive execution. No Docker/live-host acceptance is claimed. Q126/R23 remains deferred and OPEN; global W0 stays OPEN and W1 has not started.

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


### R01 working-tree closeout (2026-11-05; Arena-local W0 row CLOSED, E462)

The source-backed Q119-A command/workspace matrix was checked against the
wrapper branches and current C1/C2 coverage: run/workflow lifecycle selection,
stats session-filter preservation, authoring workspace/manifest paths, relative
config commands, chunk path anchoring, help/version, host-route exclusions, and
Q127-A's explicit-disposable smoke boundary. Q128-B preserves owner reuse and
only permits a disjoint unowned workspace under the approved root.

`tests/test_controller_installed.py::test_wrapper_product_command_uses_installed_controller_with_hostile_project_env`
executes ordinary `fa inject` through the copied production `scripts/fa`, a
Compose-shape Docker stub, and a real frozen runtime-only installed wheel. It
starts from the active project CWD with hostile `fa`/`sitecustomize` on
`PYTHONPATH`, a project venv, and an `.active` entry naming that project; the
stub models the trusted image
CWD, passes `FA_WRAPPER_ACTIVE_WORKSPACE`, and executes the installed
`controller_entry`. The command output and exact argv are asserted, and no
project poison marker may appear. The actual production C2 workspace/identity,
negative no-effect, and matrix cases remain in
`tests/test_execution_composition.py::test_r01_wrapper_run_resolves_active_workspace_and_revalidates_session`
and the sibling invalid-selector tests.

On CPython 3.13.16, the final related bank passed **270 passed, 12 skipped,
1 expected xfail**. The skips are only ShellCheck-not-installed cases; the
xfail is the existing SLICE4 STEP2 publication boundary. The installed
controller bank passed **60 passed, 81 deselected**. Ruff check/format,
`bash -n scripts/fa`, `py_compile`, and `git diff --check` passed.

Three targeted mutants were killed and restored byte-exactly (wrapper
SHA-256 `4feffe501c47c7b885c4caf0aeb394632a63a88437fa214c8b54cd8f592dfc43`):
removing `-I` executed the project poison and failed the marker oracle; removing
the `FA_WRAPPER_ACTIVE_WORKSPACE` exec argument failed the exact argv oracle;
replacing generic installed-controller dispatch with legacy `first-agent fa`
failed because the installed controller command was absent. No mutant remains.

This closes only R01's Arena-local W0 row. Q126/R23 stays deferred and OPEN;
global Q113 W0 remains OPEN; W1 has not started. Host/deployed acceptance and
live-host ledger-append E2E remain NOT RUN and reserved for the final wave.
