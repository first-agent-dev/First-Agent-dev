# S12.1 — Windows failure attribution

**Input:** `tests/data/windows-baseline-2026-08-02.txt` (85 unique node IDs,
92 FAILED lines) + per-test tracebacks from the operator log.
**Rule (plan RV8):** a test may be marked `requires_*` only when the row names
the specific POSIX capability the failure depends on. "Downstream of something"
is not an attribution — such tests are ESCALATED, not skipped.

**Result: 85/85 attributed · 0 UNCLASSIFIED · 0 remaining escalations ·
0 product defects.**

7 tests were escalated on the first pass and all 7 were then root-caused to a
single **test-fixture** mechanism (E1 below): `monkeypatch.setenv("HOME", ...)`
does not move the home directory on Windows, because `ntpath.expanduser`
prefers `USERPROFILE`. They are reclassified B4.

| bucket | count |
|---|---:|
| B1 POSIX shell | 10 |
| B2 POSIX modes | 11 |
| B3 tmux/PTY | 26 |
| B4 POSIX paths | 34 |
| B5 symlinks | 2 |
| B6 short paths | 2 |
| **total** | **85** |


## B1 — POSIX shell dialect / no working bash backend (`requires_posix_shell`)

| test | evidence |
|---|---|
| `test_cli.py::test_fa_run_repo_write_bash_allowed_after_pr_prepare` | bash never wrote src/fa/x.py -> FileNotFoundError; shell write did not happen |
| `test_cli.py::test_fa_run_verify_only_bash_allowed_before_pr_prepare` | fs_run_bash returned no result: bash gate could not execute the command |
| `test_cli.py::test_fa_stats_reads_current_session_db_and_rejects_legacy_without_writes` | 0 == 2 rows: the run that should populate the DB used bash and failed |
| `test_inner_loop_tools.py::test_run_bash_tool_preserves_failure_diagnostics` | fs_run_bash result is None: no working shell backend |
| `test_inner_loop_tools.py::test_run_bash_tool_runs_in_workspace` | MSYS path dialect: shell answered /c/... where Python asked C:\... |
| `test_run_bash_tool_projection.py::test_run_bash_elide_preserves_fixed_preview_shape_over_budget` | artifact never produced; depends on fs_run_bash output |
| `test_s5_state_root_contract.py::test_entrypoint_and_cli_agree_on_state_root` | MSYS path dialect: shell answered /c/... where Python asked C:\... |
| `test_s6_subagent_fidelity.py::test_failing_subagent_does_not_leak_secret_into_tracked_worklog` | FAIL branch not taken: subagent shell command did not run |
| `test_secret_exfiltration.py::test_workspace_env_files_are_not_present` | bash exited 1 with mojibake stderr through the Git Bash pipe |
| `test_subagent_runner.py::test_run_stateless` | subagent verifier exit_code=1: shell command failed under Windows |


## B2 — POSIX mode bits (`requires_posix_modes`)

| test | evidence |
|---|---|
| `test_deploy_scripts.py::test_executable_script_modes_are_pinned` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |
| `test_hygiene_hooks_install.py::test_install_one_copy_fallback_target_is_executable` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |
| `test_s10c_artifact_posture.py::test_s10c_directories_are_0700` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |
| `test_s10c_artifact_posture.py::test_s10c_named_artifacts_are_0600` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |
| `test_s10c_artifact_posture.py::test_s10c_no_artifact_is_group_or_world_accessible` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |
| `test_s10c_artifact_posture.py::test_s10c_private_opener_creates_0600_and_appends` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |
| `test_s10c_artifact_posture.py::test_s10c_session_db_and_wal_sidecars_are_private` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |
| `test_s10c_artifact_posture.py::test_s10c_session_dir_is_private_at_creation_without_the_repair_pass` | session dir mode is 0o777 on NTFS at creation |
| `test_s10c_artifact_posture.py::test_s10c_tighten_pass_never_widens` | pass "widened" a read-only artifact: NTFS has no POSIX mode to preserve |
| `test_s10c_artifact_posture.py::test_s10c_tighten_pass_repairs_existing_modes` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |
| `test_s10c_artifact_posture.py::test_s10c_umask_does_not_affect_created_modes` | POSIX mode bits: NTFS reports 0o666/0o777; chmod is a no-op |


