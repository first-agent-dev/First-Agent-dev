#!/usr/bin/env bash
# fa-clean-rebuild.sh — tear down the FA stack and rebuild it clean (ADR-12).
#
# Intended use on the deployment host:
#   /srv/first-agent/repo/First-Agent-dev/scripts/fa-clean-rebuild.sh
#
# What it does (in order):
#   1. Preflight (docker/compose present, repo + compose file exist, secrets dir).
#   2. Back up /srv/first-agent/{state,secrets} to a timestamped 0700 dir.
#   3. Stop the systemd service + `docker compose down --remove-orphans`.
#   4. Reset run history (/srv/first-agent/state/runs/*); with WIPE_STATE=1 the
#      whole state dir, then recreate a models.yaml template (host-user-owned).
#   5. KEEP secrets/ untouched (LLM keys, deploy key, fa_proxy_token); generate
#      the fa->proxy token if it is missing. NEVER deletes secrets.
#   6. Rebuild images --no-cache and bring the TWO containers up
#      (fa-egress-proxy + first-agent), waiting for both to be healthy.
#   7. Verify secret isolation (agent holds no LLM key) and re-enable the service.
#
# Deliberately does NOT call setup-fa-desktop.sh: that script re-provisions the
# whole HOST (apt full-upgrade, Docker reinstall, UFW/SSH, etc.), which is unsafe
# to trigger from a container-rebuild. Only the container-scoped bits are inlined.
#
# Safe by design: persistent data lives in host bind-mounts, so removing
# containers/images never loses keys or config.
#
# Flags (env vars):
#   WIPE_STATE=1     clear ALL of state/ (models.yaml/config.yaml/history); a
#                    models.yaml template is recreated for you to re-fill.
#                    Keys in secrets/ are preserved. Default: keep state.
#   PRUNE=1          `docker system prune -af` after teardown (frees disk; removes
#                    ALL unused images/build cache). Default: off.
#   NO_BACKUP=1      skip the backup step (NOT recommended).
#   ASSUME_YES=1     do not prompt for confirmation on destructive flags.
#   HEALTH_TIMEOUT_SECONDS  per-container health wait (default 90).

set -Eeuo pipefail

# ═══════════════════════════════════════════════════════════════
#  Configuration (override via environment variables)
# ═══════════════════════════════════════════════════════════════
FA_DIR="${FA_DIR:-/srv/first-agent}"
REPO_DIR="${REPO_DIR:-${FA_DIR}/repo/First-Agent-dev}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.fa.yml}"
SERVICE="${SERVICE:-fa.service}"
FA_USER="${FA_USER:-$USER}"
WIPE_STATE="${WIPE_STATE:-0}"
NO_BACKUP="${NO_BACKUP:-0}"
PRUNE="${PRUNE:-0}"
ASSUME_YES="${ASSUME_YES:-0}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-90}"
EXAMPLE_MODELS="${REPO_DIR}/knowledge/examples/models.yaml.example"

