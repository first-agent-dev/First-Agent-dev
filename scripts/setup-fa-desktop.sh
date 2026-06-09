#!/usr/bin/env bash
# Setup script for dedicated Ubuntu Desktop 24.04 AIO running First-Agent 24/7
# Run this on a fresh Ubuntu Desktop 24.04 LTS minimal install
# WARNING: This script modifies system settings. Review before running.

set -euo pipefail

# Configuration
FA_USER="${FA_USER:-$USER}"
FA_DIR="${FA_DIR:-$HOME/fa}"
REPO_URL="${REPO_URL:-https://github.com/first-agent-dev/First-Agent-dev.git}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 1. System update and essential packages
log_info "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    curl wget git build-essential \
    universal-ctags \
    unattended-upgrades \
    fail2ban \
    ufw \
    powertop \
    restic \
    x11-xserver-utils \
    neovim

# 2. Desktop pruning — conservative (mask, do not purge packages that break metapackage)
log_info "Pruning unnecessary Desktop services..."

# Safe to remove: gnome-software has known memory leaks (~2-3GB)
sudo apt-get remove -y gnome-software || true
sudo apt-get autoremove -y || true

# Safe to disable (not purge): crash reporting
sudo systemctl disable whoopsie.service || true
sudo systemctl disable apport.service || true
sudo systemctl stop whoopsie.service || true
sudo systemctl stop apport.service || true

# Mask (do NOT purge) — removing packages breaks ubuntu-desktop metapackage
# See: AskUbuntu "I deleted tracker-miner-fs from Lubuntu"
sudo -u "$FA_USER" systemctl --user mask tracker-miner-fs-3.service || true
sudo -u "$FA_USER" systemctl --user mask tracker-extract-3.service || true

# Disable Bluetooth (attack surface + power drain)
sudo systemctl stop bluetooth || true
sudo systemctl disable bluetooth || true

# Keep power-profiles-daemon (cross-reference: TLP is for laptops, causes USB issues on desktop AIO)
sudo systemctl enable power-profiles-daemon || true

# 3. Suspend prevention — dual lock (gsettings + logind.conf)
# Cross-reference: Chris Siebenmann (UToronto) — both display manager AND greeter can independently trigger suspend
log_info "Disabling suspend via dual lock..."

sudo tee /etc/systemd/logind.conf.d/no-suspend.conf > /dev/null <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF

# Prevent GNOME from suspending
sudo -u "$FA_USER" gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 0
sudo -u "$FA_USER" gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-timeout 0

# Screen blank after 60s, NO lock (cross-reference: aggressive blank saves ~5-15W)
sudo -u "$FA_USER" gsettings set org.gnome.desktop.session idle-delay 60
sudo -u "$FA_USER" gsettings set org.gnome.desktop.screensaver lock-enabled false

# Disable telemetry
sudo -u "$FA_USER" gsettings set org.gnome.desktop.privacy report-technical-problems false

# Set power profile to power-saver (cross-reference: start here, skip TLP on desktop AIO)
sudo -u "$FA_USER" powerprofilesctl set power-saver || true

# Aggressive DPMS screen blank — gsettings idle-delay blanks the session,
# but the AIO panel backlight stays on unless DPMS is triggered explicitly
# Cross-reference: ~5-15W savings from aggressive blanking
sudo -u "$FA_USER" xset dpms 0 0 60 || true

# Optional: boot to multi-user.target (text mode) by default
# Cross-reference: saves ~300-500MB RAM by not starting GNOME on every boot
# Emergency GUI access: sudo systemctl isolate graphical.target
log_warn "Optional: Run 'sudo systemctl set-default multi-user.target' to boot headless."
log_warn "For emergency GUI: 'sudo systemctl isolate graphical.target'"

# 4. SSH hardening — reachable ONLY over Tailscale interface
log_info "Hardening SSH..."
sudo tee /etc/ssh/sshd_config.d/99-fa-hardening.conf > /dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers FA_USER_PLACEHOLDER
EOF
sudo sed -i "s/FA_USER_PLACEHOLDER/$FA_USER/g" /etc/ssh/sshd_config.d/99-fa-hardening.conf

# Restart sshd only if not currently connected via SSH (avoid locking yourself out)
if [ -z "${SSH_CONNECTION:-}" ]; then
    sudo systemctl restart sshd
else
    log_warn "Skipping sshd restart — you are connected via SSH. Run 'sudo systemctl restart sshd' manually when safe."
fi

# 5. Firewall — default deny, allow Tailscale interface to SSH
# WARNING: Docker bypasses UFW for published ports. Do not publish ports publicly.
# See: https://docs.docker.com/engine/network/packet-filtering-firewalls/
log_info "Configuring UFW..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
# Only allow SSH via Tailscale interface (tailscale0 created after 'tailscale up')
sudo ufw allow in on tailscale0 to any port 22 proto tcp comment "SSH via Tailscale only"
sudo ufw allow 41641/udp comment "Tailscale wireguard"
sudo ufw --force enable