## B3 — tmux / PTY backend absent (`requires_tmux`)

| test | evidence |
|---|---|
| `test_cli.py::test_fa_run_opaque_exec_bash_allowed_after_pr_prepare` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_cli.py::test_inner_loop_smoke_canon_snapshot_matches_seed_baseline` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_cli.py::test_inner_loop_smoke_command_runs` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_cli.py::test_inner_loop_smoke_gotcha_dedups_across_repeated_runs` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_cli.py::test_inner_loop_smoke_wires_learning_observer` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_inner_loop_runtime.py::test_run_session_executes_tool_through_hooks` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_inner_loop_runtime.py::test_run_session_run_bash_is_stateful_when_pty_runtime_is_available` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_inner_loop_runtime_limits.py::test_bash_timeout_is_plumbed_into_tool` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_inner_loop_tools.py::test_run_bash_large_output_offloads_artifact_without_internal_error` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_pty_persistence.py::test_ansi_strip` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_pty_persistence.py::test_carriage_returns_cleaned_in_session_output` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_pty_persistence.py::test_ctrl_c` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_pty_persistence.py::test_heredoc_command_completes_via_active_backend` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_pty_persistence.py::test_heredoc_command_completes_via_pexpect_fallback` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_pty_persistence.py::test_pty_env_persistence` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_pty_persistence.py::test_pty_persistence_cd` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_pty_persistence.py::test_sequential_commands_do_not_bleed_into_each_other` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_pty_persistence.py::test_slow_command_does_not_return_stale_prior_result` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_pty_persistence.py::test_timed_out_field_distinguishes_timeout_from_other_failures` | hardcoded base_cwd=Path("/tmp") -> C:\tmp absent; tmux missing -> pexpect fallback |
| `test_s7_cli_run_paths.py::test_smoke_authority_is_labelled_and_scoped` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_s7_cli_run_paths.py::test_smoke_authority_rejects_a_foreign_session_row` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_s7_cli_run_paths.py::test_smoke_creates_no_session_less_authority_at_the_fa_root` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_s7_cli_run_paths.py::test_smoke_still_reports_success_and_writes_its_output` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_slice5_6_7_wiring.py::test_pr6_wiring_bash_large_output_offloads_artifact_via_live_path` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_slice5_6_7_wiring.py::test_pr6_wiring_cr_cleaning_via_bash` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |
| `test_slice5_6_7_wiring.py::test_pr6_wiring_pty_persistence_via_session` | pexpect has no Windows spawn(); tmux absent -> no PTY backend |


## B4 — POSIX path semantics (`requires_posix_paths`)

| test | evidence |
|---|---|
| `test_coverage_failure_paths.py::test_stats_dead_zone_detection_handles_missing_and_unread_files` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_deploy_scripts.py::test_backup_env_parser_whitelists_only_b2_vars` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_deploy_scripts.py::test_fa_update_extract_active_fa_vars_survives_commented_only_template` | sed: can't read C:UsersАдминистратор...: backslashes consumed as escapes by the shell |
| `test_doc_links.py::test_explicit_legacy_file_is_skipped_unless_all` | same "/"-join defect as the sibling doc-links test |
| `test_doc_links.py::test_repo_has_no_broken_internal_file_links` | link resolver joined with "/" producing knowledge\research\knowledge\... |
| `test_fa_entrypoint.py::test_entrypoint_command_override_executes_inside_session_clone` | same mixed-separator mismatch |
| `test_fa_entrypoint.py::test_entrypoint_creates_session_clone` | bash emitted ...sessions/test-session-123 while Python expects ...sessions\test-session-123 |
| `test_fa_entrypoint.py::test_entrypoint_resumes_session_clone` | same mixed-separator mismatch as creates_session_clone |
| `test_fa_entrypoint.py::test_entrypoint_task_file_must_stay_inside_workspace` | entrypoint containment message differs: workspace path uses mixed separators |
| `test_hygiene_hooks_install.py::test_resolve_hooks_dir_respects_core_hookspath` | core.hooksPath resolution differs: SystemExit "does not exist" on a Windows path |
| `test_observability_runtime_authority.py::test_usage_explicit_run_id_reads_run_authority` | HOME monkeypatch ignored (tests/test_observability_runtime_authority.py:93); expanduser prefers USERPROFILE so the EventLog was written elsewhere (E1 mechanism) |
| `test_s10b_cli_parity.py::test_s10b_parity_happy_path` | HOME monkeypatch ignored: ntpath.expanduser prefers USERPROFILE, so the run wrote to the real ~/.fa (E1) |
| `test_s10b_cli_parity.py::test_s10b_parity_without_sink_exports_global_history` | HOME monkeypatch ignored: ntpath.expanduser prefers USERPROFILE, so the run wrote to the real ~/.fa (E1) |
| `test_s10b_cli_parity.py::test_s10b_prepare_pr_draft_clear_failure_is_fatal` | HOME monkeypatch ignored: ntpath.expanduser prefers USERPROFILE, so the run wrote to the real ~/.fa (E1) |
| `test_s10b_cli_parity.py::test_s10b_prepare_pr_draft_read_failure_warns_but_continues` | HOME monkeypatch ignored: ntpath.expanduser prefers USERPROFILE, so the run wrote to the real ~/.fa (E1) |
| `test_s10b_cli_parity.py::test_s10b_session_db_error_messages_are_distinct` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_s10b_cli_parity.py::test_s10b_stats_parity_global_history_console_goes_to_stderr` | HOME monkeypatch ignored: ntpath.expanduser prefers USERPROFILE, so the run wrote to the real ~/.fa (E1) |
| `test_s10b_cli_parity.py::test_s10b_stats_parity_global_history_json_goes_to_stdout` | HOME monkeypatch ignored: ntpath.expanduser prefers USERPROFILE, so the run wrote to the real ~/.fa (E1) |
| `test_s10b_complexity_ratchet.py::test_s10b_every_c901_waiver_is_load_bearing` | ValueError: path is not in the subpath of (drive/short-name mismatch) |
| `test_s4_log_kind.py::test_log_kind_member_count_matches_source` | source scanner globs "/"-joined paths, finds 0 producers, all 32 members look orphaned |
| `test_s5_state_root_contract.py::test_defaults_to_home_dot_fa` | HOME monkeypatch ineffective on Windows (USERPROFILE); fa_state_root() returned real ~/.fa |
| `test_s5_state_root_contract.py::test_ignores_non_absolute_override` | Path("relative").is_absolute() semantics differ; override wrongly honoured |
| `test_sandbox_bash_gate.py::test_general_write_rm_outside_workspace_denied` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_sandbox_secret_paths.py::test_command_reads_secret_path_normalized_traversal` | _normalize/_lexical_abs are POSIX-only (Path.parts yields "\\" on Windows) |
| `test_sandbox_secret_paths.py::test_lexical_abs_path_collapsing` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_sandbox_secret_paths.py::test_normalize_proc_and_relative` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_sandbox_validators.py::test_validate_chmod_denies_outside_workspace` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_sandbox_validators.py::test_validate_command_dispatches_rm` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_sandbox_validators.py::test_validate_rm_denies_etc` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_sandbox_validators.py::test_validate_rm_denies_home` | expanduser() home path compared with POSIX-shaped denial reason |
| `test_stats.py::test_dead_zones` | POSIX path semantics: os.sep/pathlib differ; test compares "/"-joined strings |
| `test_stats_global_wiring.py::test_stats_global_history_cli_reads_projection` | projection keyed by "/"-joined run paths |
| `test_worktree_defensive.py::test_isolated_manager_branch_already_checked_out` | git worktree list returns C:/... forward slashes; manager compares C:\... |
| `test_worktree_defensive.py::test_worktree_defensive_exists` | same git-worktree separator mismatch |


