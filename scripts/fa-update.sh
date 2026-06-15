#!/usr/bin/env bash
# fa-update.sh — host-side update/deploy helper for the FA AIO container.
#
# Intended use on the deployment host:
#   /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
#
# The script is deliberately conservative: it refuses dirty working trees
# unless AUTO_STASH=1, pulls main with --ff-only, rebuilds/restarts when
# inputs changed, waits for container health, runs smoke checks, optionally
# runs tests, and leaves the container running for inspection.

set -Eeuo pipefail

# ═══════════════════════════════════════════════════════════════
#  Configuration (override via environment variables)
# ═══════════════════════════════════════════════════════════════

REPO_DIR="${REPO_DIR:-/srv/first-agent/repo/First-Agent-dev}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.fa.yml}"

ENV_TEMPLATE="${ENV_TEMPLATE:-.env.fa.template}"
ENV_FA="${ENV_FA:-.env.fa}"
ENV_HASH_FILE="${ENV_HASH_FILE:-.env.fa.sha256}"

SERVICE_NAME_OVERRIDE="${SERVICE_NAME_OVERRIDE:-}"

NO_CACHE="${NO_CACHE:-0}"
COMPOSE_BUILD_PULL="${COMPOSE_BUILD_PULL:-1}"

AUTO_STASH="${AUTO_STASH:-0}"
SKIP_TESTS="${SKIP_TESTS:-0}"
SKIP_UV_SYNC="${SKIP_UV_SYNC:-0}"

HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-60}"

PRUNE="${PRUNE:-1}"
PRUNE_UNTIL="${PRUNE_UNTIL:-72h}"

# Derived
LOCK_FILE="${LOCK_FILE:-/tmp/fa-update.lock}"
LOG_FILE="${LOG_FILE:-/tmp/fa-update.log}"

# Runtime state
STASHED=0
HEAD_CHANGED=0
NEEDS_BUILD=0
NEEDS_RESTART=0
TEST_RC=0
SERVICE_NAME="first-agent"
ENV_HASH_PENDING=0
ENV_HASH_VALUE=""

# ═══════════════════════════════════════════════════════════════
#  Logging / Locking / Error handling
# ═══════════════════════════════════════════════════════════════

exec 9>"${LOCK_FILE}"
flock -n 9 || {
  echo "Update already running (lock: ${LOCK_FILE}). Exiting."
  exit 1
}

exec > >(tee -a "${LOG_FILE}") 2>&1
# shellcheck disable=SC2154  # rc IS assigned (rc=$?) inside this same trap string.
trap 'rc=$?; echo "❌ ERROR at line ${LINENO}: ${BASH_COMMAND}"; exit "${rc}"' ERR

# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing command: $1"
    exit 1
  }
}

get_service_name() {
  if [[ -n "${SERVICE_NAME_OVERRIDE}" ]]; then
    echo "${SERVICE_NAME_OVERRIDE}"
    return
  fi
  local svc
  svc=$(docker compose -f "${COMPOSE_FILE}" config --services 2>/dev/null | head -n1 || true)
  echo "${svc:-first-agent}"
}

compose_container_id() {
  docker compose -f "${COMPOSE_FILE}" ps -q "$1" 2>/dev/null || true
}

health_status() {
  local cid="$1"
  if [[ -z "${cid}" ]]; then
    echo "missing"
    return
  fi
  docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \
    "${cid}" 2>/dev/null || echo "unknown"
}

extract_active_fa_vars() {
  local file="$1"
  # Only uncommented FA_* assignments are required. Commented FA_* rows in
  # .env.fa.template document optional controls and must not make deploys fail.
  grep -E '^[[:space:]]*FA_[A-Z0-9_]+[[:space:]]*=' "${file}" 2>/dev/null \
    | sed -E 's/^[[:space:]]*(FA_[A-Z0-9_]+)[[:space:]]*=.*$/\1/' \
    | sort -u
}

# ═══════════════════════════════════════════════════════════════
#  Step 0 — Preflight
# ═══════════════════════════════════════════════════════════════

preflight_checks() {
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 0 — Preflight checks                       ║"
  echo "╚═══════════════════════════════════════════════════╝"

  need_cmd git
  need_cmd docker
  need_cmd sha256sum
  need_cmd awk
  need_cmd grep
  need_cmd sed
  need_cmd flock

  docker compose version >/dev/null 2>&1 || {
    echo "  ✗ docker compose not available"
    exit 1
  }

  local disk_usage
  disk_usage=$(df -h /var/lib/docker 2>/dev/null | awk 'NR==2 {print $5}' | tr -d '%')
  if [[ -n "${disk_usage}" ]] && ((disk_usage > 90)); then
    echo "  ✗ Disk usage at ${disk_usage}% (>90%). Aborting."
    exit 1
  fi

  echo "  ✓ Commands available, Docker OK, disk space OK."
}

