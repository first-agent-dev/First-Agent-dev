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

---

## Open e2e-only risks, recorded now so they are not rediscovered live

- **Admission timing.** CT53's purity is proven structurally, by walking the functions' AST.
  That proves they *can* run before the coder stage; only a live run proves they *do*.
- **Cost.** Phase B does not start until Phase A yields a measured per-command cost from a
  real run (E130). That measurement has no in-repo proxy.
- **Observe-vs-enforce.** The switch recorded in `verification.json` (E132, CT77c) changes
  nothing a unit test can see; its first real exercise is the live host.
