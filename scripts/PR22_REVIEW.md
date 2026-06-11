# PR #22 Review — "loop wired into docker"

**Reviewer:** Principal DevOps Engineer / Senior Runtime Engineer / AI Agent Systems Architect  
**PR URL:** https://github.com/first-agent-dev/First-Agent-dev/pull/22  
**Branch:** `devin/2026-06-10-loop-entrypoint-from-main`  
**Date:** 2026-06-11

---

## 1. Baseline Findings

### What PR #22 Currently Does

The PR introduces five files/areas of change:

1. **New file: `scripts/fa-entrypoint.sh`** — Dual-mode entrypoint script:
   - If `FA_TASK` is set → runs `fa run --task "$FA_TASK"` (auto-run mode)
   - If `FA_TASK` is unset and `$@` is non-empty → runs `$@` (command override)
   - If `FA_TASK` is unset and `$@` is empty → `sleep infinity` (stand-by mode)
   - Sets `PYTHONPATH=/workspace/src` as a prepend

2. **`Dockerfile.fa` changes** — Adds build-time `fa` CLI installation:
   - Copies `pyproject.toml`, `uv.lock`, `README.md`, `src/` to `/tmp/fa-build/`
   - Runs `uv pip install --system .` to install the `fa` console script
   - Symlinks the `fa` binary to `/usr/local/bin/fa`
   - Sets `ENV PYTHONPATH=/workspace/src`
   - Copies and enables `scripts/fa-entrypoint.sh` as `ENTRYPOINT`
   - Changes `CMD` from `["sleep", "infinity"]` to `[]`

3. **`docker-compose.fa.yml` changes** — Adds env vars:
   - `FA_TASK`, `FA_ROLE`, `FA_MAX_TURNS`, `FA_RUN_ID` (unresolved references, values from `.env.fa` or docker run `-e`)

4. **`knowledge/SETUP_AIO.md`** — Documents the new dual-mode entrypoint behavior, including the restart-loop caveat

5. **`HANDOFF.md`** — Updates current-state blurb

6. **`scripts/fa.service`** — Removes `Requires=docker.service`

7. **`.dockerignore`** — Refines exclusion patterns to allow `scripts/fa-entrypoint.sh` and `README.md` through

### Where the PR Is Correct

| Area | Assessment |
|------|------------|
| Dual-mode entrypoint concept | ✅ Correct design. Stand-by + auto-run is the right split. |
| Build-time `fa` CLI installation | ✅ Correct approach. Copies only what's needed to `/tmp/fa-build/`. |
| `PYTHONPATH=/workspace/src` | ✅ Correct. Ensures live bind-mount takes precedence over baked snapshot. |
| `ENTRYPOINT ["/usr/local/bin/fa-entrypoint.sh"]` + `CMD []` | ✅ Correct Docker semantics. |
| `.dockerignore` refinement | ✅ Correct. `!scripts/fa-entrypoint.sh` and `!README.md` exceptions are well-placed. |
| `scripts/fa.service` fix | ✅ Correct. `Requires=docker.service` was a bug (system-level unit unavailable in user context). |

### Where the PR Is Incomplete or Defective

| Area | Assessment |
|------|------------|
| **Restart-loop problem** | ❌ CRITICAL. Acknowledged in docs but NOT fixed in code. |
| **`fa run` exit code handling** | ⚠️ MEDIUM. Entrypoint uses `exec` — if `fa run` exits, container exits, Docker restarts. |
| **`PYTHONPATH` in Dockerfile ENV** | ⚠️ LOW. The `ENV PYTHONPATH=/workspace/src` layer means `/workspace/src` is always in PYTHONPATH even when `/workspace` is not bind-mounted (e.g. during build or standalone run). |
| **tmpfs for `/home/fa/.local`** | ⚠️ MEDIUM. The entrypoint runs `fa` which was installed via `uv pip install --system .`. The `fa` script is at `/usr/local/bin/fa` (symlinked). But Python packages installed by `uv pip install --system` land in the system site-packages (likely under `/usr/local/lib/python3.13/dist-packages`), NOT under `~/.local`. This is actually fine — the symlink ensures the CLI is on PATH regardless. |
| **No logging/telemetry on entrypoint decisions** | ⚠️ LOW. When auto-run completes or crashes, there's no indication in logs. |
| **FA_TASK env expansion is unsafe** | ⚠️ MEDIUM. The `${FA_ROLE:+--role "$FA_ROLE"}` pattern works for single-word values but if any value contains spaces and is unquoted in compose, it could break. |

