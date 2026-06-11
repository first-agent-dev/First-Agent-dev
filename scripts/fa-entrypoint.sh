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
    [ -n "${FA_TASK:-}" ] && echo "task=${FA_TASK}"
    [ -n "${FA_ROLE:-}" ] && echo "role=${FA_ROLE}"
    [ -n "${FA_MAX_TURNS:-}" ] && echo "max_turns=${FA_MAX_TURNS}"
    [ -n "${FA_RUN_ID:-}" ] && echo "run_id=${FA_RUN_ID}"
    [ -n "$detail" ] && echo "detail=$detail"
  } > "$STATUS_FILE"
}

# ── PYTHONPATH: live bind-mounted source takes precedence ──
export PYTHONPATH="/workspace/src${PYTHONPATH:+:$PYTHONPATH}"
log "PYTHONPATH=$PYTHONPATH"

if [[ -n "${FA_TASK:-}" ]]; then
  # ── Auto-run mode ──
  log "Auto-run mode: FA_TASK is set"
  log "Starting: fa run --task \"${FA_TASK}\" --workspace /workspace"

  FA_CMD=(fa run --task "$FA_TASK" --workspace /workspace)

  if [[ -n "${FA_ROLE:-}" ]]; then
    FA_CMD+=(--role "$FA_ROLE")
    log "  --role=\"${FA_ROLE}\""
  fi
  if [[ -n "${FA_MAX_TURNS:-}" ]]; then
    FA_CMD+=(--max-turns "$FA_MAX_TURNS")
    log "  --max-turns=\"${FA_MAX_TURNS}\""
  fi
  if [[ -n "${FA_RUN_ID:-}" ]]; then
    FA_CMD+=(--run-id "$FA_RUN_ID")
    log "  --run-id=\"${FA_RUN_ID}\""
  fi

  # Run fa as a child process (NOT exec). This is critical: we need to
  # capture the exit code and then transition to stand-by mode instead
  # of letting the container exit and trigger a Docker restart loop.
  log "Launching fa run..."
  fa_exit_code=0
  # </dev/null prevents any interactive prompt from hanging the container.
  # stdout and stderr both go to Docker logs for full traceability.
  "${FA_CMD[@]}" </dev/null || fa_exit_code=$?

  if [[ $fa_exit_code -eq 0 ]]; then
    log "fa run completed successfully (exit code 0)"
    write_status 0 "SUCCESS" "Task completed successfully"
  else
    log "fa run exited with code $fa_exit_code"
    write_status "$fa_exit_code" "FAILED" "fa run exited with code $fa_exit_code"
  fi

  log "Transitioning to stand-by mode (sleep infinity). Container is alive for inspection."
  log "  Review status: cat $STATUS_FILE"
  log "  Re-run task:  docker exec first-agent fa run --task '${FA_TASK}' --workspace /workspace"
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