# ═══════════════════════════════════════════════════════════════
#  Step 1 — Git update & change detection
# ═══════════════════════════════════════════════════════════════

git_update() {
  echo ""
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 1 — Git update & change detection          ║"
  echo "╚═══════════════════════════════════════════════════╝"

  cd "${REPO_DIR}"

  STASHED=0

  if [[ -n "$(git status --porcelain)" ]]; then
    echo "  ⚠ Dirty working tree detected."
    git status --short || true
    if [[ "${AUTO_STASH}" == "1" ]]; then
      echo "  → Auto-stashing (AUTO_STASH=1)..."
      git stash push -u -m "auto-stash $(date -u '+%Y%m%dT%H%M%SZ')" || true
      STASHED=1
    else
      echo "  ✗ Aborting. Commit/stash manually, or set AUTO_STASH=1."
      exit 1
    fi
  fi

  git fetch origin --prune

  local current_branch
  current_branch=$(git rev-parse --abbrev-ref HEAD)
  if [[ "${current_branch}" != "main" ]]; then
    echo "  → Switching from ${current_branch} to main..."
    git switch main 2>/dev/null || git checkout main
  fi

  local before after
  before=$(git rev-parse HEAD)
  git pull --ff-only origin main
  after=$(git rev-parse HEAD)

  if [[ "${STASHED}" == "1" ]]; then
    echo "  → Restoring stashed changes..."
    git stash pop || {
      echo "  ✗ Stash pop failed — resolve conflicts and rerun."
      exit 1
    }
  fi

  HEAD_CHANGED=0
  if [[ "${before}" != "${after}" ]]; then
    HEAD_CHANGED=1
    echo "  ✓ Updated: ${before:0:8} → ${after:0:8} ($(git rev-list --count "${before}".."${after}") commit(s))"
    git log --oneline "${before}..${after}"
  else
    echo "  ✓ Already up to date at ${after}."
  fi
}

# ═══════════════════════════════════════════════════════════════
#  Step 2 — Decide build vs restart
# ═══════════════════════════════════════════════════════════════

evaluate_changes() {
  echo ""
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 2 — Change evaluation                      ║"
  echo "╚═══════════════════════════════════════════════════╝"

  NEEDS_BUILD=0
  NEEDS_RESTART=0
  ENV_HASH_PENDING=0
  ENV_HASH_VALUE=""

  if [[ "${HEAD_CHANGED}" == "1" ]]; then
    NEEDS_BUILD=1
    NEEDS_RESTART=1
  fi

  # Detect .env.fa changes (requires restart, not necessarily rebuild).
  # Persist the new hash only after deploy succeeds; otherwise a failed deploy
  # could hide an env change on the next run.
  if [[ -f "${ENV_FA}" ]]; then
    local current_hash prev_hash
    current_hash=$(sha256sum "${ENV_FA}" | awk '{print $1}')
    ENV_HASH_VALUE="${current_hash}"
    ENV_HASH_PENDING=1
    if [[ -f "${ENV_HASH_FILE}" ]]; then
      prev_hash=$(cat "${ENV_HASH_FILE}" || true)
      if [[ "${current_hash}" != "${prev_hash}" ]]; then
        NEEDS_RESTART=1
        echo "  → ${ENV_FA} changed (hash mismatch) → restart needed."
      fi
    else
      NEEDS_RESTART=1
      echo "  → First run with hash tracking → restart needed."
    fi
  else
    echo "  ⚠ ${ENV_FA} not found. Container will use defaults."
    NEEDS_RESTART=1
  fi

  # If no git changes, check if build-critical files were modified in working tree.
  if [[ "${HEAD_CHANGED}" == "0" ]]; then
    local critical_files=(
      "docker-compose.fa.yml"
      "Dockerfile.fa"
      "pyproject.toml"
      "uv.lock"
      ".dockerignore"
      "scripts/fa-entrypoint.sh"
    )
    for f in "${critical_files[@]}"; do
      if [[ -f "${f}" ]] && ! git diff --quiet -- "${f}" 2>/dev/null; then
        echo "  → Working-tree change in ${f} → build needed."
        NEEDS_BUILD=1
        NEEDS_RESTART=1
        break
      fi
    done
  fi

  echo "  Summary: NEEDS_BUILD=${NEEDS_BUILD}  NEEDS_RESTART=${NEEDS_RESTART}"

  if [[ "${NEEDS_BUILD}" == "0" && "${NEEDS_RESTART}" == "0" ]]; then
    echo "  ✓ No changes detected. Skipping build/deploy."
    echo "--- Update completed at $(date -Is) (no-op) ---"
    exit 0
  fi
}