# 6. Install Docker CE from official docker.com apt repo (NOT Ubuntu snap)
# Hold packages to prevent surprise breaking changes on apt upgrade
log_info "Installing Docker CE from official repository..."
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$FA_USER"

# Pin Docker packages — review release notes before unholding
log_info "Pinning Docker CE packages..."
sudo apt-mark hold docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable live-restore: containers survive Docker daemon restarts (upgrades)
log_info "Configuring Docker live-restore..."
sudo mkdir -p /etc/docker
if ! grep -q '"live-restore"' /etc/docker/daemon.json 2>/dev/null; then
    echo '{"live-restore": true, "log-opts": {"max-size": "10m", "max-file": "3"}}' | sudo tee /etc/docker/daemon.json > /dev/null
    log_warn "Docker live-restore + log rotation enabled. Restart Docker with: sudo systemctl restart docker"
fi

# 7. Install Tailscale
log_info "Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sudo sh
log_warn "Tailscale installed. Run: sudo tailscale up --ssh"
log_warn "Then authenticate with your Tailscale account."

# 8. Create FA workspace at /srv/first-agent/ (cross-reference: bind-mount friendly)
FA_DIR="/srv/first-agent"
log_info "Creating FA workspace at $FA_DIR..."
sudo mkdir -p "$FA_DIR"/{repo,state,secrets,backup,scripts}
sudo chown -R "$FA_USER:$FA_USER" "$FA_DIR"
sudo chmod 700 "$FA_DIR/state"
sudo chmod 700 "$FA_DIR/secrets"

# 9. Clone repo (if not already present)
if [ ! -d "$FA_DIR/repo/First-Agent-dev" ]; then
    log_info "Cloning First-Agent repository..."
    git clone "$REPO_URL" "$FA_DIR/repo/First-Agent-dev"
fi

# 10. Generate SSH deploy key + pin GitHub Ed25519 host key
DEPLOY_KEY="$FA_DIR/secrets/github_deploy_key"
if [ ! -f "$DEPLOY_KEY" ]; then
    log_info "Generating ED25519 deploy key..."
    ssh-keygen -t ed25519 -f "$DEPLOY_KEY" -N "" -C "first-agent-deploy@$(hostname)"
    chmod 600 "$DEPLOY_KEY"
    chmod 644 "$DEPLOY_KEY.pub"
    log_warn "Add the following PUBLIC key to GitHub repo Settings -> Deploy keys (WRITE access):"
    cat "$DEPLOY_KEY.pub"
    log_warn "Then enable branch protection on 'main' — agent should push to 'agent/*' branches only."
fi

# Pin GitHub's Ed25519 host key (mitigates host-key rotation outages)
GH_ED25519_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okMS0XmZcBPwZR"
mkdir -p "$FA_DIR/secrets"
if ! grep -q "$GH_ED25519_KEY" "$FA_DIR/secrets/known_hosts" 2>/dev/null; then
    echo "github.com $GH_ED25519_KEY" >> "$FA_DIR/secrets/known_hosts"
    log_info "Pinned GitHub Ed25519 host key in $FA_DIR/secrets/known_hosts"
fi

# 10b. Create .env.fa from template
ENV_FA="$FA_DIR/repo/First-Agent-dev/.env.fa"
if [ ! -f "$ENV_FA" ]; then
    cp "$FA_DIR/repo/First-Agent-dev/.env.fa.template" "$ENV_FA"
    chmod 600 "$ENV_FA"
    log_warn "Template .env.fa created at $ENV_FA. EDIT IT to add your LLM API keys before first run."
fi

# 10c. Create models.yaml from example
MODELS_YAML="$FA_DIR/state/models.yaml"
if [ ! -f "$MODELS_YAML" ]; then
    cp "$FA_DIR/repo/First-Agent-dev/knowledge/examples/models.yaml.example" "$MODELS_YAML"
    log_warn "Template models.yaml created at $MODELS_YAML. EDIT IT to configure provider chains."
fi

# 11. Enable automatic security updates + auto-reboot (non-interactive)
log_info "Enabling unattended security updates..."
sudo tee /etc/apt/apt.conf.d/20auto-upgrades > /dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

# Auto-reboot at 04:00 after kernel/security updates (24/7 box must stay patched)
log_info "Configuring automatic reboot after updates..."
sudo tee /etc/apt/apt.conf.d/50unattended-upgrades-fa > /dev/null <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF

# 12. Weekly Docker image prune (prevents daemon RAM bloat; scoped to unused images only)
log_info "Adding weekly Docker image cleanup cron job..."
(sudo crontab -l 2>/dev/null || true; echo "0 3 * * 0 /usr/bin/docker image prune -f > /dev/null 2>&1") | sudo crontab -

# 13. Install systemd user service template
log_info "Installing systemd user service template..."
# Resolve target user's home directory (handles sudo + FA_USER correctly)
FA_USER_HOME=$(getent passwd "$FA_USER" | cut -d: -f6)
mkdir -p "$FA_USER_HOME/.config/systemd/user"
cat > "$FA_USER_HOME/.config/systemd/user/fa.service" <<EOF
[Unit]
Description=First-Agent 24/7 container
After=docker.service network-online.target tailscaled.service
Requires=docker.service
Wants=network-online.target tailscaled.service

