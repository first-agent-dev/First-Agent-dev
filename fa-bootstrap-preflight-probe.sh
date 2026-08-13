#!/usr/bin/env bash
# Read-only topology/readiness probe for the First-Agent AIO host.
#
# Safe to launch as the normal `fa` user from any directory. The script:
# - does not create/attach/delete sessions;
# - does not run an LLM or a quality gate;
# - does not install/sync dependencies or hooks;
# - does not print file contents, Git config, credentials, or general env;
# - disables Git optional index refresh and fsmonitor for status probes.
#
# Default deployment paths may be overridden with COMPOSE, SERVICE,
# DEPLOY_REPO, or HOME_REPO. Overrides are treated as operator-controlled input.
set -Eeuo pipefail

COMPOSE="${COMPOSE:-/srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml}"
SERVICE="${SERVICE:-first-agent}"
DEPLOY_REPO="${DEPLOY_REPO:-/srv/first-agent/repo/First-Agent-dev}"
HOME_REPO="${HOME_REPO:-${HOME}/First-Agent-dev}"

section() { printf '\n===== %s =====\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    printf 'ERROR: required command is missing: %s\n' "$name" >&2
    exit 2
  fi
}

# Git remotes sometimes contain an HTTPS userinfo token. Never print that
# component. `%q` also neutralizes terminal control characters in all values.
print_safe_value() {
  local label="$1" value="$2" redact_url="${3:-0}"
  if [[ "$redact_url" == "1" && "$value" =~ ^(https?://)[^/@]+@(.+)$ ]]; then
    value="${BASH_REMATCH[1]}<redacted>@${BASH_REMATCH[2]}"
  fi
  printf '%s=%q\n' "$label" "$value"
}

git_value() {
  local path="$1" label="$2" redact_url="$3"
  shift 3
  local value
  if value="$(GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$path" "$@" 2>/dev/null)"; then
    print_safe_value "$label" "$value" "$redact_url"
  else
    print_safe_value "$label" '<unset-or-unavailable>' 0
  fi
}

repo_facts() {
  local label="$1" path="$2" git_dir hooks_dir status_lines
  printf -- '--- %s: %s\n' "$label" "$path"
  if [[ ! -e "$path" ]]; then
    echo 'exists=no'
    return
  fi
  echo 'exists=yes'
  if real="$(readlink -f -- "$path" 2>/dev/null)"; then
    print_safe_value 'realpath' "$real"
  else
    echo 'realpath=<unavailable>'
  fi
  stat -c 'stat=device:%d inode:%i mode:%a owner:%u:%g' -- "$path" || true
  if ! GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo 'git_worktree=no'
    return
  fi

  git_value "$path" 'toplevel' 0 rev-parse --show-toplevel
  git_value "$path" 'head' 0 rev-parse HEAD
  git_value "$path" 'branch' 0 branch --show-current
  git_value "$path" 'origin.fetch' 1 remote get-url origin
  git_value "$path" 'origin.push' 1 remote get-url --push origin

  # --no-optional-locks prevents the otherwise read-shaped status command from
  # refreshing and rewriting the index. Disabling fsmonitor prevents execution
  # of a repo-local fsmonitor command from Git config.
  status_lines="$(
    GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$path" \
      status --porcelain=v1 --untracked-files=all 2>/dev/null | wc -l
  )"
  printf 'status.lines=%s\n' "$status_lines"
  printf 'venv='; [[ -d "$path/.venv" ]] && echo yes || echo no

  if git_dir="$(GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$path" rev-parse --absolute-git-dir 2>/dev/null)"; then
    hooks_dir="$git_dir/hooks"
    printf 'custom_hook_seats='
    if [[ -d "$hooks_dir" ]]; then
      find "$hooks_dir" -maxdepth 1 -type f ! -name '*.sample' -printf '%f ' 2>/dev/null || true
    fi
    echo
  else
    echo 'custom_hook_seats=<unavailable>'
  fi
}

for command_name in bash docker git readlink stat find basename tr tail wc du df; do
  require_command "$command_name"