# ═══════════════════════════════════════════════════════════════
#  Step 3 — Environment variable validation
# ═══════════════════════════════════════════════════════════════

validate_env() {
  echo ""
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 3 — Environment variable validation        ║"
  echo "╚═══════════════════════════════════════════════════╝"

  if [[ ! -f "${ENV_TEMPLATE}" || ! -f "${ENV_FA}" ]]; then
    echo "  ⚠ Skipping (missing ${ENV_TEMPLATE} or ${ENV_FA})."
    return
  fi

  local tmpl_vars env_vars missing
  tmpl_vars=$(extract_active_fa_vars "${ENV_TEMPLATE}")
  env_vars=$(extract_active_fa_vars "${ENV_FA}")

  if [[ -z "${tmpl_vars}" ]]; then
    echo "  ✓ No required active FA_* vars found in ${ENV_TEMPLATE}; optional commented controls ignored."
    return
  fi

  missing=$(comm -23 <(echo "${tmpl_vars}") <(echo "${env_vars}") || true)
  if [[ -n "${missing}" ]]; then
    echo "  ✗ Variables missing from ${ENV_FA} (active in template):"
    echo "${missing}" | sed 's/^/    - /'
    cp "${ENV_FA}" "${ENV_FA}.bak-$(date +%s)"
    echo "  → Backed up ${ENV_FA}"
  else
    echo "  ✓ All active template variables present in ${ENV_FA}."
  fi
}

# ═══════════════════════════════════════════════════════════════
#  Step 4 — Build & deploy
# ═══════════════════════════════════════════════════════════════

build_and_deploy() {
  echo ""
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 4 — Build & deploy                         ║"
  echo "╚═══════════════════════════════════════════════════╝"

  if [[ "${NEEDS_BUILD}" == "1" ]]; then
    echo "  → Building images..."
    local build_cmd=(docker compose -f "${COMPOSE_FILE}" build)
    [[ "${COMPOSE_BUILD_PULL}" == "1" ]] && build_cmd+=(--pull)
    [[ "${NO_CACHE}" == "1" ]] && build_cmd+=(--no-cache)
    "${build_cmd[@]}"
  fi

  if [[ "${NEEDS_RESTART}" == "1" ]]; then
    echo "  → Deploying containers..."
    local up_cmd=(docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans)
    # Force recreate when env changed but no rebuild (picks up new env vars).
    [[ "${NEEDS_BUILD}" == "0" ]] && up_cmd+=(--force-recreate)
    "${up_cmd[@]}"
  fi

  if [[ "${ENV_HASH_PENDING}" == "1" && -n "${ENV_HASH_VALUE}" ]]; then
    echo "${ENV_HASH_VALUE}" >"${ENV_HASH_FILE}"
  fi

  # Ensure host-side scripts are executable after checkout/update.
  if [[ -d "scripts" ]]; then
    find scripts/ -name '*.sh' -type f -exec chmod +x {} + || true
  fi
}

# ═══════════════════════════════════════════════════════════════
#  Step 5 — Health check
# ═══════════════════════════════════════════════════════════════

wait_for_health() {
  echo ""
  echo "  → Waiting up to ${HEALTH_TIMEOUT_SECONDS}s for ${SERVICE_NAME} health..."

  local status="missing" cid=""
  for i in $(seq 1 "${HEALTH_TIMEOUT_SECONDS}"); do
    cid=$(compose_container_id "${SERVICE_NAME}")
    status=$(health_status "${cid}")
    case "${status}" in
      healthy | no-healthcheck)
        echo "  ✓ ${SERVICE_NAME} status=${status} after ${i}s."
        return 0
        ;;
      missing)
        # Container may not be created yet; keep waiting.
        sleep 1
        ;;
      *)
        sleep 1
        ;;
    esac
  done

  echo "  ⚠ Not healthy after ${HEALTH_TIMEOUT_SECONDS}s (status=${status})."
  echo "  → Last 200 log lines:"
  docker compose -f "${COMPOSE_FILE}" logs --tail=200 "${SERVICE_NAME}" || true
  return 1
}

# ═══════════════════════════════════════════════════════════════
#  Step 6 — Smoke tests
# ═══════════════════════════════════════════════════════════════

smoke_tests() {
  echo ""
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 6 — Smoke tests                            ║"
  echo "╚═══════════════════════════════════════════════════╝"

  local cid
  cid=$(compose_container_id "${SERVICE_NAME}")
  if [[ -z "${cid}" ]]; then
    echo "  ⚠ No running container found for ${SERVICE_NAME}. Skipping."
    return
  fi

  if docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE_NAME}" fa --version >/dev/null 2>&1; then
    echo "  ✓ fa CLI is available."
  else
    echo "  ⚠ fa CLI not found or not working."
  fi

  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE_NAME}" python - <<'PYEOF' || echo "  ⚠ Core imports failed."
