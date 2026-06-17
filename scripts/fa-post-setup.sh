#!/usr/bin/env bash
# fa-post-setup.sh — Run AFTER setup-fa-desktop.sh and manual steps
# (Tailscale auth, GitHub deploy key, .env.fa edited).
#
# Handles: docker build, git test, service start, backup cron.
# Idempotent: safe to re-run.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

REPO_DIR="/srv/first-agent/repo/First-Agent-dev"
ENV_FA="$REPO_DIR/.env.fa"
BACKUP_ENV="/srv/first-agent/secrets/backup.env"
SERVICE_FILE="$HOME/.config/systemd/user/fa.service"
TEST_BRANCH="agent/test-bootstrap"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if [[ "$EUID" -eq 0 ]]; then
    log_error "Do not run as root. Run as the same user that ran setup-fa-desktop.sh."
    exit 1
fi

if ! id -Gn | grep -qw 'docker'; then
    log_error "User $(whoami) is NOT in the 'docker' group."
    log_error "Fix: log out of GNOME completely and log back in (or reboot)."
    log_error "Then re-run this script."
    exit 1
fi

if [[ ! -f "$SERVICE_FILE" ]]; then
    log_error "systemd service file not found: $SERVICE_FILE"
    log_error "Run setup-fa-desktop.sh first."
    exit 1
fi

if [[ ! -f "$ENV_FA" ]]; then
    log_error ".env.fa not found: $ENV_FA"
    log_error "Run setup-fa-desktop.sh first."
    exit 1
fi

# Validate .env.fa is not still a raw template
if [[ ! -s "$ENV_FA" ]] || grep -qi 'CHANGEME' "$ENV_FA"; then
    log_warn ".env.fa looks unedited (still contains placeholder hints)."
    log_warn "Edit it first: nano $ENV_FA"
    read -rp "Continue anyway? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || exit 1
fi

cd "$REPO_DIR"

# 0. Tailscale connectivity check (warn only, do not block)
if command -v tailscale &>/dev/null; then
    if ! tailscale status 2>/dev/null | grep -q "Connected"; then
        log_warn "Tailscale does not appear to be connected."
        log_warn "If your Git SSH depends on Tailscale DNS, the git test below may fail."
        log_warn "Run: sudo tailscale up --ssh   (if not already done)"
    fi
fi

# Derive the repo SSH URL from origin remote (supports forks)
REPO_SSH_URL=$(git remote get-url origin 2>/dev/null | sed 's|https://github.com/|git@github.com:|' || echo "git@github.com:first-agent-dev/First-Agent-dev.git")

# ---------------------------------------------------------------------------
# 1. Build + start the stack (two services: fa-egress-proxy + first-agent)
# ---------------------------------------------------------------------------
log_info "Building FA images..."
docker compose -f docker-compose.fa.yml build

log_info "Starting FA stack (egress-proxy then agent via depends_on)..."
docker compose -f docker-compose.fa.yml up -d

# ---------------------------------------------------------------------------
# 2. Wait for BOTH containers to be healthy (ADR-12 two-container topology).
#    The agent has `depends_on: fa-egress-proxy (service_healthy)`, so if the
#    proxy never becomes healthy the agent will not start at all — detect that
#    explicitly instead of waiting on a container that never appears.
# ---------------------------------------------------------------------------
wait_for_container() {
    # $1 = container name, $2 = require "healthy" (1) or just "running" (0)
    local name="$1" need_health="$2" status health
    for _ in {1..60}; do
        status=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null || echo "missing")
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null || echo "none")
        if [[ "$need_health" -eq 1 ]]; then
            if [[ "$status" == "running" && ( "$health" == "healthy" || "$health" == "none" ) ]]; then
                log_info "Container '$name' is running (health=$health)."
                return 0
            fi
        elif [[ "$status" == "running" ]]; then
            log_info "Container '$name' is running."
            return 0
        fi
        sleep 1
    done
    return 1
}