[Service]
Type=oneshot
RemainAfterExit=yes
OOMScoreAdjust=-500
Restart=on-failure
RestartSec=10
WorkingDirectory=$FA_DIR/repo/First-Agent-dev
ExecStart=/usr/bin/docker compose -f docker-compose.fa.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.fa.yml down
TimeoutStartSec=0

[Install]
WantedBy=default.target
EOF
sudo -u "$FA_USER" systemctl --user daemon-reload

# Enable systemd lingering so user services survive logout and start after reboot
loginctl enable-linger "$FA_USER" 2>/dev/null || true

log_info "Enable with: systemctl --user enable fa.service"

# 14. Create backup script template
log_info "Creating backup script template..."
cat > "$FA_DIR/scripts/backup-fa.sh" <<'BACKUP_EOF'
#!/usr/bin/env bash
# Backup First-Agent state to Backblaze B2 (S3-compatible endpoint)
# Cross-reference: restic community recommends S3-compatible B2 endpoint over native B2 backend.
#
# Pre-requisites:
#   1. Create a Backblaze B2 bucket
#   2. Generate an Application Key with read/write access to that bucket
#   3. Fill in B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET below
#   4. Run once manually: restic -r "$RESTIC_REPO" init
#   5. Add to cron or systemd timer for nightly execution
#
# Schedule example (cron):
#   0 3 * * * /srv/first-agent/scripts/backup-fa.sh >> /srv/first-agent/backup/backup.log 2>&1
#
# Test restore quarterly:
#   restic -r "$RESTIC_REPO" restore latest --target /tmp/restore-test

set -euo pipefail

B2_KEY_ID="${B2_KEY_ID:-CHANGEME}"
B2_APPLICATION_KEY="${B2_APPLICATION_KEY:-CHANGEME}"
B2_BUCKET="${B2_BUCKET:-CHANGEME}"
# Use S3-compatible B2 endpoint (NOT native b2: backend)
RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/${B2_BUCKET}"
BACKUP_TAG="fa-$(hostname)"

export AWS_ACCESS_KEY_ID="$B2_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$B2_APPLICATION_KEY"

# If FA uses SQLite, uncomment to stop the agent process before snapshot for consistency
# docker exec first-agent pkill -f "fa run" || true
# sleep 2

restic -r "$RESTIC_REPO" backup \
    /srv/first-agent/state \
    /srv/first-agent/secrets \
    /srv/first-agent/scripts \
    /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml \
    /srv/first-agent/repo/First-Agent-dev/.env.fa \
    /etc/ssh/sshd_config.d/99-fa-hardening.conf \
    /etc/systemd/logind.conf.d/no-suspend.conf \
    /etc/apt/apt.conf.d/50unattended-upgrades-fa \
    /etc/docker/daemon.json \
    "$HOME/.config/systemd/user/fa.service" \
    --tag "$BACKUP_TAG" \
    --exclude-if-present .nobackup \
    --exclude "**/__pycache__" \
    --exclude "**/.mypy_cache" \
    --exclude "**/.pytest_cache" \
    --exclude "**/.ruff_cache" \
    --exclude "**/.venv" \
    --exclude "**/*.pyc"

# Retention: 7 daily + 4 weekly + 6 monthly
restic -r "$RESTIC_REPO" forget \
    --tag "$BACKUP_TAG" \
    --keep-daily 7 \
    --keep-weekly 4 \
    --keep-monthly 6 \
    --prune

# Test restore quarterly by running:
# restic -r "$RESTIC_REPO" restore latest --target /tmp/restore-test
BACKUP_EOF
chmod +x "$FA_DIR/scripts/backup-fa.sh"

# 14b. Create backup credentials template (outside repo, not tracked)
BACKUP_ENV="$FA_DIR/secrets/backup.env"
if [ ! -f "$BACKUP_ENV" ]; then
    cat > "$BACKUP_ENV" <<'EOF'
B2_KEY_ID=CHANGEME
B2_APPLICATION_KEY=CHANGEME
B2_BUCKET=CHANGEME
EOF
    chmod 600 "$BACKUP_ENV"
    log_warn "Backup credentials template created at $BACKUP_ENV. EDIT IT with real values."
fi

# 15. Summary
log_info "====================================="
log_info "Setup complete! Next steps:"
log_info "====================================="
echo ""
echo "1. Run: sudo tailscale up --ssh"
echo "2. Add deploy key to GitHub (public key shown above)"
echo "3. Enable branch protection on 'main' — agent pushes to 'agent/*'"
echo "4. Log out and back in for docker group membership"
echo "5. Review docker-compose.fa.yml and Dockerfile.fa"
echo "6. Start FA: systemctl --user start fa.service"
echo ""
echo "FA workspace:   $FA_DIR/repo/First-Agent-dev"
echo "FA state:       $FA_DIR/state"
echo "FA secrets:     $FA_DIR/secrets"
echo "FA backup:      $FA_DIR/scripts/backup-fa.sh (edit B2 credentials)"
echo "FA service:     ~/.config/systemd/user/fa.service"