from fa.cli import main
from fa.inner_loop.prompt import build_system_message
from fa.inner_loop.state import EventLog
from fa.inner_loop.tools import build_planner_registry, build_eval_registry
print("  ✓ Core Python imports OK.")
PYEOF

  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE_NAME}" bash -lc \
    "cat /workspace/.fa/entrypoint-status.txt 2>/dev/null || echo '  (no entrypoint status file — expected on first run)'" || true
}

# ═══════════════════════════════════════════════════════════════
#  Step 7 — Run tests
# ═══════════════════════════════════════════════════════════════

run_tests() {
  echo ""
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 7 — Run tests (non-fatal)                  ║"
  echo "╚═══════════════════════════════════════════════════╝"

  TEST_RC=0

  if [[ "${SKIP_TESTS}" == "1" ]]; then
    echo "  → Skipping (SKIP_TESTS=1)."
    return
  fi

  if [[ "${SKIP_UV_SYNC}" == "0" ]]; then
    if docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE_NAME}" \
      bash -lc 'cd /workspace && uv sync --frozen --extra dev' >/dev/null 2>&1; then
      echo "  ✓ Dev dependencies synced in /workspace."
    else
      echo "  ⚠ Failed to sync dev dependencies."
    fi
  fi

  echo "  → Running pytest..."
  set +e
  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE_NAME}" \
    bash -lc 'cd /workspace && if command -v uv >/dev/null 2>&1; then uv run python -m pytest -v --tb=short; else python -m pytest -v --tb=short; fi'
  TEST_RC=$?
  set -e

  if [[ "${TEST_RC}" -ne 0 ]]; then
    echo "  ⚠ pytest failed (rc=${TEST_RC}). Container is still running."
  else
    echo "  ✓ All tests passed."
  fi
}

# ═══════════════════════════════════════════════════════════════
#  Step 8 — Usage info
# ═══════════════════════════════════════════════════════════════

print_usage_info() {
  echo ""
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 8 — Usage info                             ║"
  echo "╚═══════════════════════════════════════════════════╝"

  cat <<USAGE

  Multi-role workflow (run individually, each calls an LLM):

    # Planner
    docker compose -f ${COMPOSE_FILE} exec -T ${SERVICE_NAME} fa run \
      --role planner --workspace /workspace --task "Build JWT auth" --run-id "workflow-1"

    # Coder (resumes planner's draft)
    docker compose -f ${COMPOSE_FILE} exec -T ${SERVICE_NAME} fa run \
      --role coder --workspace /workspace --task "Execute S1" --run-id "workflow-1" --resume

    # Evaluator (verifies coder's work)
    docker compose -f ${COMPOSE_FILE} exec -T ${SERVICE_NAME} fa run \
      --role eval --workspace /workspace --task "Verify S1" --run-id "workflow-1" --resume

  Auto-run mode (on next container start):

    Edit ${ENV_FA}:
      FA_AUTO_RUN=1
      FA_TASK=Build JWT auth
      FA_ROLE=planner
      FA_RUN_ID=auth-workflow

    Then restart:
      docker compose -f ${COMPOSE_FILE} restart

    Check result:
      docker compose -f ${COMPOSE_FILE} exec -T ${SERVICE_NAME} \
        cat /workspace/.fa/entrypoint-status.txt

USAGE
}

# ═══════════════════════════════════════════════════════════════
#  Cleanup
# ═══════════════════════════════════════════════════════════════

cleanup_images() {
  if [[ "${PRUNE}" == "1" ]]; then
    echo "  → Pruning images older than ${PRUNE_UNTIL}..."
    docker image prune -f --filter "until=${PRUNE_UNTIL}" >/dev/null 2>&1 || true
  fi
}

# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

main() {
  echo "============================================================"
  echo "🟢 fa-update started at $(date -Is)"
  echo "  Repo:    ${REPO_DIR}"
  echo "  Compose: ${COMPOSE_FILE}"
  echo "  Log:     ${LOG_FILE}"
  echo "============================================================"

  preflight_checks
  git_update

  SERVICE_NAME=$(get_service_name)
  echo "  → Service: ${SERVICE_NAME}"

  evaluate_changes
  validate_env
  build_and_deploy
  wait_for_health
  smoke_tests
  run_tests
  print_usage_info
  cleanup_images

  echo ""
  echo "============================================================"
  echo "✅ Update complete. HEAD: $(cd "${REPO_DIR}" && git rev-parse --short HEAD)"
  echo "   Health: $(health_status "$(compose_container_id "${SERVICE_NAME}")")"
  echo "   Tests:  rc=${TEST_RC}"
  echo "   Time:   $(date -Is)"
  echo "============================================================"

  exit "${TEST_RC}"
}

main "$@"
