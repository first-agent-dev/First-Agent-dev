INTENT: FIX
CLASS: REPAIR
INVARIANT: Affects: Dockerized FA runtime must default to inspectable stand-by, run autonomous tasks only when explicitly requested, preserve role/resume state, and remain debuggable after success, partial failure, or crash.

DEGREE-OF-FREEDOM CLOSED: The previous container story mixed a placeholder `sleep infinity` image with a proposed `FA_TASK`-triggered wrapper that could accidentally auto-run and/or re-run under `restart: unless-stopped`. This PR makes auto-run explicit (`FA_AUTO_RUN=1`), validates inputs before launching the agent, runs `fa run` as a child process, records status, and always returns the container to stand-by for inspection.

DETERMINISTIC MECHANISM: `scripts/fa-entrypoint.sh` gates one-shot execution on truthy `FA_AUTO_RUN`, validates task/run configuration, launches `fa run` as a child process, writes `/workspace/.fa/entrypoint-status.txt`, captures the child exit code, and then `exec sleep infinity` instead of exiting the container.

## Summary

This PR finalizes the Dockerized FA runtime so it is usable for real coding work inside an Ubuntu-based container:

- manual `docker exec` operation is the safe default;
- auto-run is explicit, one-shot, status-recorded, and restart-loop safe;
- live bind-mounted source edits work without rebuilding the image;
- role-aware FA sessions and `--resume` workflows remain usable in the container;
- bad startup inputs fail safely while keeping the container inspectable;
- resumed runs append to `events.jsonl` with monotonic event ids.

## Architectural Review / Findings

### What was already good

- Role-aware prompts already existed and `drive_session()` already passes `role` into `build_system_message(system_prompt_extra, role=role)`.
- Planner/eval registries already correctly expose read-only operational tools (`fs.read_file`, `fs.run_bash`) while `pr.prepare` is still registered later by the CLI for work-log updates.
- `fa run --resume` already preserves a prior PR draft, injects it into the system prompt, and uses `getattr(args, "resume", False)` for older tests.

### Blockers found and fixed

1. **Auto-run was too easy to trigger.**
   A wrapper that runs whenever `FA_TASK` is set is dangerous because compose env files are persistent and `restart: unless-stopped` can re-run the same task after every restart. Auto-run is now gated by `FA_AUTO_RUN=1`; `FA_TASK` alone leaves the container in stand-by.

2. **The image did not install the package/runtime dependencies.**
   With only a bind-mounted `/workspace`, `fa` was not guaranteed to exist in a fresh container. The Dockerfile now builds an image-owned venv at `/opt/fa-venv` using `uv sync --frozen --no-dev`, while `PYTHONPATH=/workspace/src` lets live source edits override the image copy.

3. **Entrypoint script was excluded from Docker build context.**
   `.dockerignore` excluded all `scripts/`. It now re-includes only `scripts/fa-entrypoint.sh` and `README.md` needed by the package metadata/build.

4. **Invalid env inputs needed fail-safe behavior.**
   The entrypoint now validates task emptiness, mutually exclusive `FA_TASK`/`FA_TASK_FILE`, task-file containment inside `/workspace`, workspace writability, `FA_MAX_TURNS`, and `FA_RUN_ID` before launching `fa run`.

5. **CLI configuration failures could surface as tracebacks.**
   `_cmd_run()` now rejects empty tasks, invalid max turns, unsafe run ids, and catches config-load errors as clean exit-code-2 user errors.

6. **Resume event logs could duplicate event ids.**
   `EventLog` now seeds `_next_id` from an existing log file, so appending to an existing run id during resume does not restart at `ev-000001`.

7. **Role prompt alias had a latent argument-order bug.**
   `build_system_message_from_role()` now calls `build_system_message(extra, role=role)` instead of passing the role as `extra`.

## Code Changes

### Docker/runtime

- `Dockerfile.fa`
  - Adds `/opt/fa-venv` runtime environment via `uv sync --frozen --no-dev`.
  - Sets `PATH=/opt/fa-venv/bin:...` and `PYTHONPATH=/workspace/src`.
  - Copies `scripts/fa-entrypoint.sh` into `/usr/local/bin/`.
  - Replaces placeholder `CMD ["sleep", "infinity"]` with `ENTRYPOINT ["/usr/local/bin/fa-entrypoint.sh"]`.

