# I03 execution call inventory — source-grounded initial version

Date: 2026-10-15; E230 refresh 2026-10-16. Current source `1132eee`/runtime `a32a72f`.
The initial d910 line table below is historical; refreshed exact symbol ranges follow it.
**State: OPEN.** This is an inspected starting inventory, not proof of complete runtime closure.
Rows name actual producers; proposed replacement APIs are in the I03 spec. Implementer must add
exact new source lines, actual caller traces and test nodeids/results before setting a row closed.
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

| File | Current actual producer ranges | I03 handoff |
| --- | --- | --- |
| `src/fa/cli.py` | `_cmd_run:2166–2515`, `_make_workflow_ctx_provider:1616–1697`, `_build_pty_pool:1923–1951`, `_prepare_managed_workspace:150–159` | Extend current seam; managed IO/execution and preserved invariants per spec §§2.1–7.1 |
| `src/fa/session/manager.py` | `_new_session:262–330`, `_provision_workspace:208–240`, `_check_reverse_workspace_ownership:193–206`, `begin_run:441–478` | Provisioner BEFORE create; reference reuse; preserve run reservation; never delete supervisor-owned committed root |
| `src/fa/inner_loop/tools/workflow_tool.py` | `_child_run_context:387–403`, `_requires_acquisition:382–384`, `build_invoke_workflow_tool:406–587` | Existing non-coder child allocation is already real; reuse it, replace coder-only unavailable branch only after acquisition approval |
| `src/fa/inner_loop/workflow_controller.py` | `_run_stage:1181–1383`, `_effective_controller_route:613–645`, `_git_output:835–864`, `_stage_task:1164–1178` | Extend current seam; managed IO/execution and preserved invariants per spec §§2.1–7.1 |
| `src/fa/inner_loop/coder_loop.py` | `_drive_session_inner:535–2111` | Live local conversation snapshot callback at pre-tool dispatch; strict route final-outcome guard only if Q59 approved |
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