log_info "Waiting for egress proxy 'fa-egress-proxy' to become healthy..."
if ! wait_for_container "fa-egress-proxy" 1; then
    log_error "Egress proxy did not become healthy within 60s."
    log_error "The agent will NOT start until the proxy is healthy (depends_on)."
    log_error "Common causes: missing/empty proxy token or models.yaml. Check:"
    log_error "  ls -l /srv/first-agent/secrets/fa_proxy_token /srv/first-agent/state/models.yaml"
    log_error "  docker compose -f docker-compose.fa.yml logs fa-egress-proxy"
    exit 1
fi

log_info "Waiting for agent 'first-agent' to start..."
if ! wait_for_container "first-agent" 0; then
    log_error "Agent container did not start within 60s. Check logs:"
    log_error "  docker compose -f docker-compose.fa.yml logs"
    exit 1
fi

# ---------------------------------------------------------------------------
# 3. Configure git inside container (local config, since /workspace is writable bind-mount)
# ---------------------------------------------------------------------------
log_info "Configuring git inside container..."
docker exec first-agent bash -c 'cd /workspace && git config user.name "First Agent"'
docker exec first-agent bash -c 'cd /workspace && git config user.email "agent@first-agent.local"'

# ---------------------------------------------------------------------------
# 4. Test git SSH connectivity
# ---------------------------------------------------------------------------
log_info "Testing git SSH connectivity..."

if docker exec first-agent bash -c "cd /workspace && git ls-remote ${REPO_SSH_URL}" >/dev/null 2>&1; then
    log_info "Git SSH connectivity: OK"
else
    log_error "Git SSH test FAILED. Check:"
    log_error "  - Deploy key added to GitHub with WRITE access"
    log_error "  - Container has internet access"
    log_error "  - Tailscale is up (if DNS depends on it)"
    exit 1
fi

# ---------------------------------------------------------------------------
# 5. Test git push (create + push + delete test branch)
# ---------------------------------------------------------------------------
log_info "Testing git push..."

# Idempotent cleanup: remove remote + local test branch from any previous aborted run
log_info "Preparing clean test state..."
docker exec first-agent bash -c "cd /workspace && git push origin --delete $TEST_BRANCH || true" 2>/dev/null || true
if docker exec first-agent bash -c "cd /workspace && git rev-parse --verify $TEST_BRANCH" >/dev/null 2>&1; then
    docker exec first-agent bash -c "cd /workspace && git checkout - || true; git branch -D $TEST_BRANCH || true"
fi

# Push test branch
docker exec first-agent bash -c "
    cd /workspace &&
    git checkout -b $TEST_BRANCH &&
    touch bootstrap-test.txt &&
    git add bootstrap-test.txt &&
    git commit -m 'test: bootstrap verification' &&
    git push origin $TEST_BRANCH
" || {
    log_error "Git push test FAILED."
    exit 1
}

log_info "Git push test passed. Cleaning up test branch..."
docker exec first-agent bash -c "
    cd /workspace &&
    git checkout - || true;
    git branch -D $TEST_BRANCH || true;
    git push origin --delete $TEST_BRANCH || true;
    rm -f bootstrap-test.txt
" || true

# ---------------------------------------------------------------------------
# 5b. Secret-isolation smoke check (ADR-12): the AGENT container must hold no
#     LLM provider key — no key file, no key env var. (Warn-only: a finding here
#     means the isolation regressed; it does not block the deploy.)
# ---------------------------------------------------------------------------
log_info "Verifying the agent container holds no LLM key (ADR-12)..."
if docker exec first-agent sh -c 'test -e /run/secrets/fa.env' 2>/dev/null; then
    log_warn "  agent has /run/secrets/fa.env mounted — it must NOT (keys belong in the proxy)."
else
    log_info "  OK: no LLM key file in the agent container."
fi
if docker exec first-agent sh -c 'printenv | grep -qiE "API_KEY|_TOKEN=|SECRET"' 2>/dev/null; then
    log_warn "  agent env contains an API_KEY/TOKEN/SECRET variable — investigate."