- `.dockerignore`
  - Keeps scripts generally excluded, but re-includes `scripts/fa-entrypoint.sh`.
  - Re-includes `README.md` so package metadata has a readme during image build.

- `docker-compose.fa.yml`
  - Adds `PYTHONPATH=/workspace/src`, `FA_WORKSPACE=/workspace`, and `FA_CONTAINER_NAME=first-agent`.
  - Documents that auto-run is opt-in via `.env.fa`/environment.
  - Changes healthcheck from “Python exists” to `fa --version` so it verifies the installed console script and imports.

- `scripts/fa-entrypoint.sh`
  - Command override mode runs first and always `exec`s the provided command.
  - Default mode is stand-by (`sleep infinity`) for manual `docker exec` workflows.
  - Auto-run requires truthy `FA_AUTO_RUN`.
  - Supports `FA_TASK` or `FA_TASK_FILE` (mutually exclusive).
  - Requires task files to resolve inside `/workspace`.
  - Supports `FA_ROLE`, `FA_CONFIG`, `FA_MAX_TURNS`, `FA_RUN_ID`, and `FA_RESUME`.
  - Generates a safe default Docker run id if none is provided.
  - Writes status rows for `RUNNING`, `SUCCESS`, `FAILED`, `INVALID_CONFIG`, and `TERMINATED`.
  - Records task SHA-256 and short preview rather than only dumping full task text.
  - Forwards SIGTERM/SIGINT to the child `fa run` process and writes `TERMINATED` status.
  - Always transitions to inspectable stand-by after auto-run completion/failure.

### CLI/runtime correctness

- `src/fa/cli.py`
  - Adds `_valid_run_id()` and rejects unsafe run ids (`[A-Za-z0-9_.-]{1,128}`).
  - Rejects empty/whitespace-only `--task`.
  - Rejects `--max-turns < 1`.
  - Catches `ConfigurationError`, `EvalFamilyConflictError`, and `OSError` around model-config load and returns exit code `2` with a clean error.

- `src/fa/inner_loop/state.py`
  - `EventLog` now continues event ids when appending to an existing `events.jsonl`.

- `src/fa/inner_loop/prompt.py`
  - Fixes `build_system_message_from_role()` argument forwarding.
  - Keeps `__all__` sorted.

### Docs/templates

- `.env.fa.template`
  - Documents `FA_AUTO_RUN`, `FA_TASK`, `FA_TASK_FILE`, `FA_ROLE`, `FA_MAX_TURNS`, `FA_RUN_ID`, `FA_RESUME`, and `FA_CONFIG`.
  - Recommends `FA_TASK_FILE` for long plan-following workflows.

- `README.md`
  - Documents stand-by-first operation and one-shot auto-run behavior.

- `knowledge/SETUP_AIO.md`
  - Replaces the old “placeholder sleep infinity” note with the final entrypoint semantics.
  - Documents status-file location, restart-loop prevention, task-file preference, and role/resume usage.

## Tests Added / Updated

- `tests/test_fa_entrypoint.py`
  - Stand-by does not auto-run when only `FA_TASK` is set.
  - Auto-run executes child once and writes `SUCCESS`.
  - Blank task writes `INVALID_CONFIG` and does not run child.
  - `FA_TASK_FILE` inside workspace is accepted.
  - `FA_TASK_FILE` outside workspace is rejected.

- `tests/test_cli.py`
  - Empty `--task` returns exit code 2.
  - Unsafe `--run-id` returns exit code 2.
  - Missing config/env key returns exit code 2 without traceback.

- `tests/test_inner_loop_audit_sink.py`
  - Resumed `EventLog` appends monotonic event ids.

- `tests/test_prompt.py`
  - `build_system_message_from_role()` preserves role and extra text.

## Validation Performed

- `bash -n scripts/fa-entrypoint.sh` — pass.
- `PYTHONPATH=src pytest -q -o addopts=''` — `1064 passed`.
  - Note: sandbox environment did not have pytest-cov initially, so repo coverage addopts were disabled for this run.
