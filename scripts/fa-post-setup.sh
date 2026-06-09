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

# ---------------------------------------------------------------------------
# 1. Build + start container
# ---------------------------------------------------------------------------
log_info "Building FA container..."
docker compose -f docker-compose.fa.yml build

log_info "Starting FA container..."
docker compose -f docker-compose.fa.yml up -d

# ---------------------------------------------------------------------------
# 2. Wait for container to be running and healthy
# ---------------------------------------------------------------------------
log_info "Waiting for container to become healthy..."
for i in {1..30}; do
    status=$(docker inspect --format='{{.State.Status}}' first-agent 2>/dev/null || echo "missing")
    if [[ "$status" == "running" ]]; then
        log_info "Container 'first-agent' is running."
        break
    fi
    sleep 1
    if [[ "$i" -eq 30 ]]; then
        log_error "Container did not start within 30s. Check logs:"
        log_error "  docker compose -f docker-compose.fa.yml logs"
        exit 1
    fi
done

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

if docker exec first-agent bash -c 'cd /workspace && git ls-remote git@github.com:anton-sh/First-Agent-dev.git' >/dev/null 2>&1; then
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
# 6. Enable and start systemd service
# ---------------------------------------------------------------------------
log_info "Enabling FA systemd service..."
systemctl --user daemon-reload
systemctl --user enable fa.service

# Stop any existing container first so the service starts fresh
if docker ps --format '{{.Names}}' | grep -q '^first-agent$'; then
    log_warn "Stopping existing container before service hand-off..."
    docker compose -f docker-compose.fa.yml down || true
fi

systemctl --user start fa.service

sleep 2
if systemctl --user is-active fa.service >/dev/null 2>&1; then
    log_info "FA service is ACTIVE."
else
    log_warn "FA service status uncertain. Check with: systemctl --user status fa.service"
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
echo "Container:    docker ps"
echo "Logs:         docker compose -f docker-compose.fa.yml logs -f"
echo "Service:      systemctl --user status fa.service"
echo "Backup:       /srv/first-agent/scripts/backup-fa.sh"
echo ""
echo "To stop FA:   systemctl --user stop fa.service"
echo "To start:     systemctl --user start fa.service"
echo "To restart:   systemctl --user restart fa.service"