else
    log_info "  OK: no key-shaped variable in the agent environment."
fi

# ---------------------------------------------------------------------------
# 6. Configure boot autostart — WITHOUT tearing down the running stack.
# ---------------------------------------------------------------------------
# The stack is already UP and healthy (step 1) and the agent is in stand-by,
# ready for `docker compose exec` / the WebUI backend. Do NOT `down` it to hand
# off to systemd: `systemctl --user start` silently no-ops when there is no
# user D-Bus/linger session, which would leave NOTHING running. Keep compose as
# the authoritative runtime; use systemd only to (re)start on REBOOT.
log_info "Configuring boot autostart (systemd user service)..."
loginctl enable-linger "${USER}" 2>/dev/null || \
    sudo loginctl enable-linger "${USER}" 2>/dev/null || \
    log_warn "Could not enable linger; the service may not autostart until you log in."
if systemctl --user daemon-reload 2>/dev/null; then
    systemctl --user enable fa.service 2>/dev/null \
        && log_info "fa.service enabled (will start on reboot)." \
        || log_warn "Could not enable fa.service; enable it later: systemctl --user enable fa.service"
else
    log_warn "systemctl --user not available in this session (no D-Bus/linger)."
    log_warn "The stack is running via docker compose right now. To arm reboot autostart,"
    log_warn "log in as ${USER} over SSH and run:"
    log_warn "  loginctl enable-linger ${USER}"
    log_warn "  systemctl --user daemon-reload && systemctl --user enable fa.service"
fi

# Final guarantee: the stack must be UP and in stand-by when this script exits,
# regardless of the systemd outcome above (idempotent — no-op if already up).
docker compose -f docker-compose.fa.yml up -d >/dev/null 2>&1 || true
if docker ps --format '{{.Names}}' | grep -q '^first-agent$'; then
    log_info "Stack is UP; agent is in stand-by, ready for 'docker compose exec ... fa run'."
else
    log_warn "Stack is not running — check: docker compose -f docker-compose.fa.yml ps"
fi

# ---------------------------------------------------------------------------
# 7. Backup cron (idempotent)
# ---------------------------------------------------------------------------
if [[ -f "$BACKUP_ENV" ]] && ! grep -qiE '^\s*B2_KEY_ID\s*=\s*CHANGEME' "$BACKUP_ENV"; then
    log_info "Backup credentials found. Adding nightly cron job..."
    CRON_LINE='0 3 * * * /srv/first-agent/scripts/backup-fa.sh >> /srv/first-agent/backup/backup.log 2>&1'
    if ! (crontab -l 2>/dev/null || true) | grep -qF "$CRON_LINE"; then
        (crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
    fi
    log_info "Backup cron installed."
else
    log_warn "Backup not configured yet. Edit: $BACKUP_ENV"
    log_warn "Then run: crontab -e and add:"
    log_warn '  0 3 * * * /srv/first-agent/scripts/backup-fa.sh >> /srv/first-agent/backup/backup.log 2>&1'
fi

# ---------------------------------------------------------------------------
# 8. Summary
# ---------------------------------------------------------------------------
log_info "====================================="
log_info "Post-setup complete!"
log_info "====================================="
echo ""
echo "Containers:   docker compose -f docker-compose.fa.yml ps   (expect first-agent + fa-egress-proxy)"
echo "Logs:         docker compose -f docker-compose.fa.yml logs -f"
echo "Proxy logs:   docker compose -f docker-compose.fa.yml logs -f fa-egress-proxy"
echo "Run a task:   docker compose -f docker-compose.fa.yml exec first-agent fa run --role coder --workspace /workspace --task \"...\""
echo "Backup:       /srv/first-agent/scripts/backup-fa.sh"
echo ""
echo "Primary control (always works):"
echo "  Up/refresh: docker compose -f docker-compose.fa.yml up -d"
echo "  Stop:       docker compose -f docker-compose.fa.yml down"
echo "Reboot autostart (systemd, once configured): systemctl --user {status,restart} fa.service"