log_info()  { echo -e "\033[0;32m[INFO]\033[0m  $*"; }
log_warn()  { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $*" >&2; }

on_error() { log_error "Failed at line $1. The stack may be partially rebuilt; re-run after fixing."; }
trap 'on_error $LINENO' ERR

if [[ $EUID -eq 0 ]]; then
    log_error "Do not run as root. Run as your normal user with passwordless sudo."
    exit 1
fi

# ───────────────────────────────────────────────────────────────
# 1. Preflight
# ───────────────────────────────────────────────────────────────
log_info "Preflight checks..."
command -v docker >/dev/null 2>&1 || { log_error "docker not found in PATH."; exit 1; }
docker compose version >/dev/null 2>&1 || { log_error "'docker compose' plugin not available."; exit 1; }
docker info >/dev/null 2>&1 || { log_error "Docker daemon not reachable (is it running? are you in the 'docker' group?)."; exit 1; }
[[ -d "${REPO_DIR}" ]] || { log_error "Repo dir not found: ${REPO_DIR}"; exit 1; }
[[ -f "${REPO_DIR}/${COMPOSE_FILE}" ]] || { log_error "Compose file not found: ${REPO_DIR}/${COMPOSE_FILE}"; exit 1; }
cd "${REPO_DIR}"

# Confirmation for destructive flags (skip with ASSUME_YES=1 or non-interactive).
if [[ "${WIPE_STATE}" == "1" || "${PRUNE}" == "1" ]] && [[ "${ASSUME_YES}" != "1" ]]; then
    [[ "${WIPE_STATE}" == "1" ]] && log_warn "WIPE_STATE=1 will DELETE all of ${FA_DIR}/state/* (keys are kept)."
    [[ "${PRUNE}" == "1" ]] && log_warn "PRUNE=1 will remove ALL unused Docker images + build cache."
    if [[ -t 0 ]]; then
        read -r -p "Proceed? [y/N] " reply
        [[ "${reply}" =~ ^[Yy]$ ]] || { log_info "Aborted by user."; exit 0; }
    else
        log_error "Destructive flags set but no TTY to confirm. Re-run with ASSUME_YES=1."
        exit 1
    fi
fi

# ───────────────────────────────────────────────────────────────
# 2. Backup (0700 — it contains secrets)
# ───────────────────────────────────────────────────────────────
BK=""
if [[ "${NO_BACKUP}" != "1" ]]; then
    BK="${HOME}/fa-backup-$(date +%Y%m%d-%H%M%S)"
    ( umask 077; mkdir -p "${BK}" )
    log_info "Backing up state + secrets to ${BK} (0700) ..."
    sudo cp -a "${FA_DIR}/state" "${BK}/state" 2>/dev/null || true
    sudo cp -a "${FA_DIR}/secrets" "${BK}/secrets" 2>/dev/null || true
    sudo chown -R "${USER}:${USER}" "${BK}" 2>/dev/null || true
    chmod -R go-rwx "${BK}" 2>/dev/null || true
    log_info "Backup done: ${BK}"
else
    log_warn "NO_BACKUP=1 — skipping backup."
fi

# ───────────────────────────────────────────────────────────────
# 3. Stop service + tear down containers
# ───────────────────────────────────────────────────────────────
log_info "Stopping systemd service (if present)..."
systemctl --user stop "${SERVICE}" 2>/dev/null || true

log_info "Tearing down containers (down --remove-orphans)..."
docker compose -f "${COMPOSE_FILE}" down --remove-orphans || true

if docker ps -a --format '{{.Names}}' | grep -qE '^(first-agent|fa-egress-proxy)$'; then
    log_warn "Some FA containers still present; forcing removal..."
    docker rm -f first-agent fa-egress-proxy 2>/dev/null || true
fi

if [[ "${PRUNE}" == "1" ]]; then
    log_warn "PRUNE=1 — removing ALL unused images + build cache..."
    docker system prune -af || true
fi

# ───────────────────────────────────────────────────────────────
# 4. Reset state (keys are NEVER touched here)
# ───────────────────────────────────────────────────────────────
# Always clear run history (safe; pure runtime artifacts).
if [[ -d "${FA_DIR}/state/runs" ]]; then
    log_info "Clearing run history (${FA_DIR}/state/runs/*)..."
    sudo rm -rf "${FA_DIR}/state/runs/"* 2>/dev/null || true
fi

if [[ "${WIPE_STATE}" == "1" ]]; then
    log_warn "WIPE_STATE=1 — clearing ALL of ${FA_DIR}/state/* (keys in secrets/ preserved)."
    sudo rm -rf "${FA_DIR}/state/"* 2>/dev/null || true
fi

# Recreate a models.yaml template if it is now missing (e.g. after WIPE_STATE),
# owned by the host user so the container (uid of FA_USER) can read/write it.
MODELS_YAML="${FA_DIR}/state/models.yaml"
if [[ ! -f "${MODELS_YAML}" ]]; then
    log_warn "No models.yaml — creating a template at ${MODELS_YAML} (EDIT IT to set providers)."
    sudo mkdir -p "${FA_DIR}/state"
    if [[ -f "${EXAMPLE_MODELS}" ]]; then
        sudo cp "${EXAMPLE_MODELS}" "${MODELS_YAML}"
    else
        sudo tee "${MODELS_YAML}" >/dev/null <<'EOF'
coder:
  model: "deepseek-v3"
  family: "deepseek"
  chain:
    - provider: openrouter
      slug: "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
EOF
    fi
fi
# Ensure state is owned by the host user (container runs as that uid).
sudo chown -R "${FA_USER}:${FA_USER}" "${FA_DIR}/state" 2>/dev/null || true

# ───────────────────────────────────────────────────────────────
# 5. Secrets: keep keys; ensure the fa->proxy token exists
# ───────────────────────────────────────────────────────────────
if [[ ! -s "${FA_DIR}/secrets/fa.env" ]]; then
    log_warn "No ${FA_DIR}/secrets/fa.env (LLM keys) — the agent cannot call providers until you set it:"
    log_warn "  sudo micro ${FA_DIR}/secrets/fa.env"
fi

TOKEN_FILE="${FA_DIR}/secrets/fa_proxy_token"
if [[ ! -s "${TOKEN_FILE}" ]]; then
    log_info "Generating fa->proxy token at ${TOKEN_FILE}..."
    sudo mkdir -p "${FA_DIR}/secrets"
    head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n' | sudo tee "${TOKEN_FILE}" >/dev/null
    sudo chmod 600 "${TOKEN_FILE}"
    sudo chown "${FA_USER}:${FA_USER}" "${TOKEN_FILE}" 2>/dev/null || true
fi
# Hard requirement: the proxy rejects the agent without this token.
if [[ ! -s "${TOKEN_FILE}" ]]; then
    log_error "Could not create ${TOKEN_FILE}. The proxy would reject the agent. Aborting."
    exit 1
fi

# ───────────────────────────────────────────────────────────────
# 6. Rebuild clean + bring up the two containers
# ───────────────────────────────────────────────────────────────
log_info "Building images (--no-cache)..."
docker compose -f "${COMPOSE_FILE}" build --no-cache

log_info "Starting stack via systemd service (single source of truth)..."
# The service's ExecStart is `docker compose up -d`; using it avoids a double
# `up -d` and keeps runtime ownership with systemd.
if ! systemctl --user start "${SERVICE}" 2>/dev/null; then
    log_warn "systemd service unavailable; starting with docker compose directly."
    docker compose -f "${COMPOSE_FILE}" up -d
fi

wait_for_health() {
    # $1 = container name; success = running AND (healthy | no healthcheck).
    local name="$1" status health
    local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
    while (( SECONDS < deadline )); do
        status=$(docker inspect --format='{{.State.Status}}' "${name}" 2>/dev/null || echo missing)
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${name}" 2>/dev/null || echo none)
        if [[ "${status}" == "running" && ( "${health}" == "healthy" || "${health}" == "none" ) ]]; then
            log_info "Container '${name}' is running (health=${health})."
            return 0
        fi
        if [[ "${status}" == "exited" || "${status}" == "dead" ]]; then
            return 1
        fi
        sleep 2
    done
    return 1
}

log_info "Waiting for fa-egress-proxy to become healthy..."
if ! wait_for_health "fa-egress-proxy"; then
    log_error "Egress proxy did not become healthy in ${HEALTH_TIMEOUT_SECONDS}s."
    log_error "  Check: ls -l ${TOKEN_FILE} ${MODELS_YAML}"
    log_error "  Logs:  docker compose -f ${COMPOSE_FILE} logs fa-egress-proxy"
    exit 1
fi

log_info "Waiting for first-agent to start..."
if ! wait_for_health "first-agent"; then
    log_error "Agent container did not start in ${HEALTH_TIMEOUT_SECONDS}s."
    log_error "  Logs: docker compose -f ${COMPOSE_FILE} logs first-agent"
    exit 1
fi

# ───────────────────────────────────────────────────────────────
# 7. Verify secret isolation (ADR-12) — warn-only
# ───────────────────────────────────────────────────────────────
log_info "Verifying secret isolation (agent must hold no LLM key)..."
if docker exec first-agent sh -c 'test -e /run/secrets/fa.env' 2>/dev/null; then
    log_warn "  agent has /run/secrets/fa.env mounted — it must NOT (keys belong to the proxy)."
else
    log_info "  OK: no LLM key file in the agent container."
fi
if docker exec first-agent sh -c 'printenv | grep -qiE "API_KEY|_TOKEN=|SECRET"' 2>/dev/null; then
    log_warn "  agent env contains a key-shaped variable — investigate."
else
    log_info "  OK: no key-shaped variable in the agent environment."
fi

# ───────────────────────────────────────────────────────────────
# 8. Summary
# ───────────────────────────────────────────────────────────────
log_info "====================================="
log_info "Clean rebuild complete."
log_info "  Containers: docker compose -f ${COMPOSE_FILE} ps"
log_info "  Proxy logs: docker compose -f ${COMPOSE_FILE} logs -f fa-egress-proxy"
[[ -n "${BK}" ]] && log_info "  Backup:     ${BK}"
log_info "====================================="
exit 0
