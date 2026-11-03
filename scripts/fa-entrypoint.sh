#!/usr/bin/env bash
# fa-entrypoint.sh — dual-mode entrypoint for the First-Agent container.
#
# Modes:
#   1. Command override: arguments are present -> exec "$@".
#   2. Auto-run: FA_AUTO_RUN is truthy -> run `fa run` once as a child,
#      write a status file, then transition to stand-by.
#   3. Stand-by: default -> sleep infinity, ready for `docker exec`.
#
# Auto-run deliberately does NOT exec `fa run`: the agent is a child
# process so this wrapper can capture its exit code and keep the
# container inspectable instead of triggering Docker restart loops.

set -Eeuo pipefail

WORKSPACE="${FA_WORKSPACE:-/workspace}"
STATUS_FILE="${FA_STATUS_FILE:-${WORKSPACE}/.fa/entrypoint-status.txt}"
TASK_TEXT=""
TASK_SOURCE=""
CHILD_PID=""
ENTRYPOINT_MANAGED_AUTO_RUN=0
ENTRYPOINT_HAS_COMMAND_OVERRIDE=0
if [[ $# -gt 0 ]]; then
  ENTRYPOINT_HAS_COMMAND_OVERRIDE=1
fi

log() {
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "[fa-entrypoint ${ts}] $*"
}

_truthy() {
  case "${1,,}" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

_one_line() {
  tr '\r\n' '  ' | sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^ //' -e 's/ $//'
}

_task_sha256() {
  printf '%s' "$TASK_TEXT" | sha256sum | awk '{print $1}'
}

_task_preview() {
  printf '%s' "$TASK_TEXT" | _one_line | cut -c 1-160
}

_write_status() {
  local exit_code="$1"
  local status_label="$2"
  local detail="${3:-}"
  local status_dir tmp_file

  status_dir="$(dirname "$STATUS_FILE")"
  if ! mkdir -p "$status_dir" 2>/dev/null; then
    log "WARN: could not create status directory: $status_dir"
    return 0
  fi
  tmp_file="${STATUS_FILE}.tmp.$$"
  {
    echo "exit_code=${exit_code}"
    echo "status=${status_label}"
    echo "timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "workspace=${WORKSPACE}"
    echo "auto_run=${FA_AUTO_RUN:-0}"
    [[ -n "${TASK_SOURCE}" ]] && echo "task_source=${TASK_SOURCE}"
    [[ -n "${TASK_TEXT}" ]] && echo "task_sha256=$(_task_sha256)"
    [[ -n "${TASK_TEXT}" ]] && echo "task_preview=$(_task_preview)"
    [[ -n "${FA_ROLE:-}" ]] && echo "role=${FA_ROLE}"
    [[ -n "${FA_CONFIG:-}" ]] && echo "config=${FA_CONFIG}"
    [[ -n "${FA_MAX_TURNS:-}" ]] && echo "max_turns=${FA_MAX_TURNS}"
    [[ -n "${FA_SESSION_ID:-}" ]] && echo "session_id=${FA_SESSION_ID}"
    [[ -n "${FA_RUN_ID:-}" ]] && echo "run_id=${FA_RUN_ID}"
    [[ -n "${FA_RESUME:-}" ]] && echo "resume=${FA_RESUME}"
    [[ -n "$detail" ]] && echo "detail=$(printf '%s' "$detail" | _one_line)"
  } > "$tmp_file" && mv "$tmp_file" "$STATUS_FILE" || {
    rm -f "$tmp_file" 2>/dev/null || true
    log "WARN: could not write status file: $STATUS_FILE"
  }
}

_standby() {
  log "Stand-by mode: sleep infinity"
  log "  Exec shell: docker exec -it ${FA_CONTAINER_NAME:-first-agent} bash"
  log "  Status:     cat ${STATUS_FILE}"
  exec sleep infinity
}

_fail_to_standby() {
  local detail="$1"
  log "Invalid auto-run configuration: $detail"
  _write_status 2 "INVALID_CONFIG" "$detail"
  _standby
}

_publish_active_workspace() {
  local workspace_path="$1"
  printf '%s\n' "$workspace_path" > "/sessions/.active.tmp.$$"
  mv -f "/sessions/.active.tmp.$$" "/sessions/.active"
}

_validate_session_id() {
  local value="$1"
  [[ "$value" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]]
}

_validate_run_id() {
  local value="$1"
  [[ "$value" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]]
}

_load_task() {
  local raw_file candidate workspace_real file_real

  if [[ -n "${FA_TASK:-}" && -n "${FA_TASK_FILE:-}" ]]; then
    _fail_to_standby "Set only one of FA_TASK or FA_TASK_FILE, not both"
  fi

  if [[ -n "${FA_TASK_FILE:-}" ]]; then
    raw_file="$FA_TASK_FILE"
    if [[ "$raw_file" = /* ]]; then
      candidate="$raw_file"
    else
      candidate="${WORKSPACE%/}/$raw_file"
    fi
    workspace_real="$(readlink -f "$WORKSPACE" 2>/dev/null || true)"
    file_real="$(readlink -f "$candidate" 2>/dev/null || true)"
    [[ -n "$workspace_real" ]] || _fail_to_standby "Workspace does not exist: $WORKSPACE"
    [[ -n "$file_real" ]] || _fail_to_standby "FA_TASK_FILE not found: $FA_TASK_FILE"
    case "$file_real" in
      "$workspace_real"|"$workspace_real"/*) ;;
      *) _fail_to_standby "FA_TASK_FILE must resolve inside workspace: $FA_TASK_FILE" ;;
    esac
    [[ -f "$file_real" ]] || _fail_to_standby "FA_TASK_FILE is not a regular file: $FA_TASK_FILE"
    [[ -r "$file_real" ]] || _fail_to_standby "FA_TASK_FILE is not readable: $FA_TASK_FILE"
    TASK_TEXT="$(cat "$file_real")"
    TASK_SOURCE="file:$file_real"
  else
    TASK_TEXT="${FA_TASK:-}"
    TASK_SOURCE="env:FA_TASK"
  fi

  if [[ -z "${TASK_TEXT//[[:space:]]/}" ]]; then
    _fail_to_standby "Task is empty or whitespace-only"
  fi
}

_on_term() {
  log "Received termination signal"
  if [[ -n "$CHILD_PID" ]] && kill -0 "$CHILD_PID" 2>/dev/null; then
    log "Forwarding SIGTERM to fa run child pid=$CHILD_PID"
    kill -TERM "$CHILD_PID" 2>/dev/null || true
    wait "$CHILD_PID" 2>/dev/null || true
  fi
  _write_status 143 "TERMINATED" "Container received SIGTERM/SIGINT during auto-run"
  exit 143
}

_configure_entrypoint_workspace() {
  local python_bin="${PYTHON:-python3}"
  "$python_bin" -m fa.session.workspace configure-existing \
    --source /repo \
    --workspace "$SESSION_DIR" \
    --session-id "$SESSION_ID" \
    >/dev/null
}

_prepare_entrypoint_workspace() {
  local python_bin="${PYTHON:-python3}"
  local readiness_rc=0
  if "$python_bin" -m fa.workspace_bootstrap ensure --workspace "$SESSION_DIR" >/dev/null; then
    return 0
  else
    readiness_rc=$?
  fi
  if [[ "$ENTRYPOINT_HAS_COMMAND_OVERRIDE" == "1" ]]; then
    log "WARN: workspace readiness degraded (rc=$readiness_rc); continuing explicit command override"
    return 0
  fi
  if _truthy "${FA_AUTO_RUN:-0}"; then
    log "ERROR: workspace readiness degraded (rc=$readiness_rc); refusing auto-run"
    return "$readiness_rc"
  fi
  log "WARN: workspace readiness degraded (rc=$readiness_rc); continuing to standby"
  return 0
}

# Session workspace setup — runs once on container start. Managed auto-run
# delegates materialization, identity, and readiness to SessionManager. Explicit
# command overrides and standby retain their legacy filesystem adapter path.
if [[ -n "${FA_SESSION_ID:-}" ]]; then
    _validate_session_id "$FA_SESSION_ID" || _fail_to_standby \
        "FA_SESSION_ID must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}; got '${FA_SESSION_ID}'"
fi

if [[ -d "/repo/.git" ]] && [[ -z "${FA_WORKSPACE:-}" ]]; then
    SESSION_ID="${FA_SESSION_ID:-session-$(date -u +%Y%m%dT%H%M%S)-$$}"
    export FA_SESSION_ID="$SESSION_ID"
    SESSION_DIR="/sessions/${SESSION_ID}"

    if [[ "$ENTRYPOINT_HAS_COMMAND_OVERRIDE" == "0" ]] && _truthy "${FA_AUTO_RUN:-0}"; then
        # The manager validates the id and owns the default /sessions/<id> root.
        # Do not touch host Git or project files before its managed handoff.
        ENTRYPOINT_MANAGED_AUTO_RUN=1
        WORKSPACE="$SESSION_DIR"
    else
        # Explicit override and standby intentionally preserve the legacy adapter.
        if ! git check-ref-format --branch "agent/${SESSION_ID}" >/dev/null 2>&1; then
            _fail_to_standby "FA_SESSION_ID does not form a valid Git branch: $SESSION_ID"
        fi

        SESSION_CREATED=0
        if [[ ! -d "$SESSION_DIR/.git" ]]; then
            # file:// uses pack transport rather than cross-device hardlinks.
            if git clone "file:///repo" "$SESSION_DIR" \
                && git -C "$SESSION_DIR" checkout -b "agent/${SESSION_ID}"; then
                SESSION_CREATED=1
                cd "$SESSION_DIR"
                log "Created session workspace: $SESSION_DIR"
            else
                rm -rf "$SESSION_DIR" 2>/dev/null || true
                _fail_to_standby "git clone/checkout failed for $SESSION_DIR"
            fi
        else
            cd "$SESSION_DIR"
            log "Resumed session workspace: $SESSION_DIR"
        fi

        if ! _configure_entrypoint_workspace; then
            if [[ "$SESSION_CREATED" == "1" ]]; then
                rm -rf "$SESSION_DIR" 2>/dev/null || true
            fi
            _fail_to_standby "managed Git configuration failed for $SESSION_DIR"
        fi

        if ! _prepare_entrypoint_workspace; then
            if [[ "$SESSION_CREATED" == "1" ]]; then
                rm -rf "$SESSION_DIR" 2>/dev/null || true
            fi
            detail="workspace readiness failed; managed auto-run refused"
            log "Auto-run refused: $detail"
            _write_status 2 "FAILED" "$detail"
            _standby
        fi

        _publish_active_workspace "$SESSION_DIR"
        WORKSPACE="$SESSION_DIR"
        if [[ -z "${FA_STATUS_FILE:-}" ]]; then
            STATUS_FILE="${WORKSPACE}/.fa/entrypoint-status.txt"
        fi
    fi
fi

# Live bind-mounted source wins over the image copy — but ONLY when /workspace
# actually holds the source (the agent container). The egress-proxy container
# deliberately has NO /workspace mount so it runs the IMMUTABLE image code from
# /opt/fa-venv; never prepend a non-existent (or, worse, agent-writable) path.
# Guard with a real file check so a stray empty /workspace can't shadow the image.
if [[ "$ENTRYPOINT_MANAGED_AUTO_RUN" == "1" ]]; then
  # Managed auto-run must import the installed controller, never session code.
  unset PYTHONPATH
elif [[ -f "${WORKSPACE%/}/src/fa/__init__.py" ]]; then
  export PYTHONPATH="${WORKSPACE%/}/src${PYTHONPATH:+:$PYTHONPATH}"
fi
# Prepend the image-owned venv so `fa` resolves to the installed console script.
# The directory is overridable via FA_VENV_BIN (default /opt/fa-venv/bin) so the
# entrypoint is testable outside the image (a test can point it at a stub dir, or
# set it empty to skip the prepend); production leaves it unset and gets the
# image venv. An empty/absent dir is never prepended.
FA_VENV_BIN="${FA_VENV_BIN-/opt/fa-venv/bin}"
if [[ -n "$FA_VENV_BIN" && -d "$FA_VENV_BIN" ]]; then
  export PATH="${FA_VENV_BIN}:$PATH"
fi
log "PYTHONPATH=${PYTHONPATH:-<image-default>}"

_provision_entrypoint_session() {
  local state_root="${FA_STATE_ROOT:-${HOME}/.fa}"
  local python_bin="${PYTHON:-python3}"
  "$python_bin" -m fa.session.manager provision \
    --state-root "$state_root" \
    --workspace-root "/sessions" \
    --session-id "$FA_SESSION_ID" \
    >/dev/null
}

# The managed path admits and readies the default session through one manager
# reservation. Only success publishes the active pointer or reaches `fa run`.
if [[ "$ENTRYPOINT_MANAGED_AUTO_RUN" == "1" ]]; then
  if _provision_entrypoint_session; then
    cd "$WORKSPACE"
    if [[ -z "${FA_STATUS_FILE:-}" ]]; then
      STATUS_FILE="${WORKSPACE}/.fa/entrypoint-status.txt"
    fi
    _publish_active_workspace "$WORKSPACE"
  else
    provision_rc=$?
    detail="managed session provisioning/readiness failed (exit=$provision_rc)"
    log "Auto-run refused: $detail"
    _write_status 2 "FAILED" "$detail"
    _standby
  fi
fi

# Explicit docker command overrides always win, even if FA_AUTO_RUN is set.
if [[ $# -gt 0 ]]; then
  log "Command override mode: exec $*"
  exec "$@"
fi

if _truthy "${FA_AUTO_RUN:-0}"; then
  log "Auto-run mode enabled (FA_AUTO_RUN=${FA_AUTO_RUN})"
  [[ -d "$WORKSPACE" ]] || _fail_to_standby "Workspace does not exist: $WORKSPACE"
  [[ -w "$WORKSPACE" ]] || _fail_to_standby "Workspace is not writable: $WORKSPACE"
  _load_task

  if [[ -n "${FA_MAX_TURNS:-}" && ! "${FA_MAX_TURNS}" =~ ^[1-9][0-9]*$ ]]; then
    _fail_to_standby "FA_MAX_TURNS must be a positive integer; got '${FA_MAX_TURNS}'"
  fi

  FA_ROLE="${FA_ROLE:-coder}"
  export FA_ROLE

  if [[ -n "${FA_RUN_ID:-}" ]]; then
    _validate_run_id "$FA_RUN_ID" || _fail_to_standby \
      "FA_RUN_ID must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}; got '${FA_RUN_ID}'"
  fi
  if _truthy "${FA_RESUME:-0}" && [[ -z "${FA_SESSION_ID:-}" ]]; then
    _fail_to_standby "FA_RESUME requires FA_SESSION_ID so the run attaches to a persistent session"
  fi

  FA_CMD=(fa run --task "$TASK_TEXT" --workspace "$WORKSPACE" --role "$FA_ROLE")
  [[ -n "${FA_SESSION_ID:-}" ]] && FA_CMD+=(--session-id "$FA_SESSION_ID")
  [[ -n "${FA_RUN_ID:-}" ]] && FA_CMD+=(--run-id "$FA_RUN_ID")
  [[ -n "${FA_CONFIG:-}" ]] && FA_CMD+=(--config "$FA_CONFIG")
  [[ -n "${FA_MAX_TURNS:-}" ]] && FA_CMD+=(--max-turns "$FA_MAX_TURNS")
  _truthy "${FA_RESUME:-0}" && FA_CMD+=(--resume)

  log "Launching fa run as child process"
  log "  workspace=${WORKSPACE}"
  log "  role=${FA_ROLE:-coder}"
  log "  session_id=${FA_SESSION_ID:-<cli-created>}"
  log "  run_id=${FA_RUN_ID:-<allocated-by-cli>}"
  log "  task_source=${TASK_SOURCE}"
  log "  task_sha256=$(_task_sha256)"
  _write_status -1 "RUNNING" "fa run child process is active"

  trap _on_term TERM INT
  "${FA_CMD[@]}" </dev/null &
  CHILD_PID=$!
  if wait "$CHILD_PID"; then
    fa_exit_code=0
  else
    fa_exit_code=$?
  fi
  CHILD_PID=""
  trap - TERM INT

  if [[ $fa_exit_code -eq 0 ]]; then
    log "fa run completed successfully (exit code 0)"
    _write_status 0 "SUCCESS" "Task completed successfully"
  else
    log "fa run exited with code $fa_exit_code"
    _write_status "$fa_exit_code" "FAILED" "fa run exited with code $fa_exit_code"
  fi

  log "Auto-run completed once; transitioning to inspectable stand-by state"
  _standby
fi

if [[ -n "${FA_TASK:-}" || -n "${FA_TASK_FILE:-}" ]]; then
  log "FA_TASK/FA_TASK_FILE present but FA_AUTO_RUN is not truthy; not running automatically"
  TASK_TEXT="${FA_TASK:-}"
  TASK_SOURCE="manual-disabled"
  _write_status 0 "STANDBY" "FA_AUTO_RUN is not enabled; ready for docker exec"
else
  _write_status 0 "STANDBY" "Ready for docker exec"
fi
_standby