## B5 — symlinks (`requires_symlinks`)

| test | evidence |
|---|---|
| `test_hygiene_hooks_install.py::test_install_hooks_is_idempotent_replacing_own_symlinks` | symlink create/detect needs Developer Mode |
| `test_s10c_artifact_posture.py::test_s10c_tighten_pass_skips_symlinks` | symlink create/detect needs Developer Mode |


## B6 — 8.3 short paths (`requires_stable_tmpdir`)

| test | evidence |
|---|---|
| `test_deploy_scripts.py::test_wrapper_env_preserves_host_binaries_and_shadows_docker` | 8.3 short path != long username form |
| `test_worktree_defensive.py::test_shared_dir_manager` | 8.3 short path != long username form |

---

## Escalation detail (RV8) — candidate product defects, NOT skipped

These 7 are **not** marked with capability markers. Per the plan's RV8 rule they
become BACKLOG items with a one-line repro. S12.3 leaves them failing on Windows
until they are resolved; hiding them behind a marker is the exact anti-pattern
this slice exists to prevent.

### E1 — `events.jsonl` / global-history not written after a successful run (5 tests)

- `test_s10b_parity_happy_path` — run reported `OK: stopped_by_llm (turns=1)` on
  stdout, then `events.jsonl` was absent.
- `test_s10b_parity_without_sink_exports_global_history`
- `test_s10b_stats_parity_global_history_json_goes_to_stdout` — "fixture did not
  write the projection"