---

## 2. Root-Cause Table

| # | Issue | Impact | Root Cause | Proposed Fix | Severity |
|---|-------|--------|------------|--------------|----------|
| 1 | `restart: unless-stopped` + `FA_TASK` set → infinite re-execution loop | Agent runs the same task forever, burning API credits, creating git noise, filling logs | `exec fa run` replaces PID 1 with `fa`. When `fa` exits (success or crash), PID 1 exits → container stops → Docker restarts it → `FA_TASK` is still set → `fa run` fires again | Entry-point script must catch `fa run` exit, log the result, and transition to `sleep infinity` instead of letting the process exit and trigger a restart | **CRITICAL** |
| 2 | No distinction between task success, failure, or crash | Operator cannot tell from container state whether the task completed correctly | `exec` replaces the shell; exit code propagates to Docker but is immediately lost to restart | Capture and log exit code; write a state file to `/workspace/.fa/runs/` with outcome metadata | **HIGH** |
| 3 | `fa run` may hang on TTY/stdin in non-interactive Docker | Agent appears frozen; consumes resources without progress | LLM provider calls or interactive prompts may expect a TTY | Ensure `fa run` runs with no TTY (`--no-tty` if the CLI supports it, or `</dev/null` redirect) | **MEDIUM** |
| 4 | PYTHONPATH set both in Dockerfile ENV and entrypoint script | Redundant but not harmful — Dockerfile ENV provides the base, entrypoint prepends `/workspace/src` | Double definition is intentional (Dockerfile = baseline, entrypoint = runtime prepend) | Leave as-is; the entrypoint's prepend syntax `${PYTHONPATH:+:$PYTHONPATH}` is correct | **LOW (info only)** |
| 5 | `/home/fa/.local` is tmpfs — wiped on container restart | If `fa` CLI was installed to `~/.local/`, it would be lost after restart | The PR correctly uses `uv pip install --system` + `/usr/local/bin/fa` symlink, so this is not an actual problem | No fix needed — installation path is correct | **N/A** |
| 6 | `FA_TASK` values with spaces or special chars in compose | Could break argument parsing if not properly quoted | Compose env vars with unquoted `- FA_TASK` pass through correctly if set in compose file; but if set via `docker run -e FA_TASK="..."` the quoting depends on the shell | Document quoting requirements; entrypoint script already uses `"$FA_TASK"` which is correct | **LOW (info only)** |
| 7 | `read_only: true` root filesystem + `fa run` needs writable paths | `fa run` writes to `/workspace/.fa/runs/`, `~/.fa/config.yaml`, etc. | These paths are either bind-mounted (`/workspace`, `/home/fa/.fa`) or tmpfs (`/tmp`, `/home/fa/.cache`, `/home/fa/.local`) — all writable | No fix needed — volume layout is correct | **N/A** |
| 8 | `init: true` (tini) with `exec` in entrypoint | `exec` replaces the shell, making tini the parent of `fa run`. When `fa run` exits, tini exits, container stops. | This is the correct behavior for the current (broken) restart policy, but it's what causes the loop | The fix must prevent `exec fa run` from being the final process — instead run it as a child and continue to `sleep infinity` | **CRITICAL (related to #1)** |

---

## 3. Fix Plan

### Minimum Coherent Set of Changes

The fix centers on **one file**: `scripts/fa-entrypoint.sh`. The restart-loop problem is an entrypoint-layer issue, not a compose-layer issue. Changing the compose restart policy would break the 24/7 stand-by mode. The correct fix is:

**Make the entrypoint a process supervisor instead of a simple `exec`:**