done
if [[ ! -f "$COMPOSE" ]]; then
  printf 'ERROR: compose file does not exist: %s\n' "$COMPOSE" >&2
  exit 2
fi
if ! docker compose version >/dev/null 2>&1; then
  echo 'ERROR: docker compose is unavailable' >&2
  exit 2
fi
if [[ "$(docker inspect "$SERVICE" --format '{{.State.Running}}' 2>/dev/null || true)" != "true" ]]; then
  printf 'ERROR: container is not running: %s\n' "$SERVICE" >&2
  exit 2
fi

section 'HOST CHECKOUTS'
repo_facts 'operator development clone' "$HOME_REPO"
repo_facts 'deployment mirror' "$DEPLOY_REPO"

section 'CONTAINER MOUNTS (paths and RW flag only)'
docker inspect "$SERVICE" --format '{{range .Mounts}}{{println .Type .Source "->" .Destination "rw=" .RW}}{{end}}'

section 'CONTAINER-CREATION ENV RELEVANT TO SESSION SELECTION'
docker compose -f "$COMPOSE" exec -T "$SERVICE" bash -c '
  printf "FA_SESSION_ID=%q\n" "${FA_SESSION_ID-<unset>}"
  printf "FA_WORKSPACE=%q\n" "${FA_WORKSPACE-<unset>}"
  printf "PYTHONPATH=%q\n" "${PYTHONPATH-<unset>}"
  printf "PWD=%q\n" "$PWD"
'

section 'ACTIVE ENTRYPOINT WORKSPACE'
# Missing .active is a valid observable result. Keep the `|| true` inside the
# substitution so `set -o pipefail` does not terminate the probe prematurely.
ACTIVE_RAW="$(docker compose -f "$COMPOSE" exec -T "$SERVICE" cat /sessions/.active 2>/dev/null || true)"
ACTIVE="$(printf '%s' "$ACTIVE_RAW" | tr -d '\r' | tail -1)"
ACTIVE_VALID=0
SID=""
if [[ -z "$ACTIVE" ]]; then
  echo 'active=<missing>'
elif [[ "$ACTIVE" =~ ^/sessions/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]]; then
  ACTIVE_VALID=1
  SID="$(basename -- "$ACTIVE")"
  print_safe_value 'active' "$ACTIVE"
  print_safe_value 'active.basename' "$SID"
else
  print_safe_value 'active.invalid' "$ACTIVE"
  warn '/sessions/.active did not match the canonical contained session path; skipping workspace Git inspection'
fi

if [[ "$ACTIVE_VALID" == "1" ]]; then
  docker compose -f "$COMPOSE" exec -T -e ACTIVE="$ACTIVE" -e SID="$SID" "$SERVICE" bash -c '
    set -Eeuo pipefail
    print_value() { printf "%s=%q\n" "$1" "$2"; }
    redact_url() {
      local value="$1"
      if [[ "$value" =~ ^(https?://)[^/@]+@(.+)$ ]]; then
        value="${BASH_REMATCH[1]}<redacted>@${BASH_REMATCH[2]}"
      fi
      printf "%s" "$value"
    }
    git_value() {
      local label="$1" redact="$2" value
      shift 2
      if value="$(GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$ACTIVE" "$@" 2>/dev/null)"; then
        [[ "$redact" == "1" ]] && value="$(redact_url "$value")"
        print_value "$label" "$value"
      else
        print_value "$label" "<unset-or-unavailable>"
      fi
    }

    active_real="$(readlink -f -- "$ACTIVE")"
    print_value "active.realpath" "$active_real"
    stat -c "active.stat=device:%d inode:%i mode:%a owner:%u:%g" -- "$ACTIVE"
    git_value "active.head" 0 rev-parse HEAD
    git_value "active.branch" 0 branch --show-current
    git_value "active.origin.fetch" 1 remote get-url origin
    git_value "active.origin.push" 1 remote get-url --push origin
    status_lines="$(
      GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$ACTIVE" \
        status --porcelain=v1 --untracked-files=all 2>/dev/null | wc -l
    )"
    printf "active.status.lines=%s\n" "$status_lines"
    printf "active.venv="; [[ -d "$ACTIVE/.venv" ]] && echo yes || echo no
    printf "active.ready.marker="; [[ -f "$ACTIVE/.fa/ready-state.json" ]] && echo yes || echo no
    hooks="$(GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$ACTIVE" rev-parse --git-path hooks)"
    for hook_name in pre-commit pre-push prepare-commit-msg commit-msg; do
      if [[ -x "$hooks/$hook_name" ]]; then result=executable
      elif [[ -e "$hooks/$hook_name" ]]; then result=present-not-executable
      else result=missing
      fi
      printf "active.hook.%s=%s\n" "$hook_name" "$result"
    done
    manifest="/home/fa/.fa/sessions/$SID/manifest.json"
    printf "active.manifest="; [[ -f "$manifest" ]] && echo yes || echo no
  '

  HOST_ACTIVE="/srv/first-agent/sessions/${SID}"
  if [[ -d "$HOST_ACTIVE" ]]; then
    stat -c 'host_active.stat=device:%d inode:%i mode:%a owner:%u:%g' -- "$HOST_ACTIVE"
  else
    echo 'host_active=<missing>'
  fi