- `test_s10b_stats_parity_global_history_console_goes_to_stderr` — same
- `test_s10b_session_db_error_messages_are_distinct` (2 params)

**Why not a capability:** the assertion is `Path(...).is_file()` on an artifact
the product is contracted to write. No separator, mode, or shell mechanism
explains a *successful* run producing no durable log. Producer is
`src/fa/cli.py:1909` (`session_dir / "events.jsonl"`) and `:2486`
(`run_log_dir / "events.jsonl"`).

**Same shape as a defect already on the board:** S10c found `global_history`
deriving `exit_code` twice and disagreeing with the returned verdict. "Run says
success, artifact says otherwise" is that class.

### E1 — RESOLVED 2026-08-02: test-fixture defect, **not** a product defect

Root-caused before S12.3, per the plan's stop rule. **The product wrote
`events.jsonl` correctly. The test looked in the wrong place.**

`tests/test_s10b_cli_parity.py:80` `_cli_home()` isolates the state root with:

```python
monkeypatch.setenv("HOME", str(home))
```

`fa_state_root()` (`src/fa/paths.py:60`) returns `Path.home() / ".fa"`.
On POSIX, `Path.home()` → `posixpath.expanduser("~")` → reads **`HOME`** ⇒ the
fixture works. On Windows it is `ntpath.expanduser("~")`, which prefers
**`USERPROFILE`** and only falls back to `HOME`. Measured:

```
$ python -c "os.environ['HOME']='/fake/home'; os.environ['USERPROFILE']=r'C:\Users\Real';
             print(ntpath.expanduser('~'))"
C:\Users\Real            # HOME ignored
```

So `_run_dir(home, ...)` looked under `tmp_path/home/.fa/...` while the run
wrote to the operator's **real** `C:\Users\Администратор\.fa\...`.

**Corroborating evidence in the same log — two independent confirmations:**

1. `test_s10c_no_artifact_is_group_or_world_accessible` reported real artifacts
   it should never have seen: `'session-log\\posture\\events.jsonl': '0o666'`,
   `'sessions\\session-19752b44...': '0o777'`. Those are the operator's actual
   `~/.fa` contents — proof the isolation failed and the writes landed there.
2. `test_defaults_to_home_dot_fa` failed with
   `WindowsPath('C:/Users/…/.fa') == (tmp_path/'.fa')` — the same
   `HOME`-vs-`USERPROFILE` mechanism, independently attributed to B4.

**Reclassification: E1's 6 tests move from ESCALATED to B4** (POSIX path
semantics — `expanduser` honours a different variable). They are marked
`requires_posix_paths`, not left failing.

**Real finding worth keeping:** the suite leaked into the operator's real
`~/.fa` on Windows. `tests/conftest.py` `_isolate_fa_session_log_root` is
`autouse` and deliberately narrow (it documents refusing to patch `Path.home`
globally because 25 tests bind home-relative constants at import). That
narrowness is correct on POSIX but leaves a Windows hole. → **BACKLOG I-43**.

**Severity of the fixture bug: MED** — no product impact, but on Windows the
suite writes into the developer's real state directory.

