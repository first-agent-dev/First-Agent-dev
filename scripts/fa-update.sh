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
# Hash-tracking state lives OUTSIDE the repo (ADR-12: never write tracking files
# into the agent's /workspace). Defaults to the host state dir.
ENV_HASH_FILE="${ENV_HASH_FILE:-/srv/first-agent/state/.env.fa.sha256}"
# Secret isolation (ADR-12 Option C): LLM keys live here, consumed ONLY by the
# egress-proxy container. The fa->proxy token and models.yaml routing also
# trigger a recreate when changed (the proxy reads all three at startup).
SECRETS_ENV="${SECRETS_ENV:-/srv/first-agent/secrets/fa.env}"
PROXY_TOKEN_FILE="${PROXY_TOKEN_FILE:-/srv/first-agent/secrets/fa_proxy_token}"
MODELS_YAML_FILE="${MODELS_YAML_FILE:-/srv/first-agent/routing/models.yaml}"
ROUTING_DIR="${ROUTING_DIR:-$(dirname "${MODELS_YAML_FILE}")}"
# SUNSET (remove after 2026-12-01, once all hosts run the unified routing file):
# one-time migration inputs from the pre-unification layouts. They are only read
# when routing/models.yaml does not yet exist; after migration they are ignored.
LEGACY_STATE_MODELS="${LEGACY_STATE_MODELS:-/srv/first-agent/state/models.yaml}"
LEGACY_PROXY_MODELS="${LEGACY_PROXY_MODELS:-/srv/first-agent/proxy/models.yaml}"

SERVICE_NAME_OVERRIDE="${SERVICE_NAME_OVERRIDE:-}"

NO_CACHE="${NO_CACHE:-0}"
COMPOSE_BUILD_PULL="${COMPOSE_BUILD_PULL:-1}"

AUTO_STASH="${AUTO_STASH:-0}"
SKIP_TESTS="${SKIP_TESTS:-0}"
SKIP_UV_SYNC="${SKIP_UV_SYNC:-0}"

HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-90}"

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
_FA_UPDATE_REEXEC="${_FA_UPDATE_REEXEC:-0}"
_FA_UPDATE_REEXEC_HEAD_CHANGED="${_FA_UPDATE_REEXEC_HEAD_CHANGED:-0}"

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

ensure_routing_models() {
  # Migration/idempotency: both containers now mount the SAME routing file
  # read-only. Legacy state/proxy copies are inputs only; no proxy copy is
  # maintained after this point.
  local example_models="${REPO_DIR}/knowledge/examples/models.yaml.example"
  sudo mkdir -p "${ROUTING_DIR}"
  sudo chown 1000:1000 "${ROUTING_DIR}"
  sudo chmod 750 "${ROUTING_DIR}"

  if [[ ! -f "${MODELS_YAML_FILE}" ]]; then
    if [[ -f "${LEGACY_STATE_MODELS}" ]]; then
      sudo cp "${LEGACY_STATE_MODELS}" "${MODELS_YAML_FILE}"
      echo "  → Migrated legacy routing config: ${LEGACY_STATE_MODELS} → ${MODELS_YAML_FILE}"
    elif [[ -f "${LEGACY_PROXY_MODELS}" ]]; then
      sudo cp "${LEGACY_PROXY_MODELS}" "${MODELS_YAML_FILE}"
      echo "  → Migrated legacy routing config: ${LEGACY_PROXY_MODELS} → ${MODELS_YAML_FILE}"
    elif [[ -f "${example_models}" ]]; then
      sudo cp "${example_models}" "${MODELS_YAML_FILE}"
      echo "  ⚠ Created routing template at ${MODELS_YAML_FILE}; edit it before fa run."
    else
      sudo tee "${MODELS_YAML_FILE}" >/dev/null <<'EOF'
coder:
  model: "deepseek-v3"
  family: "deepseek"
  chain:
    - provider: openrouter
      slug: "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
EOF
      echo "  ⚠ Created fallback routing template at ${MODELS_YAML_FILE}; edit it before fa run."
    fi
  fi

  sudo chown 1000:1000 "${MODELS_YAML_FILE}"
  sudo chmod 640 "${MODELS_YAML_FILE}"
}

validate_file_mount_sources() {
  local required_files=(
    "${SECRETS_ENV}"
    "${PROXY_TOKEN_FILE}"
    "/srv/first-agent/secrets/github_deploy_key"
    "/srv/first-agent/secrets/known_hosts"
    "${MODELS_YAML_FILE}"
  )
  local missing=0
  for path in "${required_files[@]}"; do
    if [[ -d "${path}" ]]; then
      echo "  ✗ Mount source is a DIRECTORY (should be a file): ${path}"
      missing=1
    elif [[ ! -e "${path}" ]]; then
      echo "  ✗ Required file bind-mount source missing: ${path}"
      missing=1
    fi
  done
  if [[ "${missing}" -ne 0 ]]; then
    echo "  ✗ Aborting before docker compose up. Run setup-fa-desktop.sh or restore the missing files."
    exit 1
  fi
}