fi

section 'SESSION MANIFESTS (identity and workspace only)'
# -I ignores PYTHONPATH/user site and -B forbids pyc writes. repr() escapes any
# terminal control characters in agent-writable manifest string fields.
docker compose -f "$COMPOSE" exec -T "$SERVICE" python3 -I -B - <<'PY'
import json
from pathlib import Path

root = Path("/home/fa/.fa/sessions")
for path in sorted(root.glob("*/manifest.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"{str(path)!r}: CORRUPT {type(exc).__name__}")
        continue
    print(
        f"id={data.get('session_id')!r} status={data.get('status')!r} "
        f"workspace={data.get('workspace_path')!r}"
    )
PY

section 'WHAT A DEFAULT fa run WOULD CONFIGURE (NO SESSION CREATION)'
# SessionManager.__init__ calls mkdir(exist_ok=True). Require both directories to
# exist first so this diagnostic cannot create missing state while probing.
if docker compose -f "$COMPOSE" exec -T "$SERVICE" \
    sh -c 'test -d /sessions && test -d /home/fa/.fa/sessions'; then
  docker compose -f "$COMPOSE" exec -T "$SERVICE" python3 -I -B - <<'PY'
import argparse
from fa.cli import _session_manager_for_args

args = argparse.Namespace(workspace=None)
manager = _session_manager_for_args(args)
print("arg.workspace=None")
print(f"manager.workspace_root={str(manager.workspace_root)!r}")
print(f"manager.source_workspace={str(manager.source_workspace)!r}")
print("create_or_attach(session_id=None, workspace_override=None) => new generated session")
PY
else
  warn 'canonical session roots are missing; skipped SessionManager construction to keep the probe non-mutating'
fi

section 'CACHE / FILESYSTEM BASELINE (NO CLEANUP)'
if [[ "$ACTIVE_VALID" == "1" ]]; then
  docker compose -f "$COMPOSE" exec -T -e ACTIVE="$ACTIVE" "$SERVICE" bash -c '
    df -T /sessions /tmp/uv-cache /home/fa/.cache 2>/dev/null || true
    du -sh /tmp/uv-cache 2>/dev/null || true
    du -sh /home/fa/.cache/pre-commit 2>/dev/null || true
    du -sh "$ACTIVE/.venv" 2>/dev/null || true
  '
else
  docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -c '
    df -T /sessions /tmp/uv-cache /home/fa/.cache 2>/dev/null || true
    du -sh /tmp/uv-cache 2>/dev/null || true
    du -sh /home/fa/.cache/pre-commit 2>/dev/null || true
  '
fi

section 'RESULT'
echo 'probe=complete (read-only diagnostics; no session or LLM was created)'
