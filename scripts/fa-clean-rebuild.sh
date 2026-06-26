#!/usr/bin/env bash
# fa-clean-rebuild.sh — tear down the FA stack and rebuild it clean (ADR-12).
#
# Intended use on the deployment host:
#   /srv/first-agent/repo/First-Agent-dev/scripts/fa-clean-rebuild.sh
#
# What it does (in order):
#   1. Preflight (docker/compose present, repo + compose file exist).
#   2. Update the local repo to origin/<branch> (--ff-only); re-exec the updated
#      copy of THIS script so the rest runs the new code/compose. SKIP_UPDATE=1
#      to skip. (A truly clean install should run the latest main.)
#   3. Back up /srv/first-agent/{state,routing,secrets} to a timestamped 0700 dir.
#   4. Stop the systemd service + `docker compose down --remove-orphans`.
#   5. Reset run history (/srv/first-agent/state/runs/*); with WIPE_STATE=1,
#      clear state and reset routing/models.yaml for backward compatibility.
#   6. KEEP secrets/ untouched (LLM keys, deploy key, fa_proxy_token); generate
#      the fa->proxy token if it is missing. NEVER deletes secrets.
#   7. Rebuild images --no-cache and bring the TWO containers up
#      (fa-egress-proxy + first-agent), waiting for both to be healthy.
#   8. Verify secret isolation (agent holds no LLM key) and re-enable the service.
#
# Bootstrap note: this script lives INSIDE the repo it updates. On a server with
# an OLD checkout (no fa-clean-rebuild.sh yet), first run once manually:
#   cd /srv/first-agent/repo/First-Agent-dev && git pull --ff-only origin main
# then run scripts/fa-clean-rebuild.sh.
#
# Deliberately does NOT call setup-fa-desktop.sh: that script re-provisions the
# whole HOST (apt full-upgrade, Docker reinstall, UFW/SSH, etc.), which is unsafe
# to trigger from a container-rebuild. Only the container-scoped bits are inlined.
#
# Safe by design: persistent data lives in host bind-mounts, so removing
# containers/images never loses keys or config.
#
# Flags (env vars):
#   WIPE_STATE=1     clear ALL of state/ and reset routing/models.yaml (old
#                    versions stored models.yaml under state/). A routing
#                    template is recreated for you to re-fill. Keys preserved.
#   PRUNE=1          `docker system prune -af` after teardown (frees disk; removes
#                    ALL unused images/build cache on the host). Default: off.
#   NO_CACHE=0       use Docker cache for the image build (default: 1 = --no-cache).
#   COMPOSE_BUILD_PULL=0  do not pass --pull to docker compose build (default: 1).
#   BUILD_PROGRESS=plain  pass --progress plain for debuggable BuildKit logs.
#   NO_BACKUP=1      skip the backup step (NOT recommended).
#   ASSUME_YES=1     do not prompt for confirmation on destructive flags.
#   SKIP_UPDATE=1    do not git-pull the repo (use the checkout as-is).
#   AUTO_STASH=1     stash a dirty working tree before pulling (else: abort).
#   GIT_BRANCH=main  branch to fast-forward to (default main).
#   HEALTH_TIMEOUT_SECONDS  per-container health wait (default 90).
#   ALLOW_NONSTANDARD_FA_DIR=1  allow destructive ops outside /srv/first-agent
#                    (only for disposable test installs).

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
SKIP_UPDATE="${SKIP_UPDATE:-0}"
AUTO_STASH="${AUTO_STASH:-0}"
GIT_BRANCH="${GIT_BRANCH:-main}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-90}"
NO_CACHE="${NO_CACHE:-1}"
COMPOSE_BUILD_PULL="${COMPOSE_BUILD_PULL:-1}"
BUILD_PROGRESS="${BUILD_PROGRESS:-auto}"
STASHED=0
# Internal: set to 1 after we re-exec the post-pull version of this script,
# so the updated copy does not try to update the repo again (loop guard).
_FA_REBUILD_REEXEC="${_FA_REBUILD_REEXEC:-0}"
EXAMPLE_MODELS="${REPO_DIR}/knowledge/examples/models.yaml.example"
ENV_FA="${REPO_DIR}/.env.fa"
SECRETS_ENV="${FA_DIR}/secrets/fa.env"
ROUTING_DIR="${FA_DIR}/routing"
ROUTING_MODELS_FILE="${ROUTING_DIR}/models.yaml"
# SUNSET (remove after 2026-12-01, once all hosts run the unified routing file):
# one-time migration inputs from the pre-unification layouts. They are only read
# when routing/models.yaml does not yet exist; after migration they are ignored.
LEGACY_STATE_MODELS="${FA_DIR}/state/models.yaml"
LEGACY_PROXY_MODELS="${FA_DIR}/proxy/models.yaml"