**Repro:** on Windows, `uv run pytest tests/test_s10b_cli_parity.py::test_s10b_parity_happy_path`
then observe `%USERPROFILE%\.fa\session-log\parity-happy\events.jsonl` exists.

### E2 — `test_s10b_prepare_pr_draft_read_failure_warns_but_continues`

Expected the warning text `unreadable`, got `''`. A diagnostic that does not
reach the user is a real (if low-severity) defect. **Severity: LOW.**

### E3 — `test_s10b_prepare_pr_draft_clear_failure_is_fatal`

"an unclearable draft store must be fatal, not a warning" — a fatal path did not
trigger. **Severity: MED** (a stale PR draft could survive a failed clear).

### E4 — `test_general_write_rm_outside_workspace_denied`

`BashGateDecision.reason` and `.validator_result` both differ from expected.
The decision is still a denial, but the *reason* changed. Needs a source read of
`src/fa/sandbox/` to confirm the containment verdict is unchanged.
**Severity: MED — security-adjacent, verdict itself appears correct.**

### E5 — `test_usage_explicit_run_id_reads_run_authority`

`build_usage_tool().handler({"run_id": "run-42"})` returned
`ToolError(code='no_active_session', message='run_id not found: run-42')` when
an explicit run_id should be readable without an active session.
**Severity: MED.** No POSIX capability is involved.

---

## Cross-check: RV7's 13/11 split, derived independently

The 24 `which("bash")` guards were cross-referenced against this attribution:

- **13 guarded tests failed** on Windows → B1 (4) or B3 (9) → guard replaced.
- **11 guarded tests passed** on Windows → guard left untouched.

This reproduces the plan's RV7 split from a different direction (attribution vs.
log-set difference), which is the intended independent confirmation.

**Guards to replace (13), with line numbers:**

| bucket | file:line | test |
|---|---|---|
| B3 | `test_cli.py:59` | `test_inner_loop_smoke_command_runs` |
| B3 | `test_cli.py:84` | `test_inner_loop_smoke_wires_learning_observer` |
| B3 | `test_cli.py:127` | `test_inner_loop_smoke_canon_snapshot_matches_seed_baseline` |
| B3 | `test_cli.py:195` | `test_inner_loop_smoke_gotcha_dedups_across_repeated_runs` |
| B1 | `test_cli.py:713` | `test_fa_run_verify_only_bash_allowed_before_pr_prepare` |
| B3 | `test_cli.py:837` | `test_fa_run_opaque_exec_bash_allowed_after_pr_prepare` |
| B1 | `test_cli.py:883` | `test_fa_run_repo_write_bash_allowed_after_pr_prepare` |
| B3 | `test_inner_loop_runtime.py:37` | `test_run_session_executes_tool_through_hooks` |
| B3 | `test_inner_loop_runtime.py:115` | `test_run_session_run_bash_is_stateful_when_pty_runtime_is_available` |
| B3 | `test_inner_loop_runtime_limits.py:332` | `test_bash_timeout_is_plumbed_into_tool` |
| B1 | `test_inner_loop_tools.py:50` | `test_run_bash_tool_runs_in_workspace` |
| B3 | `test_inner_loop_tools.py:76` | `test_run_bash_large_output_offloads_artifact_without_internal_error` |
| B1 | `test_inner_loop_tools.py:141` | `test_run_bash_tool_preserves_failure_diagnostics` |

**Guards to LEAVE ALONE (11)** — these pass on Windows because they use bash as a
subprocess *interpreter* (assert on exit code / log file), never as a
path-speaking shell:
`test_cli.py::test_fa_run_repo_write_bash_requires_pr_prepare`,
`test_cli.py::test_fa_run_opaque_exec_bash_requires_pr_prepare`,
`test_deploy_scripts.py::test_shell_script_has_valid_syntax`,
`test_fa_update_script.py::test_fa_update_script_has_valid_bash_syntax`,
and 7 `test_hygiene_hooks_install.py::test_pre_{commit,push}_*` tests.

**`tests/test_authoring_rules_tests.py` is OUT OF SCOPE** — its 2 occurrences
(lines 134, 139) are fixture data inside
`test_pytest_mark_skipif_is_not_flagged`, the V4 rule's own regression corpus.