1. Run `fa run` as a child process (not `exec`)
2. Capture its exit code
3. Log the outcome (success, failure, crash)
4. Write a result marker to `/workspace/.fa/entrypoint-status.txt`
5. Transition to `sleep infinity` — the container stays alive, Docker does NOT restart it
6. The operator can then `docker exec` in, inspect logs, decide whether to re-run

This design:
- Preserves `restart: unless-stopped` for crash recovery (if the *entrypoint* crashes, Docker restarts; but the entrypoint won't crash because it catches `fa run` exit)
- Prevents accidental infinite re-execution
- Keeps the container inspectable after task completion
- Works correctly with `docker compose up -d` (the primary deployment path)
- Is fully compatible with `docker run --rm -e FA_TASK="..."` for one-shot use

**Alternative designs considered and rejected:**

| Alternative | Why Rejected |
|-------------|--------------|
| Change compose to `restart: "no"` when FA_TASK is set | Requires manual compose edits — exactly the poor UX we're fixing. Fragile and easy to forget. |
| Use `docker run --rm` directly instead of compose | Bypasses the whole compose infrastructure (networks, volumes, resource limits, healthcheck). Not suitable for 24/7 deployment. |
| Add a sentinel file check (`/tmp/.fa-task-done`) | tmpfs is wiped on restart. If Docker restarts the container fast enough, the sentinel doesn't survive. Also doesn't handle the case where Docker restarts without tmpfs wipe (compose down/up). |
| Use Docker's `stop_signal` to prevent restart | Docker doesn't support "don't restart on clean exit" — `restart: unless-stopped` restarts on ANY non-zero exit AND on container stop. Only `restart: "no"` prevents restarts, but that breaks crash recovery for stand-by mode. |
| Two-container approach (task runner + stand-by) | Over-engineered. The entrypoint supervisor pattern is simpler and proven (used by many production systems). |

**The entrypoint supervisor pattern is the right fix.** It's the smallest coherent change that solves the problem at the correct layer.

---

## 4. Implemented Changes

### 4.1 `scripts/fa-entrypoint.sh` (REWRITE)

```bash
#!/usr/bin/env bash
# fa-entrypoint.sh — Dual-mode entrypoint for First-Agent Docker container.
#
# Modes:
#   1. Auto-run mode: FA_TASK is set → run fa once, log outcome, then stand-by.
#   2. Command override: $@ is non-empty → exec "$@".
#   3. Stand-by mode (default): sleep infinity, ready for docker exec.
#
# The key design choice: auto-run mode does NOT exec fa. Instead, it runs fa
# as a child process, captures its exit code, logs the outcome, and then
# transitions to sleep infinity. This prevents the restart: unless-stopped
# loop where a completed or crashed fa run triggers an immediate container
# restart and re-execution.
#
# After an auto-run, the container stays alive and inspectable via docker exec.
# The operator can review logs and the status file at:
#   /workspace/.fa/entrypoint-status.txt

set -uo pipefail

# ── Status file path (on the persistent bind-mounted workspace) ──
STATUS_FILE="/workspace/.fa/entrypoint-status.txt"

log() {
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "[fa-entrypoint $ts] $*"
}

write_status() {
  local exit_code="$1"
  local status_label="$2"
  local detail="${3:-}"
  mkdir -p "$(dirname "$STATUS_FILE")"
  {
    echo "exit_code=$exit_code"
    echo "status=$status_label"
    echo "timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "task=${FA_TASK:-}"
    echo "role=${FA_ROLE:-}"
    echo "max_turns=${FA_MAX_TURNS:-}"
    echo "run_id=${FA_RUN_ID:-}"
    if [[ -n "$detail" ]]; then
      echo "detail=$detail"
    fi
  } > "$STATUS_FILE"
}

# ── PYTHONPATH: live bind-mounted source takes precedence ──
export PYTHONPATH="/workspace/src${PYTHONPATH:+:$PYTHONPATH}"
log "PYTHONPATH=$PYTHONPATH"

if [[ -n "${FA_TASK:-}" ]]; then
  # ── Auto-run mode ──
  log "Auto-run mode: FA_TASK is set"
  log "Starting: fa run --task \"$FA_TASK\" --workspace /workspace"

  FA_CMD=(fa run --task "$FA_TASK" --workspace /workspace)

  if [[ -n "${FA_ROLE:-}" ]]; then
    FA_CMD+=(--role "$FA_ROLE")
    log "  --role=\"$FA_ROLE\""
  fi
  if [[ -n "${FA_MAX_TURNS:-}" ]]; then
    FA_CMD+=(--max-turns "$FA_MAX_TURNS")
    log "  --max-turns=\"$FA_MAX_TURNS\""
  fi
  if [[ -n "${FA_RUN_ID:-}" ]]; then
    FA_CMD+=(--run-id "$FA_RUN_ID")
    log "  --run-id=\"$FA_RUN_ID\""
  fi

  # Run fa as a child process (NOT exec). This is critical: we need to
  # capture the exit code and then transition to stand-by mode instead
  # of letting the container exit and trigger a Docker restart loop.
  log "Launching fa run..."
  fa_exit_code=0
  "${FA_CMD[@]}" </dev/null 2>&1 || fa_exit_code=$?

  if [[ $fa_exit_code -eq 0 ]]; then
    log "fa run completed successfully (exit code 0)"
    write_status 0 "SUCCESS" "Task completed successfully"
  else
    log "fa run exited with code $fa_exit_code"
    write_status "$fa_exit_code" "FAILED" "fa run exited with code $fa_exit_code"
  fi

  log "Transitioning to stand-by mode (sleep infinity). Container is alive for inspection."
  log "  Review status: cat $STATUS_FILE"
  log "  Re-run task:  docker exec first-agent fa run --task '$FA_TASK' --workspace /workspace"
  exec sleep infinity

elif [[ $# -gt 0 ]]; then
  # ── Command override mode ──
  log "Command override mode: exec $*"
  exec "$@"

else
  # ── Stand-by mode ──
  log "Stand-by mode: sleep infinity"
  exec sleep infinity
fi
```

**Key changes from the original:**

1. **`exec fa run` → `"${FA_CMD[@]}"` (no exec):** This is the critical fix. Running `fa` as a child process means when `fa` exits, control returns to the entrypoint script, which then transitions to `sleep infinity`. The container does NOT exit, so Docker does NOT restart it.

2. **`</dev/null 2>&1`:** Redirects stdin from `/dev/null` to prevent any interactive prompt from hanging the container. Stderr is merged to stdout so all output goes to Docker logs.

3. **Exit code capture and logging:** The script logs whether `fa run` succeeded or failed, writes a status file to the persistent workspace, and provides actionable next-step instructions.

4. **Status file:** Written to `/workspace/.fa/entrypoint-status.txt` on the bind-mounted workspace, so it persists across container restarts and is accessible from the host.

5. **`set -uo pipefail` (not `set -euo pipefail`):** We intentionally do NOT use `set -e` because we need to capture the exit code of `fa run` even when it fails. The `|| fa_exit_code=$?` pattern handles this correctly.

6. **Array-based command construction:** Instead of the `${VAR:+--option "$VAR"}` inline expansion (which can break with unquoted values), we use a proper bash array. This is safer and more maintainable.

### 4.2 `docker-compose.fa.yml` (NO CHANGES NEEDED)

The existing compose file is correct. The `restart: unless-stopped` policy works fine with the new entrypoint because:
- In stand-by mode: `sleep infinity` never exits, so restart is never triggered.
- In auto-run mode: The entrypoint catches `fa run` exit and transitions to `sleep infinity`, so restart is never triggered.
- If the entrypoint itself crashes (extremely unlikely): Docker restarts the container, which re-runs the task — this is the correct behavior for a crash recovery scenario.

### 4.3 `Dockerfile.fa` (ONE MINOR FIX)

The `uv pip install --system .` command runs in the build context where `/tmp/fa-build/` is the working directory. However, the `COPY` instructions only copy `pyproject.toml`, `uv.lock`, `README.md`, and `src/`. This is correct — we don't need tests, docs, or other non-runtime files in the image.

**No changes needed to Dockerfile.fa.**

### 4.4 `knowledge/SETUP_AIO.md` (UPDATE)

The documentation about the restart-loop caveat should be updated to reflect the fix:

```markdown
**Container entrypoint:** The Dockerfile now uses `fa-entrypoint.sh` as its entrypoint.

- **Stand-by mode (default):** If `FA_TASK` is unset, the container runs `sleep infinity`
  and you can `docker exec` into it to run FA manually.
- **Auto-run mode:** Set `FA_TASK` in `docker-compose.fa.yml` (or pass
  `-e FA_TASK="..."` to `docker run`) and the container will execute
  `fa run --task "$FA_TASK"` on start. Optional: `FA_ROLE`, `FA_MAX_TURNS`, `FA_RUN_ID`.
  After the task completes (success or failure), the container transitions to stand-by mode
  (`sleep infinity`) and remains alive for inspection. It does NOT restart or re-run the task.
  To re-run: `docker exec first-agent fa run --task "your task" --workspace /workspace`.
- **Status file:** After an auto-run, the outcome is written to
  `/workspace/.fa/entrypoint-status.txt` with exit code, status label, timestamp,
  and task metadata.
- `PYTHONPATH=/workspace/src` ensures the container always uses the live bind-mounted
  source code without requiring a rebuild after edits.
```

### 4.5 `HANDOFF.md` (UPDATE)

Update the current-state blurb to reflect the fix:

```markdown
**As of:** 2026-06-11 — Loop entrypoint fixed (branch `devin/2026-06-10-loop-entrypoint-from-main`):
`scripts/fa-entrypoint.sh` now runs `fa run` as a child process (not `exec`), captures exit code,
writes status file to `/workspace/.fa/entrypoint-status.txt`, and transitions to `sleep infinity`
instead of exiting. This eliminates the `restart: unless-stopped` infinite re-execution loop.
Container remains alive and inspectable after task completion. `docker-compose.fa.yml` and
`Dockerfile.fa` unchanged from PR #22. **Ready for first `fa inner-loop-smoke` inside the container.**
```

### 4.6 `.dockerignore` (ADD entrypoint-status.txt)

```diff
 # Test data and temporary files
 tests/test_data
 tmp
+
+# Entrypoint runtime state (generated inside container)
+.fa/entrypoint-status.txt
```

---

## 5. Validation Matrix

### 5.1 Fresh Build

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml build --no-cache
```

**Expected outcome:** Build completes successfully. The `fa` CLI is installed at `/usr/local/bin/fa`. The entrypoint script is at `/usr/local/bin/fa-entrypoint.sh`. `PYTHONPATH=/workspace/src` is set.

### 5.2 Stand-by Mode

```bash
docker compose -f docker-compose.fa.yml up -d
docker ps  # Should show container running
docker logs first-agent  # Should show "[fa-entrypoint ...] Stand-by mode: sleep infinity"
docker exec first-agent bash -c 'echo $PYTHONPATH'  # Should show /workspace/src:...
```

**Expected outcome:** Container stays running. Python path includes `/workspace/src`.

### 5.3 Manual docker exec

```bash
docker exec -it first-agent bash
fa --version  # Should print version
fa inner-loop-smoke --workspace /workspace --input README.md
```

**Expected outcome:** `fa` CLI is callable. Smoke test passes.

### 5.4 fa CLI Availability

```bash
docker exec first-agent which fa  # Should be /usr/local/bin/fa
docker exec first-agent fa --help  # Should show help text
```

**Expected outcome:** `fa` is on PATH and functional.

### 5.5 Small Coding Task (Auto-run)

```bash
docker compose -f docker-compose.fa.yml down
# Temporarily set FA_TASK in compose or via override
docker run --rm -e FA_TASK="Write a hello world Python script" \
  -v /srv/first-agent/repo/First-Agent-dev:/workspace \
  -v /srv/first-agent/state:/home/fa/.fa \
  -v /srv/first-agent/secrets/github_deploy_key:/run/secrets/git_key:ro \
  -v /srv/first-agent/secrets/known_hosts:/run/secrets/known_hosts:ro \
  -e GIT_SSH_COMMAND="ssh -i /run/secrets/git_key -o IdentitiesOnly=yes -o UserKnownHostsFile=/run/secrets/known_hosts" \
  first-agent:latest
```

**Expected outcome:** `fa run` executes the task, completes, and the container exits cleanly (with `--rm`, it's removed).

### 5.6 Long Multi-step / Plan-following Task

```bash
docker run --rm -e FA_TASK="Implement feature X following plan in /workspace/plan.md" \
  -e FA_MAX_TURNS=32 \
  -e FA_RUN_ID="plan-x-$(date +%Y%m%d)" \
  -v /srv/first-agent/repo/First-Agent-dev:/workspace \
  ... \
  first-agent:latest
```

**Expected outcome:** Task runs with increased turn cap. Events are logged to `/workspace/.fa/runs/plan-x-YYYYMMDD/events.jsonl`. Container exits cleanly after completion or turn cap.

### 5.7 Source Edit Reflected Without Rebuild

```bash
# Edit a file on the host
echo 'print("hello from live source")' > /srv/first-agent/repo/First-Agent-dev/src/fa/example.py

# Verify inside running container
docker exec first-agent python3 -c "import fa.example"  # Should work without rebuild
```

**Expected outcome:** Live bind-mounted source is picked up immediately.

### 5.8 Auto-run Behavior (with the FIX)

```bash
# Set FA_TASK via docker compose override or .env.fa
docker compose -f docker-compose.fa.yml up -d
docker logs -f first-agent  # Should show auto-run, completion, then stand-by
docker exec first-agent cat /workspace/.fa/entrypoint-status.txt  # Should show SUCCESS or FAILED
docker ps  # Container should STILL be running
```

**Expected outcome:** `fa run` executes once, logs outcome, transitions to stand-by. Container remains alive. No restart loop.

### 5.9 Success Case

- `fa run` returns 0 → entrypoint logs "SUCCESS" → writes status file → sleeps infinity → container stays up.
- Operator can `docker exec` to inspect results, review `events.jsonl`, and verify changes.

### 5.10 Crash/Failure Case

- `fa run` returns non-zero → entrypoint logs exit code → writes status file with "FAILED" → sleeps infinity → container stays up.
- Operator can `docker exec` to inspect logs, check `events.jsonl` for error traces, and decide next steps.

### 5.11 Restart-Policy Behavior: Before and After Fix

| Scenario | Before Fix (exec fa run) | After Fix (child process) |
|----------|--------------------------|---------------------------|
| FA_TASK set, task succeeds | Container exits → Docker restarts → task re-runs forever ♻️ | Entrypoint logs success → sleeps infinity → container stays alive ✅ |
| FA_TASK set, task fails | Container exits → Docker restarts → task re-runs forever ♻️ | Entrypoint logs failure → sleeps infinity → container stays alive ✅ |
| FA_TASK set, entrypoint crashes | Container exits → Docker restarts → task re-runs ♻️ | Container exits → Docker restarts → task re-runs ♻️ (correct: crash recovery) |
| FA_TASK unset, sleep infinity crashes | Container exits → Docker restarts → sleep infinity ♻️ | Container exits → Docker restarts → sleep infinity ♻️ (correct: crash recovery) |

The fix eliminates the accidental loop for task completion/failure while preserving crash recovery for the entrypoint itself.

---

## 6. Edge-Case Handling

### Successful Task Completion
- `fa run` exits 0 → entrypoint logs "SUCCESS" → writes status file → `exec sleep infinity`
- Container remains alive, Docker does NOT restart it
- Operator can inspect results via `docker exec`

### Agent Crash
- `fa run` crashes (segfault, OOM kill, etc.) → entrypoint catches non-zero exit → logs "FAILED" → writes status file → `exec sleep infinity`
- Container remains alive for debugging
- Docker does NOT restart (because the entrypoint didn't exit)

### Python/Runtime Exception
- `fa run` exits non-zero due to unhandled exception → same as crash above
- Exception traceback appears in Docker logs (stderr merged to stdout)
- Operator can review logs and status file

### Invalid FA_TASK
- `fa run` fails with error (e.g., malformed task, missing provider) → non-zero exit → caught → logged → stand-by
- Error message in Docker logs is actionable

### Missing Env Vars
- `FA_ROLE`, `FA_MAX_TURNS`, `FA_RUN_ID` are all optional
- Entry-point script only adds CLI flags when vars are non-empty
- Missing vars → default behavior from `fa` CLI (role="coder", max_turns=16, run_id=derived from PID)

### Partial Task Failure
- `fa run` may complete some tool calls before failing → events are written to `events.jsonl` → partial results are preserved
- Operator can review partial state and decide whether to continue

### Long-Running Autonomous Execution
- `fa run` can run for hours with `FA_MAX_TURNS` set appropriately
- Events are streamed to Docker logs (json-file driver with 10m/3 rotation)
- `events.jsonl` on persistent bind-mount provides full audit trail
- Container stays healthy (healthcheck just runs `python -c "import sys; sys.exit(0)"`)

### Post-Run Inspection/Debugging
- Status file at `/workspace/.fa/entrypoint-status.txt` provides machine-readable outcome
- `events.jsonl` at `/workspace/.fa/runs/<run_id>/events.jsonl` provides full execution trace
- Docker logs contain entrypoint and `fa run` output
- Container is alive for `docker exec` inspection

---

## 7. Residual Risks / Follow-ups

| Risk | Status | Notes |
|------|--------|-------|
| `fa run` hangs indefinitely (LLM provider timeout not configured) | LOW | `RuntimeLimits` has `bash_timeout_seconds=30` but no LLM call timeout. A future `FA_TIMEOUT` env var could be added. |
| Concurrent `docker exec` during `fa run` | LOW | The `fa` process has the `/workspace/.fa/runs/<run_id>/` directory locked by its own file writes. Concurrent exec can read but won't interfere. |
| Large `events.jsonl` fills disk | LOW | Docker log rotation handles stdout/stderr logs. `events.jsonl` on persistent bind-mount should be monitored. A future `fa` feature could implement log rotation for `events.jsonl`. |
| `FA_TASK` with shell-special characters | LOW | Array-based command construction handles this correctly. The value is passed as a single argument, not shell-expanded. |
| tmpfs exhaustion (1G /tmp, 500M /home/fa/.cache) | MEDIUM | For very large tasks, tmpfs limits could be reached. Monitor with `docker exec first-agent df -h`. If needed, increase tmpfs sizes in compose. |
| `fa run` output buffering | LOW | `PYTHONUNBUFFERED=1` ensures Python output is not buffered. The `2>&1` redirect captures all output to Docker logs. |

**Recommended Follow-up PRs:**
1. Add `FA_TIMEOUT` env var for LLM call wall-clock timeout (prevents hung runs)
2. Add `fa status` subcommand that reads `/workspace/.fa/entrypoint-status.txt` and renders it nicely
3. Implement `events.jsonl` log rotation for long-running tasks
4. Add a `docker compose` override file for auto-run mode (`docker-compose.fa-run.yml`) that sets `FA_TASK` cleanly without editing the main compose file

---

## 8. Final Merge Recommendation

**CHANGES REQUIRED**

The PR's approach is mostly correct but has one critical defect: the `exec fa run` pattern in the entrypoint creates an infinite restart loop when `FA_TASK` is set. This is not a minor issue — it makes auto-run mode unusable in production without manual compose edits, which is exactly the poor UX the PR aims to fix.

The fix I've provided (running `fa run` as a child process, capturing exit code, transitioning to stand-by) is the smallest coherent change that solves the problem at the correct layer. It:
- Eliminates the infinite restart loop ✅
- Preserves crash recovery ✅
- Keeps the container inspectable after task completion ✅
- Works with the existing compose infrastructure ✅
- Requires no manual compose edits ✅
- Is fully backward compatible with stand-by mode ✅

**Required changes before merge:**
1. Rewrite `scripts/fa-entrypoint.sh` as provided above
2. Update `knowledge/SETUP_AIO.md` to reflect the new behavior (remove the ⚠️ caveat, document the status file)
3. Update `HANDOFF.md` to reflect the fix

**Optional but recommended:**
4. Add `FA_TIMEOUT` env var support in a follow-up
5. Add a `docker-compose.fa-run.yml` override file for clean auto-run configuration