- `python -m ruff check src/fa/cli.py src/fa/inner_loop/prompt.py src/fa/inner_loop/state.py tests/test_cli.py tests/test_fa_entrypoint.py tests/test_inner_loop_audit_sink.py` — pass.
- `PYTHONPATH=src python -m mypy src/fa/cli.py src/fa/inner_loop/prompt.py src/fa/inner_loop/state.py tests/test_fa_entrypoint.py tests/test_inner_loop_audit_sink.py` — pass.
- `docker-compose.fa.yml` parsed with PyYAML — pass.
- `docker compose config` could not be run in this sandbox because Docker Compose is unavailable; run it on the deployment host before merge/deploy.

## Edge Case Behavior

### Successful task completion

`fa run` exits 0. Entrypoint writes:

```text
status=SUCCESS
exit_code=0
```

Then the container transitions to `sleep infinity` for post-run inspection.

### Agent crash or Python/runtime exception

If `fa run` exits non-zero, the wrapper captures the exit code, writes:

```text
status=FAILED
exit_code=<child exit code>
```

Docker logs retain stdout/stderr, `events.jsonl` remains under `/workspace/.fa/runs/<run_id>/`, and the container stays alive.

### Invalid `FA_TASK` inputs

- `FA_AUTO_RUN=1` with empty/whitespace `FA_TASK` -> `INVALID_CONFIG`, no child process launched.
- Both `FA_TASK` and `FA_TASK_FILE` set -> `INVALID_CONFIG`, no child process launched.
- `FA_TASK_FILE` outside `/workspace` -> `INVALID_CONFIG`, no child process launched.
- `FA_TASK` set without `FA_AUTO_RUN=1` -> stand-by only; no accidental execution.

### Missing environment variables

Provider/model config validation fails inside `fa run`; CLI prints a clean `fa run: configuration error: ...` message and exits 2. Entrypoint records `FAILED` with `exit_code=2`, then enters stand-by.

### Partial failure during long autonomous execution

If the agent hits iteration cap, provider-chain exhaustion, request-shape errors, hook denial, or other non-zero terminal states, the wrapper records `FAILED` with the exact exit code and leaves the container alive. Operators inspect:

```bash
cat /workspace/.fa/entrypoint-status.txt
ls -la /workspace/.fa/runs/<run_id>/
docker compose -f docker-compose.fa.yml logs --tail=200 first-agent
```

### Post-run inspection/debugging

The container does not exit after auto-run. Operators can use:

```bash
docker exec -it first-agent bash
cat /workspace/.fa/entrypoint-status.txt
fa run --task "continue from the work log" --workspace /workspace --role coder --run-id <same-id> --resume
```

## Operational Rules

### Stand-by mode (default)

Do nothing special. Start the service/container and run commands manually:

```bash
docker compose -f docker-compose.fa.yml up -d
docker exec -it first-agent bash
fa run --task "inspect and plan" --role planner --workspace /workspace
```

`FA_TASK` alone is intentionally ignored unless `FA_AUTO_RUN=1` is also set.

### Auto-run mode (explicit, one-shot)

Set exactly one task source:

```env
FA_AUTO_RUN=1
FA_TASK_FILE=tasks/implement-login.md
FA_ROLE=coder
FA_RUN_ID=login-workflow-001
FA_MAX_TURNS=24
FA_RESUME=1
```

Then start/recreate the container. It will run once, write status, and return to stand-by.

### Role-switch workflow

Recommended plan-following sequence:

```bash
fa run --role planner --run-id feature-x --task "plan feature X" --workspace /workspace
fa run --role coder   --run-id feature-x --resume --task "implement the planner work log" --workspace /workspace
fa run --role eval    --run-id feature-x --resume --task "verify the implementation" --workspace /workspace
```

Planner/eval have read-only filesystem registries plus `pr.prepare`; coder has the mutating baseline registry plus `pr.prepare`.

## Follow-ups / Out of Scope

- Run `docker compose -f docker-compose.fa.yml config` and a real image build on the deployment host/CI runner.
- Add a Docker-enabled CI smoke job if the CI environment supports Docker-in-Docker or a privileged runner.
- Keep the LLM cache/usage optimization tiers as a separate PR; mixing prompt-cache instrumentation with container-runtime stabilization would make review harder and violate the small-coherent-change rule.