log_info()  { echo -e "\033[0;32m[INFO]\033[0m  $*"; }
log_warn()  { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $*" >&2; }

# shellcheck disable=SC2154  # rc IS assigned (rc=$?) inside this same trap string.
trap_err() {
    local rc=$?
    local lineno=$1
    local cmd=$2
    log_error "Failed at line ${lineno} (rc=${rc}): ${cmd}."
    if [[ "${STASHED:-0}" == "1" ]]; then
        log_warn "Recovering auto-stashed changes before exit..."
        git -C "${REPO_DIR}" stash pop || log_error "Failed to restore stash."
    fi
    log_error "The stack may be partially rebuilt; re-run after fixing."
    exit "${rc}"
}
trap 'trap_err ${LINENO} "${BASH_COMMAND}"' ERR

retry() {
    local n=1
    local max=3
    local delay=5
    while true; do
        if "$@"; then
            return 0
        fi
        if (( n >= max )); then
            return 1
        fi
        log_warn "Command failed: $* (attempt $n of $max). Retrying in ${delay}s..."
        sleep "$delay"
        ((n++))
    done
}

assert_safe_fa_dir() {
    # This script performs recursive deletes/chowns. In production the managed
    # root is fixed; allow overrides only for explicit disposable test installs.
    if [[ "${ALLOW_NONSTANDARD_FA_DIR:-0}" == "1" ]]; then
        return
    fi
    local normalized_fa_dir="${FA_DIR%/}"
    if [[ "${normalized_fa_dir}" != "/srv/first-agent" ]]; then
        log_error "Refusing destructive operation with FA_DIR=${FA_DIR}"
        log_error "Set ALLOW_NONSTANDARD_FA_DIR=1 only for a disposable test install."
        exit 1
    fi
}

ensure_routing_models() {
    sudo mkdir -p "${ROUTING_DIR}"
    sudo chown 1000:1000 "${ROUTING_DIR}"
    sudo chmod 750 "${ROUTING_DIR}"

    if [[ ! -f "${ROUTING_MODELS_FILE}" ]]; then
        if [[ -f "${LEGACY_STATE_MODELS}" ]]; then
            sudo cp "${LEGACY_STATE_MODELS}" "${ROUTING_MODELS_FILE}"
            log_info "Migrated legacy routing config: ${LEGACY_STATE_MODELS} → ${ROUTING_MODELS_FILE}"
        elif [[ -f "${LEGACY_PROXY_MODELS}" ]]; then
            sudo cp "${LEGACY_PROXY_MODELS}" "${ROUTING_MODELS_FILE}"
            log_info "Migrated legacy routing config: ${LEGACY_PROXY_MODELS} → ${ROUTING_MODELS_FILE}"
        elif [[ -f "${EXAMPLE_MODELS}" ]]; then
            sudo cp "${EXAMPLE_MODELS}" "${ROUTING_MODELS_FILE}"
            log_warn "Template models.yaml created at ${ROUTING_MODELS_FILE} (EDIT IT to set providers)."
        else
            sudo tee "${ROUTING_MODELS_FILE}" >/dev/null <<'EOF'
coder:
  model: "deepseek-v3"
  family: "deepseek"
  chain:
    - provider: openrouter
      slug: "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
EOF
            log_warn "Fallback models.yaml created at ${ROUTING_MODELS_FILE} (EDIT IT to set providers)."
        fi
    fi

    sudo chown 1000:1000 "${ROUTING_MODELS_FILE}"
    sudo chmod 640 "${ROUTING_MODELS_FILE}"
}

normalize_env_files() {
    local normalizer="${REPO_DIR}/scripts/fa-normalize-env.sh"
    if [[ -f "${normalizer}" ]]; then
        env \
            REPO_DIR="${REPO_DIR}" \
            ENV_FA="${ENV_FA}" \
            SECRETS_ENV="${SECRETS_ENV}" \
            BACKUP_DIR="${FA_DIR}/secrets" \
            bash "${normalizer}"
    fi
}

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

# ───────────────────────────────────────────────────────────────
# 2. Update the local repo to origin/<branch>, then re-exec the new copy.
#    A clean install should run the latest code/compose, not whatever stale
#    checkout happens to be on disk. Runs BEFORE any destructive step so an
#    old script updates itself first. Skipped on the re-exec pass (loop guard)
#    and when SKIP_UPDATE=1.
# ───────────────────────────────────────────────────────────────
if [[ "${SKIP_UPDATE}" != "1" && "${_FA_REBUILD_REEXEC}" != "1" ]]; then
    if ! command -v git >/dev/null 2>&1; then
        log_error "git not found but repo update requested. Install git or set SKIP_UPDATE=1."
        exit 1
    fi
    if [[ ! -d "${REPO_DIR}/.git" ]]; then
        log_warn "${REPO_DIR} is not a git checkout — skipping repo update."
    else
        if [[ -n "$(git status --porcelain)" ]]; then
            log_warn "Dirty working tree detected:"
            git status --short || true
            if [[ "${AUTO_STASH}" == "1" ]]; then
                log_info "Auto-stashing (AUTO_STASH=1)..."
                if git stash push -u -m "fa-clean-rebuild $(date -u '+%Y%m%dT%H%M%SZ')"; then
                    STASHED=1
                else
                    log_error "git stash failed — resolve local changes manually and re-run."
                    exit 1
                fi
            else
                log_error "Refusing to update over local changes. Commit/stash them, or set AUTO_STASH=1."
                exit 1
            fi
        fi
        log_info "Updating repo to origin/${GIT_BRANCH} (--ff-only)..."
        retry git fetch origin --prune
        current_branch=$(git rev-parse --abbrev-ref HEAD)
        if [[ "${current_branch}" != "${GIT_BRANCH}" ]]; then
            log_info "Switching ${current_branch} → ${GIT_BRANCH}..."
            git switch "${GIT_BRANCH}" 2>/dev/null || git checkout "${GIT_BRANCH}"
        fi
        before=$(git rev-parse HEAD)
        retry git pull --ff-only origin "${GIT_BRANCH}"
        after=$(git rev-parse HEAD)
        if [[ "${STASHED}" == "1" ]]; then
            log_info "Restoring stashed changes before continuing..."
            if git stash pop; then
                STASHED=0
            else
                log_error "Stash pop failed — resolve conflicts, then re-run before rebuilding."
                exit 1
            fi
        fi
        if [[ "${before}" != "${after}" ]]; then
            log_info "Repo updated: ${before:0:8} → ${after:0:8} ($(git rev-list --count "${before}..${after}") commit(s))."
            # The pull may have rewritten THIS file; re-exec the updated copy so
            # the rest of the run uses the new logic/compose. Editing a running
            # bash script in place is unsafe, hence the re-exec.
            log_info "Re-executing updated script..."
            # Carry the operator's flags across the exec explicitly (robust even
            # if a flag was set but not exported into the environment).
            export _FA_REBUILD_REEXEC=1
            export WIPE_STATE NO_BACKUP PRUNE ASSUME_YES SKIP_UPDATE AUTO_STASH \
                   GIT_BRANCH HEALTH_TIMEOUT_SECONDS NO_CACHE COMPOSE_BUILD_PULL BUILD_PROGRESS \
                   FA_DIR REPO_DIR COMPOSE_FILE SERVICE FA_USER ROUTING_DIR \
                   ROUTING_MODELS_FILE LEGACY_STATE_MODELS LEGACY_PROXY_MODELS
            exec bash "${REPO_DIR}/scripts/fa-clean-rebuild.sh" "$@"
        fi
        log_info "Repo already up to date (${after:0:8})."
    fi
fi

assert_safe_fa_dir
normalize_env_files

# Confirmation for destructive flags (skip with ASSUME_YES=1 or non-interactive).
if [[ "${WIPE_STATE}" == "1" || "${PRUNE}" == "1" ]] && [[ "${ASSUME_YES}" != "1" ]]; then
    [[ "${WIPE_STATE}" == "1" ]] && log_warn "WIPE_STATE=1 will DELETE ${FA_DIR}/state/*, ${FA_DIR}/sessions/* and reset ${ROUTING_MODELS_FILE} (keys are kept)."
    [[ "${PRUNE}" == "1" ]] && log_warn "PRUNE=1 will remove ALL unused Docker images + build cache on this host, not only First-Agent."
    if [[ -t 0 ]]; then
        read -r -p "Proceed? [y/N] " reply
        [[ "${reply}" =~ ^[Yy]$ ]] || { log_info "Aborted by user."; exit 0; }
    else
        log_error "Destructive flags set but no TTY to confirm. Re-run with ASSUME_YES=1."
        exit 1
    fi
fi

# ───────────────────────────────────────────────────────────────
# 3. Backup (0700 — it contains secrets)
# ───────────────────────────────────────────────────────────────
BK=""
if [[ "${NO_BACKUP}" != "1" ]]; then
    BK="${HOME}/fa-backup-$(date +%Y%m%d-%H%M%S)"
    ( umask 077; mkdir -p "${BK}" )
    log_info "Backing up state + routing + secrets to ${BK} (0700) ..."
    sudo cp -a "${FA_DIR}/state" "${BK}/state" 2>/dev/null || true
    sudo cp -a "${FA_DIR}/routing" "${BK}/routing" 2>/dev/null || true
    sudo cp -a "${FA_DIR}/secrets" "${BK}/secrets" 2>/dev/null || true
    sudo chown -R "${USER}:${USER}" "${BK}" 2>/dev/null || true
    chmod -R go-rwx "${BK}" 2>/dev/null || true
    log_info "Backup done: ${BK}"
else
    log_warn "NO_BACKUP=1 — skipping backup."
fi

# ───────────────────────────────────────────────────────────────
# 4. Stop service + tear down containers
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
# 5. Reset state (keys are NEVER touched here)
# ───────────────────────────────────────────────────────────────
# Always clear run history (safe; pure runtime artifacts).
if [[ -d "${FA_DIR}/state/runs" ]]; then
    log_info "Clearing run history (${FA_DIR}/state/runs/*)..."
    sudo rm -rf "${FA_DIR}/state/runs/"* 2>/dev/null || true
fi

if [[ "${WIPE_STATE}" == "1" ]]; then
    log_warn "WIPE_STATE=1 — clearing ALL of ${FA_DIR}/state/*, ${FA_DIR}/sessions/* and resetting ${ROUTING_MODELS_FILE} (keys preserved)."
    sudo rm -rf "${FA_DIR}/state/"* 2>/dev/null || true
    sudo rm -rf "${FA_DIR}/sessions/"* 2>/dev/null || true
    sudo rm -f "${ROUTING_MODELS_FILE}" 2>/dev/null || true
    # WIPE_STATE historically reset models.yaml. Do not resurrect a stale
    # legacy proxy/state copy during this explicit reset; recreate from the
    # checked-in example (or fallback) instead.
    LEGACY_STATE_MODELS=""
    LEGACY_PROXY_MODELS=""
fi

# Ensure state exists/ownership is correct; routing is a separate read-only file
# mount into both containers and is prepared by ensure_routing_models.
sudo mkdir -p "${FA_DIR}/state"
sudo chown -R 1000:1000 "${FA_DIR}/state" 2>/dev/null || true
# Session workspace mount source (workspace isolation, ADR-13).
sudo mkdir -p "${FA_DIR}/sessions"
sudo chown 1000:1000 "${FA_DIR}/sessions"
ensure_routing_models

# ───────────────────────────────────────────────────────────────
# 6. Secrets: keep keys; ensure the fa->proxy token exists
# ───────────────────────────────────────────────────────────────
if [[ ! -s "${SECRETS_ENV}" ]]; then
    log_warn "No ${SECRETS_ENV} (LLM keys) — the agent cannot call providers until you set it:"
    log_warn "  sudo micro ${SECRETS_ENV}"
fi

TOKEN_FILE="${FA_DIR}/secrets/fa_proxy_token"
if [[ ! -s "${TOKEN_FILE}" ]]; then
    log_info "Generating fa->proxy token at ${TOKEN_FILE}..."
    sudo mkdir -p "${FA_DIR}/secrets"
    head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n' | sudo tee "${TOKEN_FILE}" >/dev/null
    sudo chmod 600 "${TOKEN_FILE}"
fi
# Ensure ALL of secrets/ is owned by the container uid (the proxy reads fa.env +
# token; the agent reads the deploy key). A stale root-owned file here is the
# classic "proxy unhealthy / git push fails" cause after a manual wipe.
sudo chown -R 1000:1000 "${FA_DIR}/secrets" 2>/dev/null || true
# Hard requirement: the proxy rejects the agent without this token.
if [[ ! -s "${TOKEN_FILE}" ]]; then
    log_error "Could not create ${TOKEN_FILE}. The proxy would reject the agent. Aborting."
    exit 1
fi

# Preflight: every FILE bind-mount source must already exist as a regular file.
# If a source is missing at `docker compose up`, Docker silently creates a
# ROOT-OWNED DIRECTORY there, and the container then reads a directory-as-file →
# a confusing crash that also leaves a root-owned path the scripts can't fix.
# Fail loudly here instead. (Deploy-key/known_hosts come from setup-fa-desktop.)
_required_files=(
    "${SECRETS_ENV}"
    "${FA_DIR}/secrets/fa_proxy_token"
    "${FA_DIR}/secrets/github_deploy_key"
    "${FA_DIR}/secrets/known_hosts"
    "${ROUTING_MODELS_FILE}"
)
_missing=0
for _rf in "${_required_files[@]}"; do
    if [[ -d "${_rf}" ]]; then
        log_error "Mount source is a DIRECTORY (should be a file): ${_rf}"
        log_error "  Likely created by a bare 'docker compose up' before setup. Remove it:"
        log_error "    sudo rm -rf '${_rf}'  then re-run setup-fa-desktop.sh"
        _missing=1
    elif [[ ! -e "${_rf}" ]]; then
        log_error "Required mount source missing: ${_rf} (run setup-fa-desktop.sh first)"
        _missing=1
    fi
done
[[ "${_missing}" -eq 0 ]] || { log_error "Aborting before build — fix the above."; exit 1; }

# ───────────────────────────────────────────────────────────────
# 7. Rebuild clean + bring up the two containers
# ───────────────────────────────────────────────────────────────
log_info "Building images (NO_CACHE=${NO_CACHE}, COMPOSE_BUILD_PULL=${COMPOSE_BUILD_PULL}, BUILD_PROGRESS=${BUILD_PROGRESS})..."
_build_sha=$(git -C "${REPO_DIR}" rev-parse HEAD 2>/dev/null || echo "unknown")
build_cmd=(docker compose -f "${COMPOSE_FILE}" build
           --build-arg "FA_BUILD_SHA=${_build_sha}")
[[ "${COMPOSE_BUILD_PULL}" == "1" ]] && build_cmd+=(--pull)
[[ "${NO_CACHE}" == "1" ]] && build_cmd+=(--no-cache)
[[ "${BUILD_PROGRESS}" != "auto" ]] && build_cmd+=(--progress "${BUILD_PROGRESS}")
retry "${build_cmd[@]}"

log_info "Starting stack (docker compose up -d — authoritative)..."
# Compose is the authoritative bring-up: idempotent and independent of the user
# D-Bus/linger session. `systemctl --user start` is NOT used here because it
# silently no-ops without a loaded user service, which would leave the stack
# down. systemd is only armed for REBOOT autostart below.
docker compose -f "${COMPOSE_FILE}" up -d
# Arm boot autostart (best-effort; never blocks the rebuild).
systemctl --user daemon-reload 2>/dev/null \
    && systemctl --user enable "${SERVICE}" 2>/dev/null \
    && log_info "fa.service enabled for reboot autostart." \
    || log_warn "Could not arm systemd autostart (no user session?); stack is up via compose."

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
    log_error "  Check: ls -l ${TOKEN_FILE} ${ROUTING_MODELS_FILE}"
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
# 8. Verify secret isolation (ADR-12) — warn-only
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
# 9. Install host-side `fa` CLI wrapper
# ───────────────────────────────────────────────────────────────
FA_WRAPPER="${REPO_DIR}/scripts/fa"
if [[ -x "${FA_WRAPPER}" ]]; then
    sudo ln -sf "${FA_WRAPPER}" /usr/local/bin/fa 2>/dev/null \
        && log_info "Host CLI wrapper installed: fa → ${FA_WRAPPER}" \
        || log_warn "Could not symlink ${FA_WRAPPER} → /usr/local/bin/fa (sudo required)."
fi

# ───────────────────────────────────────────────────────────────
# 10. Summary
# ───────────────────────────────────────────────────────────────
log_info "====================================="
log_info "Clean rebuild complete."
log_info "  Containers: docker compose -f ${COMPOSE_FILE} ps"
log_info "  Proxy logs: docker compose -f ${COMPOSE_FILE} logs -f fa-egress-proxy"
[[ -n "${BK}" ]] && log_info "  Backup:     ${BK}"
log_info "====================================="
exit 0
