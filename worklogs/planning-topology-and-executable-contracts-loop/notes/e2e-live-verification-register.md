# E2E live-host verification register — I02

**Purpose.** Operator instruction, 2026-10-08: *every producer created by this plan must be
marked for a future end-to-end test, and all of them verified with fixtures on the live host.*
This file is that mark. One row per producer, carrying what the host fixture has to arrange
and what it has to observe — so the e2e suite can be written from this register alone, without
re-deriving any of it from the code.

**Status vocabulary.** `unit` = proven by in-repo tests and a kill-check. `e2e` = proven on the
live host. A producer is not finished until it is `e2e`.

**Why in-repo green is not enough here.** Every producer below either spawns a process, reads
an environment the test harness fakes, or depends on a workspace layout that only the deployed
container actually has (`/opt/first-agent/src`, `/opt/fa-venv`, `/sessions/<id>/`,
`workspace_bootstrap`'s prebuilt `.venv`). Those are exactly the conditions a `tmp_path`
fixture cannot reproduce, and exactly where a silent no-op would hide.

---

## Standing fixture requirements (apply to every row)

1. A real session workspace at `/sessions/<id>/` with the bootstrapped `.venv`, **not** a
   `tmp_path` tree — the gate's whole claim is that it verifies the coder's tree.
2. A plan file containing at least one `## SLICE#` section with a `verify` fence, passed with
   `--plan`; an invocation including the `coder` role requires it (E131) and nothing infers it.
3. Assertions read from the persisted artifacts the operator reads —
   `~/.fa/session-log/<run_id>/{eval_report,flow_state}.json`, host path
   `/srv/first-agent/state/session-log/<run_id>/` — never from in-process objects.
4. Observe-mode first (E132): the first live run must record and not enforce.

---

## SLICE1 — the command runner

| Producer | Unit proof | What the host fixture must arrange | What it must observe | Status |
| :--- | :--- | :--- | :--- | :--- |
| `run_commands` | CT44 kill PROVEN | a slice whose `verify` fence holds one passing and one failing command | both results recorded, in declared order, with the real exit codes | unit |
| `_run_one` | CT44/CT49d | a command that exits non-zero | `outcome=FAIL`, **not** ERROR — the command refused, the harness did not fail | unit |
| `_timeout_result` | CT45 kill PROVEN | a `verify` command that sleeps past the budget | `ERROR`, `exit_code=None`, elapsed seconds recorded; the run continues | unit |
| `_deadline_result` | CT47 | a slice with more commands than the run budget allows | the unreached commands are `ERROR` with `duration_s == 0.0`, never `PASS` | unit |
| `_spawn_failure_result` | CT46, C4-driven | a `verify` command naming a binary absent from the image | `ERROR`, never `FAIL`; the message names the command | unit |
| `_build_env` | CT46/CT49b | a workspace whose `.venv/bin` holds a shim that the image's `/opt/fa-venv` does not | the shim runs — proving workspace-first `PATH`, not image-first | unit |
| `_pin_uv_environment` | CT49e kill PROVEN | a `verify` command of the form `uv run pytest …`, with a stale `UV_PROJECT_ENVIRONMENT` exported in the parent | `uv` resolves the **session's** venv, and no lockfile sync is attempted offline | unit |
| `_workspace_cwd` | CT49c kill PROVEN | a `verify` command that prints `pwd` | the session workspace, not `/opt/first-agent` | unit |
| **`PYTHONPATH` survival** | CT49b kill PROVEN | a workspace copy of a module that also exists in the baked image, differing observably | the **workspace** version is imported. *The highest-value row in this file*: if it fails, the gate passes no matter what the coder wrote | unit |

## SLICE2 — kill directives

| Producer | Unit proof | What the host fixture must arrange | What it must observe | Status |
| :--- | :--- | :--- | :--- | :--- |
| `parse_kill_directives` | CT50 kill PROVEN | a planner-authored plan (model-written, not a fixture) carrying `kill:` lines | the directives are recovered from the artifact the planner actually produced | unit |
| `validate_kill_directives` | CT52 kill PROVEN | a plan with a malformed directive, submitted at admission | the run is **blocked before the coder stage starts** — the scheduling claim CT53 makes and no in-repo test can observe | unit |
| `_near_miss` | CT51 kill PROVEN | a plan with `kill-check:` instead of `kill:` | a `kill-directive-near-miss` reaches the operator's console and the persisted report | unit |
| `_split_dotted` | CT50b (parse half) | a plan naming `Class.method` as a symbol | resolution succeeds; no false `PRODUCER_ABSENT`. **Kill-check deferred**: CT50b names `_resolve_symbol`, which is SLICE3's AST concern and does not exist yet | unit (partial) |

## SLICE4 — the mutation sandbox

| Producer | Unit proof | What the host fixture must arrange | What it must observe | Status |
| :--- | :--- | :--- | :--- | :--- |
| `mutation_overlay` | CT60 kill PROVEN | a kill-check against a real `/sessions/<id>/` workspace, whose `src` is a full clone rather than a four-file fixture | the overlay is built and removed; `git status --porcelain` in the session clone is unchanged. **Also the first real measurement of copy cost** — 15 ms for this repo's 2.4 MB / 163 files, but a session clone is the number Phase B's budget actually needs | unit |
| `_copy_src` | CT60/CT63 | a workspace whose `tests/` contains the oracle for the contract under check | `tests/` is absent from the overlay, so the mutation provably cannot reach its own judge | unit |
| `_overlay_target` | containment kill PROVEN (5 oracles) | a planner-authored directive whose path escapes `src` — including via a symlink the image itself ships | `OverlayError`, and the operator's file unmodified afterwards. Worth doing live because the image's `src` has real symlinks and a `tmp_path` fixture's does not | unit |
| `_prepend_pythonpath` | CT61 kill PROVEN | a session container where `PYTHONPATH` already carries `<workspace>/src` from `fa-entrypoint.sh:237` | the overlay is first **and** the workspace entry survives behind it. The in-repo test supplies that inherited value by hand; only the container proves the entrypoint really set it | unit |
| `_overlay_env` | CT61 | a kill-check and a plain verify command in the same run | both see the same scrubbing, `PATH` and `uv` pin — the kill-check must judge the same program the gate approved | unit |
| `check_kill_directive_ownership.py` | CT83, planned | the real plan folder at a moment when a slice has just been ticked | the exit code is non-zero and the message names the contract, the slice and the symbol | planned |
| `apply_kill` | CT55/CT57 kills PROVEN | a directive naming a real producer in the session clone, applied to the file as deployed at `/sessions/<id>/src/...` | `targets == 1`, `edits >= 1`, and the returned text still imports inside the overlay | unit |
| `_resolve_targets` | Q47 exactness kill PROVEN (1F) | a plan whose directive is written against a module that was refactored since -- the symbol moved into a class | `targets == 0` -> `PRODUCER_ABSENT`, naming the symbol; no silent match on the same method name elsewhere | unit |
| `_Silence` | CT56 kill PROVEN (9F) | a real producer called several times inside one function in shipped code | every call silenced, `edits` equal to the count a human finds by reading | unit |
| `KillApplication.__post_init__` | kill PROVEN (2F) | nothing -- it is an internal assertion | never fires in a live run; if it does, the bug is in `apply_kill`, not in the plan | unit |
| `DEFAULT_PROBE_TIMEOUT_SECONDS` | Q46(b), kill PROVEN | a session container under real I/O load, with a cold import of the heaviest module a kill-check will target | the probe completes well inside 30 s. If it ever does not, the budget is wrong -- but `ERROR` after 30 s is a diagnosis, where `ERROR` after 600 s is an outage | unit |
| `_assert_overlay_wins` | CT62 producer kill PROVEN; **directive deferred** | the deployed image, where `/opt/first-agent/src` is installed and an absolute path really is on `sys.path` — the condition that produced E125/D1 | `PASS`, proving the overlay beat the installed package. **The single highest-value row in this file**: if it reports `ERROR` on the real host, Phase B cannot ship, and that is exactly what it is for. CT62's own directive names `_run_kill_check`, which arrives in SLICE5 | unit |
| `_run_kill_check` | CT66/CT67/CT82, 8 hand-mutants killed | the deployed image: a real contract, its real test, and `/opt/first-agent/src` installed, so the overlay has something to beat | one of PROVEN / VACUOUS / PRODUCER_ABSENT / ERROR, and the probe gating it. The unit proof runs against a throwaway src-layout workspace with no installed package -- precisely the condition E125/D1 says is unrepresentative | planned |
| `_compare_baseline` | CT68; green→red, red→red, absent-T0, absent-now and unavailable-report oracles; 9 STEP3 hand-mutants killed across the comparator/classifier | the coder host runs baseline and current `TESTS:` paths with harness-issued `--junitxml` | only T0-green/current-red matching nodeids appear in the regression set; a new nodeid and an absent row do not | planned |
| `pytest_itemcollected` / `fa_pytest_nodeid` | CT68/CT69; real class + parametrized JUnitXML oracle, 2 hand-mutants killed | coder host runs harness-issued `pytest -p fa.inner_loop.junit_nodeid_plugin --junitxml=...` on the deployed workspace | every executed testcase has exactly one property equal to `Item.nodeid`; missing/duplicate property is an unusable report, never a reconstructed id | planned |
| `_producer_absent` | CT67 producer kill; classifier oracle | a real slice whose declared producer target does not exist in the deployed clone | final `PRODUCER_ABSENT`, with contract and target retained in its `KillCheck`; never collapsed into VACUOUS | planned |
| `_classify` | CT65-CT68; STEP3 precedence matrix | a real workflow with command FAIL plus a T0-green/current-red nodeid, and a separate green command with a regression | first case routes as `FAILING`; second as `REGRESSION`; command/kill phase errors route as `ERROR` | planned |
| `_producer_absent` | CT67 producer kill; classifier oracle | a real slice whose declared producer target does not exist in the deployed clone | final `PRODUCER_ABSENT`, with contract and target retained in its `KillCheck`; never collapsed into VACUOUS | planned |
| `_classify` | CT65-CT68; STEP3 precedence matrix | a real workflow with command FAIL plus a T0-green/current-red nodeid, and a separate green command with a regression | first case routes as `FAILING`; second as `REGRESSION`; command/kill phase errors route as `ERROR` | planned |
| `SliceVerdict` | STEP1 gate, `len == 7` | a run that reaches more than one member | the member a human reads matches the member a machine branched on; no synonym invented at the report boundary | unit |
| `KILL_CHECK_VERDICTS` | kill PROVEN (3 members rejected) | nothing -- it is an internal assertion | never fires live; if it does, a caller is minting a per-contract vocabulary the reports do not share | unit |
| `KillCheck.__post_init__` | kill PROVEN (2F) | nothing -- internal assertion | never fires live; a non-PROVEN verdict with an empty `detail` is an alarm no operator can act on | unit |
| `_module_name` | kill PROVEN (5F), 6 parametrised paths | the deployed image, where the module also exists as an installed absolute path | the derived name is the name the probe resolves. A disagreement reads as a probe failure (`ERROR`), never as a pass -- the one way this helper can be wrong is already fail-safe | planned |
| `KILL_CHECK_COMMAND` | used by every `_run_kill_check` oracle (seam patched to this interpreter) | the coder's real uv project at `/sessions/<id>/`, with `UV_PROJECT_ENVIRONMENT` pinned | `uv run pytest` resolves to the workspace venv. **The constant is never exercised verbatim by any unit test** -- the hermetic fixture substitutes it, so the live run is its first real execution | planned |
| `run_commands(env=...)` | kill PROVEN (injected env reaches the subprocess) | a kill-check on the host, where the overlay env differs from `_build_env` by `PYTHONPATH` alone | the subprocess sees the overlay's `PYTHONPATH`, so the kill-check and the verify it judges are the same program (CT61) | planned |

---

## Open e2e-only risks, recorded now so they are not rediscovered live

- **Admission timing.** CT53's purity is proven structurally, by walking the functions' AST.
  That proves they *can* run before the coder stage; only a live run proves they *do*.
- **Cost.** Phase B does not start until Phase A yields a measured per-command cost from a
  real run (E130). That measurement has no in-repo proxy.
- **Observe-vs-enforce.** The switch recorded in `verification.json` (E132, CT77c) changes
  nothing a unit test can see; its first real exercise is the live host.