normalize_env_files() {
  local normalizer="${REPO_DIR}/scripts/fa-normalize-env.sh"
  if [[ -f "${normalizer}" ]]; then
    env \
      REPO_DIR="${REPO_DIR}" \
      ENV_FA="${ENV_FA}" \
      SECRETS_ENV="${SECRETS_ENV}" \
      BACKUP_DIR="/srv/first-agent/secrets" \
      bash "${normalizer}"
  fi
}

get_service_name() {
  if [[ -n "${SERVICE_NAME_OVERRIDE}" ]]; then
    echo "${SERVICE_NAME_OVERRIDE}"
    return
  fi
  # Pin to the agent service explicitly. We must NOT pick the first service from
  # `docker compose config --services`: that output's order is not guaranteed by
  # the compose spec and is sorted in several Docker Compose versions, where
  # 'fa-egress-proxy' (e) sorts before 'first-agent' (i). Selecting the proxy
  # would make health waits, smoke tests, and `cd /workspace && pytest` all
  # target the proxy container — which deliberately has NO /workspace mount,
  # producing confusing deploy failures while the agent is actually healthy.
  # The agent service name is stable (container_name/hostname in compose).
  local services fallback
  services=$(docker compose -f "${COMPOSE_FILE}" config --services 2>/dev/null || true)
  if grep -qx 'first-agent' <<<"${services}"; then
    echo "first-agent"
    return
  fi
  # Fall back to the first non-proxy service if the canonical name ever changes.
  fallback=$(grep -v '^fa-egress-proxy$' <<<"${services}" | head -n1 || true)
  echo "${fallback:-first-agent}"
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
  # `grep` exits 1 when nothing matches; under `set -Eeuo pipefail` that 1
  # propagates out of the command substitution and trips the ERR trap, aborting
  # the deploy even though "no active FA_* vars" is the expected, valid case
  # (the caller guards on an empty result). `|| true` keeps the no-match case a
  # success without masking sed/sort failures.
  { grep -E '^[[:space:]]*FA_[A-Z0-9_]+[[:space:]]*=' "${file}" 2>/dev/null || true; } \
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
      if git stash push -u -m "auto-stash $(date -u '+%Y%m%dT%H%M%SZ')"; then
        STASHED=1
      else
        echo "  ✗ git stash failed — resolve local changes manually and rerun."
        exit 1
      fi
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
    STASHED=0
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

  # Detect changes to any input the running containers read at startup (require
  # restart, not rebuild): non-secret controls (.env.fa), the LLM keys file +
  # fa->proxy token + routing (all consumed by the egress-proxy /
  # agent at boot). Persist the new hash only after deploy succeeds; otherwise a
  # failed deploy could hide a change on the next run.
  if [[ -f "${ENV_FA}" || -f "${SECRETS_ENV}" || -f "${PROXY_TOKEN_FILE}" || -f "${MODELS_YAML_FILE}" ]]; then
    local current_hash prev_hash
    current_hash=$(cat "${ENV_FA}" "${SECRETS_ENV}" "${PROXY_TOKEN_FILE}" "${MODELS_YAML_FILE}" 2>/dev/null | sha256sum | awk '{print $1}')
    ENV_HASH_VALUE="${current_hash}"
    ENV_HASH_PENDING=1
    if [[ -f "${ENV_HASH_FILE}" ]]; then
      prev_hash=$(cat "${ENV_HASH_FILE}" || true)
      if [[ "${current_hash}" != "${prev_hash}" ]]; then
        NEEDS_RESTART=1
        echo "  → env/secrets/proxy-token/routing changed (hash mismatch) → restart needed."
      fi
    else
      NEEDS_RESTART=1
      echo "  → First run with hash tracking → restart needed."
    fi
  else
    echo "  ⚠ No env/secrets/proxy inputs found. Containers will use defaults."
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
    # Back up OUTSIDE the repo/workspace (the agent's RW mount). Even though a
    # post-migration .env.fa holds only non-secret FA_* controls, never drop
    # *.bak into /workspace — it is the same anti-pattern that leaked keys via
    # the migration backup (ADR-12). Park it in the host state dir.
    _state_dir="$(dirname "${ENV_HASH_FILE}")"
    mkdir -p "${_state_dir}" 2>/dev/null || true
    cp "${ENV_FA}" "${_state_dir}/$(basename "${ENV_FA}").bak-$(date +%s)"
    echo "  → Backed up ${ENV_FA} to ${_state_dir}"
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
#  Step 5b — Egress-proxy health + LLM-path probe
# ═══════════════════════════════════════════════════════════════
# A healthy agent (fa --version) does NOT prove the LLM tract works: keys live
# in the proxy, routing is a separate copy, and the agent reaches providers only
# THROUGH the proxy. Verify (a) the proxy container is healthy and (b) the agent
# can actually reach it, so a broken update (stale routing copy, bad token,
# crashed proxy) is caught here instead of on the operator's first `fa run`
# (where it shows up as the opaque chain_exhausted). Warn-only: it never fails
# the update — the agent itself may be fine and the cause operator-fixable.
check_proxy_path() {
  echo ""
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  STEP 5b — Egress-proxy health + LLM-path probe  ║"
  echo "╚═══════════════════════════════════════════════════╝"

  local pid phealth
  pid=$(compose_container_id "fa-egress-proxy")
  if [[ -z "${pid}" ]]; then
    echo "  ⚠ No fa-egress-proxy container found — the agent cannot call any LLM."
    return
  fi
  phealth=$(health_status "${pid}")
  case "${phealth}" in
    healthy | no-healthcheck) echo "  ✓ fa-egress-proxy status=${phealth}." ;;
    *) echo "  ⚠ fa-egress-proxy not healthy (status=${phealth}); 'fa run' will fail." ;;
  esac

  # Agent → proxy reachability (routing-independent: just /healthz).
  if docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE_NAME}" \
      python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://fa-egress-proxy:8080/healthz',timeout=5).status==200 else 1)" \
      >/dev/null 2>&1; then
    echo "  ✓ Agent can reach the proxy at http://fa-egress-proxy:8080/healthz."
  else
    echo "  ⚠ Agent could NOT reach the proxy. 'fa run' will fail (chain_exhausted)."
    echo "    Logs: docker compose -f ${COMPOSE_FILE} logs fa-egress-proxy"
  fi

  # Deeper diagnostic (warn-only): `fa selfcheck` validates that the proxy's
  # route table matches the agent's models.yaml AND that a provider key is
  # present for every route — the real causes of "both healthy but
  # chain_exhausted". /healthz above only proves reachability. Never fails the
  # update: the agent may be fine and any finding is operator-fixable.
  echo "  → Running fa selfcheck (route/key drift)..."
  if docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE_NAME}" fa selfcheck; then
    echo "  ✓ fa selfcheck passed."
  else
    echo "  ⚠ fa selfcheck reported a problem (see above); fix it before 'fa run'."
  fi
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
  # STEP 7 is non-fatal by contract: a failing test must NOT abort the deploy
  # (the stack is already up). `set +e` alone is insufficient here — the script
  # runs with `set -E` (errtrace), so the ERR trap still fires on a non-zero
  # command even with errexit disabled. Disable the ERR trap for this block and
  # restore it afterwards so a red pytest is recorded in TEST_RC, not fatal.
  set +e
  trap - ERR
  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE_NAME}" \
    bash -lc 'cd /workspace && if command -v uv >/dev/null 2>&1; then uv run python -m pytest -v --tb=short; else python -m pytest -v --tb=short; fi'
  TEST_RC=$?
  trap 'rc=$?; echo "❌ ERROR at line ${LINENO}: ${BASH_COMMAND}"; exit "${rc}"' ERR
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
  if [[ "${HEAD_CHANGED}" == "1" && "${_FA_UPDATE_REEXEC}" != "1" && "${STASHED}" != "1" ]]; then
    echo "  → Re-executing updated fa-update.sh so deploy uses the new script logic..."
    export _FA_UPDATE_REEXEC=1
    export _FA_UPDATE_REEXEC_HEAD_CHANGED=1
    export REPO_DIR COMPOSE_FILE ENV_TEMPLATE ENV_FA ENV_HASH_FILE SECRETS_ENV       PROXY_TOKEN_FILE MODELS_YAML_FILE ROUTING_DIR LEGACY_STATE_MODELS       LEGACY_PROXY_MODELS SERVICE_NAME_OVERRIDE NO_CACHE COMPOSE_BUILD_PULL       AUTO_STASH SKIP_TESTS SKIP_UV_SYNC HEALTH_TIMEOUT_SECONDS PRUNE PRUNE_UNTIL
    exec bash "${REPO_DIR}/scripts/fa-update.sh" "$@"
  fi
  if [[ "${_FA_UPDATE_REEXEC_HEAD_CHANGED}" == "1" ]]; then
    HEAD_CHANGED=1
    echo "  → Continuing after re-exec; preserving HEAD_CHANGED=1 for build/deploy."
  fi

  SERVICE_NAME=$(get_service_name)
  echo "  → Service: ${SERVICE_NAME}"

  normalize_env_files
  ensure_routing_models
  evaluate_changes
  validate_env
  validate_file_mount_sources
  build_and_deploy
  wait_for_health
  check_proxy_path
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
