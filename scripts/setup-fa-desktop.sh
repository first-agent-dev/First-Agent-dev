#!/usr/bin/env bash
# setup-fa-desktop.sh — Bootstrap a dedicated Ubuntu Desktop 24.04 AIO for First-Agent 24/7
#
# Usage:   bash scripts/setup-fa-desktop.sh
# Idempotent: safe to re-run.
# WARNING: modifies system settings (SSH, firewall, systemd, Docker, cron).
#
# Override defaults via environment:
#   FA_USER=fa  REPO_URL=https://... bash scripts/setup-fa-desktop.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FA_USER="${FA_USER:-$USER}"
FA_DIR="/srv/first-agent"
REPO_URL="${REPO_URL:-https://github.com/first-agent-dev/First-Agent-dev.git}"

# NOTE: this bootstrap script is intentionally SELF-CONTAINED (no `source`d
# helper library). knowledge/instructions/01-install.md Phase 4 Option B documents downloading
# *only* this file to /tmp and running it — the repo is cloned later, by step 9
# below — so it must not depend on any sibling file at startup.
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if [[ "$EUID" -eq 0 ]]; then
    log_error "Do not run this script as root. Run as your normal user with passwordless sudo."
    exit 1
fi

if ! command -v sudo &>/dev/null; then
    log_error "sudo is required but not installed."
    exit 1
fi

UBUNTU_CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
if [[ "$UBUNTU_CODENAME" != "noble" ]]; then
    log_warn "This script is tested on Ubuntu 24.04 (noble). Found: ${UBUNTU_CODENAME:-unknown}"
    read -rp "Continue anyway? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || exit 1
fi

FA_USER_HOME=$(getent passwd "$FA_USER" | cut -d: -f6)
if [[ -z "$FA_USER_HOME" ]]; then
    log_error "User '$FA_USER' not found."
    exit 1
fi

log_info "Starting First-Agent AIO setup for user: $FA_USER"
log_info "Workspace: $FA_DIR"

# ---------------------------------------------------------------------------
# 1. System update + essential packages
# ---------------------------------------------------------------------------
log_info "Updating system packages (non-interactive)..."

# Suppress needrestart interactive prompts on Ubuntu 24.04
export NEEDRESTART_MODE=a
sudo NEEDRESTART_MODE=a apt-get update
sudo NEEDRESTART_MODE=a apt-get full-upgrade -y
sudo NEEDRESTART_MODE=a apt-get install -y \
    curl wget git build-essential \
    universal-ctags \
    unattended-upgrades \
    fail2ban \
    ufw \
    powertop \
    restic \
    x11-xserver-utils \
    neovim \
    micro \
    openssh-server \
    cron || true

# ---------------------------------------------------------------------------
# 2. Desktop pruning
# ---------------------------------------------------------------------------
log_info "Pruning unnecessary Desktop services..."

# Safe to remove: gnome-software has known memory leaks (~2-3GB)
sudo apt-get remove -y gnome-software || true
sudo apt-get autoremove --purge -y || true

# Safe to disable (not purge): crash reporting
sudo systemctl disable whoopsie.service || true
sudo systemctl disable apport.service || true
sudo systemctl stop whoopsie.service || true
sudo systemctl stop apport.service || true

# Mask (do NOT purge) — removing packages breaks ubuntu-desktop metapackage
sudo -u "$FA_USER" systemctl --user mask tracker-miner-fs-3.service || true
sudo -u "$FA_USER" systemctl --user mask tracker-extract-3.service || true

# Disable Bluetooth (attack surface + power drain)
sudo systemctl stop bluetooth || true
sudo systemctl disable bluetooth || true

# Keep power-profiles-daemon (TLP is for laptops, causes USB issues on desktop AIO)
sudo systemctl enable power-profiles-daemon || true

# Enable and start security services installed above
sudo systemctl enable fail2ban 2>/dev/null || true
sudo systemctl start fail2ban 2>/dev/null || true
sudo systemctl enable unattended-upgrades 2>/dev/null || true
sudo systemctl start unattended-upgrades 2>/dev/null || true
sudo systemctl enable apt-daily-upgrade.timer 2>/dev/null || true
sudo systemctl start apt-daily-upgrade.timer 2>/dev/null || true

# ---------------------------------------------------------------------------
# 3. Suspend prevention — dual lock
# ---------------------------------------------------------------------------
log_info "Disabling suspend via dual lock..."

sudo mkdir -p /etc/systemd/logind.conf.d
sudo tee /etc/systemd/logind.conf.d/no-suspend.conf > /dev/null <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF
sudo systemctl daemon-reload

# GNOME power settings — only if an X session is available (not over plain SSH)
if [[ -n "${DISPLAY:-}" ]]; then
    sudo -u "$FA_USER" gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 0
    sudo -u "$FA_USER" gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-timeout 0
    sudo -u "$FA_USER" gsettings set org.gnome.desktop.session idle-delay 60
    sudo -u "$FA_USER" gsettings set org.gnome.desktop.screensaver lock-enabled false
    sudo -u "$FA_USER" gsettings set org.gnome.desktop.privacy report-technical-problems false
    sudo -u "$FA_USER" powerprofilesctl set power-saver || true
    sudo -u "$FA_USER" xset dpms 0 0 60 || true
else
    log_warn "Skipping gsettings/xset — no active X session (DISPLAY not set)."
    log_warn "If this is a headless re-run, these settings were likely applied at first boot."
fi

log_warn "Optional: 'sudo systemctl set-default multi-user.target' to skip GNOME on boot (~300-500MB RAM saved)."
log_warn "Emergency GUI: 'sudo systemctl isolate graphical.target'"

# ---------------------------------------------------------------------------
# 4. SSH hardening
# ---------------------------------------------------------------------------
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

if [[ -z "${SSH_CONNECTION:-}" ]]; then
    sudo systemctl restart ssh
else
    log_warn "Skipping ssh restart — you are connected via SSH. Run 'sudo systemctl restart ssh' manually when safe."
fi

# ---------------------------------------------------------------------------
# 5. Firewall
# ---------------------------------------------------------------------------
log_info "Configuring UFW..."

sudo ufw default deny incoming
sudo ufw default allow outgoing
# Allow SSH only via Tailscale interface (rule becomes active once tailscale0 appears)
sudo ufw allow in on tailscale0 to any port 22 proto tcp comment "SSH via Tailscale only"
sudo ufw allow 41641/udp comment "Tailscale wireguard"
sudo ufw --force enable

# ---------------------------------------------------------------------------
# 6. Docker CE (official docker.com apt repo, NOT snap)
# ---------------------------------------------------------------------------
log_info "Installing Docker CE from official repository..."

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo NEEDRESTART_MODE=a apt-get update
sudo NEEDRESTART_MODE=a apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$FA_USER"

log_info "Pinning Docker CE packages..."
sudo apt-mark hold docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Merge live-restore + log-rotate into daemon.json (preserve existing settings)
log_info "Configuring Docker daemon..."
sudo mkdir -p /etc/docker
sudo python3 <<'PYEOF'
import json, os
path = '/etc/docker/daemon.json'
data = {}
if os.path.exists(path):
    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            pass
data.setdefault('live-restore', True)
log_opts = data.setdefault('log-opts', {})
log_opts.setdefault('max-size', '10m')
log_opts.setdefault('max-file', '3')
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
PYEOF
log_info "Restarting Docker daemon to apply new settings..."
sudo systemctl restart docker

# ---------------------------------------------------------------------------
# 7. Tailscale
# ---------------------------------------------------------------------------
log_info "Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sudo sh
log_warn "Tailscale installed. Run: sudo tailscale up --ssh"
log_warn "Then authenticate with your Tailscale account."

# ---------------------------------------------------------------------------
# 8. FA workspace directories
# ---------------------------------------------------------------------------
log_info "Creating FA workspace at $FA_DIR..."
sudo mkdir -p "$FA_DIR"/{repo,state,secrets,backup,scripts}
sudo chown -R "$FA_USER:$FA_USER" "$FA_DIR"
sudo chmod 700 "$FA_DIR/state"
sudo chmod 700 "$FA_DIR/secrets"

# ---------------------------------------------------------------------------
# 9. Clone repo
# ---------------------------------------------------------------------------
if [[ ! -d "$FA_DIR/repo/First-Agent-dev" ]]; then
    log_info "Cloning First-Agent repository..."
    git clone "$REPO_URL" "$FA_DIR/repo/First-Agent-dev"
fi

# ---------------------------------------------------------------------------
# 10. Secrets (API keys) + .env.fa (non-secret controls) + models.yaml
# ---------------------------------------------------------------------------
# Secret isolation (ADR-12, Option C — egress-injection proxy): LLM API KEYS
# live OUTSIDE the repo / /workspace, in $FA_DIR/secrets/fa.env (0600). They are
# mounted read-only ONLY into the fa-egress-proxy container at
# /run/secrets/fa.env. The agent container never mounts this file and never
# receives the values — it reaches providers through the proxy, which injects
# the real key outside the agent's reach.
SECRETS_ENV="$FA_DIR/secrets/fa.env"
PROXY_TOKEN="$FA_DIR/secrets/fa_proxy_token"
ENV_FA="$FA_DIR/repo/First-Agent-dev/.env.fa"

# Migration: older deployments kept API keys in the repo .env.fa. If that file
# has uncommented API-key lines, move them to the secrets file (idempotent).
if [[ ! -f "$SECRETS_ENV" && -f "$ENV_FA" ]] && grep -qE '^[[:space:]]*[A-Z0-9_]*API_KEY[[:space:]]*=' "$ENV_FA"; then
    log_warn "Migrating API keys from repo .env.fa to $SECRETS_ENV (secret isolation)."
    cp "$ENV_FA" "$ENV_FA.pre-secret-migration.bak"
    # Extract uncommented *_API_KEY / *_TOKEN / *_SECRET lines into the secrets file.
    grep -E '^[[:space:]]*[A-Z0-9_]+(API_KEY|_TOKEN|_SECRET)[[:space:]]*=' "$ENV_FA" > "$SECRETS_ENV" || true
    chmod 600 "$SECRETS_ENV"
    # Strip those secret lines from the repo .env.fa (keep non-secret FA_* controls).
    sed -i -E '/^[[:space:]]*[A-Z0-9_]+(API_KEY|_TOKEN|_SECRET)[[:space:]]*=/d' "$ENV_FA"
    log_warn "Migrated. Backup at $ENV_FA.pre-secret-migration.bak — delete it once verified."
fi

# Seed the secrets file from template if still absent.
if [[ ! -f "$SECRETS_ENV" ]]; then
    TEMPLATE="$FA_DIR/repo/First-Agent-dev/.env.fa.template"
    if [[ -f "$TEMPLATE" ]]; then
        # Keep only the API-key lines from the template (commented placeholders).
        grep -E 'API_KEY|_TOKEN|_SECRET' "$TEMPLATE" > "$SECRETS_ENV" 2>/dev/null || true
    fi
    if [[ ! -s "$SECRETS_ENV" ]]; then
        cat > "$SECRETS_ENV" <<'EOF'
# First-Agent API KEYS — read-only mounted at /run/secrets/fa.env (ADR-12).
# NEVER commit. Uncomment and fill in the providers you use.
# OPENROUTER_API_KEY=sk-or-v1-CHANGEME
# FIREWORKS_API_KEY=fw-CHANGEME
# ANTHROPIC_API_KEY=sk-ant-CHANGEME
# OPENAI_API_KEY=sk-CHANGEME
EOF
    fi
    chmod 600 "$SECRETS_ENV"
    log_warn "API-keys file created at $SECRETS_ENV. EDIT IT (with: micro $SECRETS_ENV) before first run."
fi

# fa->proxy bootstrap token (ADR-12 Option C): proves the agent container is the
# legitimate caller of the egress proxy. NOT an LLM key — leaking it only allows
# metered LLM calls through the proxy, never key disclosure. Generated once.
if [[ ! -s "$PROXY_TOKEN" ]]; then
    # 32 random bytes, url-safe base64 (no shell-special chars).
    head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n' > "$PROXY_TOKEN"
    chmod 600 "$PROXY_TOKEN"
    log_info "Generated fa->proxy token at $PROXY_TOKEN"
fi

# .env.fa now holds ONLY non-secret runtime controls (FA_AUTO_RUN, FA_TASK, ...).
if [[ ! -f "$ENV_FA" ]]; then
    cat > "$ENV_FA" <<'EOF'
# First-Agent NON-SECRET runtime controls (loaded by Docker Compose env_file).
# API KEYS do NOT go here — they live in /srv/first-agent/secrets/fa.env (ADR-12).
# Optional one-shot auto-run controls:
# FA_AUTO_RUN=0
# FA_TASK=...
# FA_ROLE=coder
# FA_RUN_ID=my-run-id
EOF
    chmod 600 "$ENV_FA"
    log_warn "Created $ENV_FA for non-secret controls. API keys go in $SECRETS_ENV."
fi

MODELS_YAML="$FA_DIR/state/models.yaml"
if [[ ! -f "$MODELS_YAML" ]]; then
    EXAMPLE="$FA_DIR/repo/First-Agent-dev/knowledge/examples/models.yaml.example"
    if [[ -f "$EXAMPLE" ]]; then
        cp "$EXAMPLE" "$MODELS_YAML"
    else
        # Inline fallback
        cat > "$MODELS_YAML" <<'EOF'
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
    log_warn "Template models.yaml created at $MODELS_YAML. EDIT IT to configure provider chains."
fi

# ---------------------------------------------------------------------------
# 11. SSH deploy key + pinned GitHub host key
# ---------------------------------------------------------------------------
DEPLOY_KEY="$FA_DIR/secrets/github_deploy_key"
if [[ ! -f "$DEPLOY_KEY" ]]; then
    log_info "Generating ED25519 deploy key..."
    ssh-keygen -t ed25519 -f "$DEPLOY_KEY" -N "" -C "first-agent-deploy@$(hostname)"
    chmod 600 "$DEPLOY_KEY"
    chmod 644 "$DEPLOY_KEY.pub"
    log_warn "Add the following PUBLIC key to GitHub repo Settings -> Deploy keys (WRITE access):"
    cat "$DEPLOY_KEY.pub"
    log_warn "Then enable branch protection on 'main' — agent pushes to 'agent/*' branches only."
fi

GH_ED25519_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okMS0XmZcBPwZR"
# Use ssh-keygen -F to detect existing entries (handles both plain and hashed formats).
if ! ssh-keygen -F github.com -f "$FA_DIR/secrets/known_hosts" >/dev/null 2>&1; then
    echo "github.com $GH_ED25519_KEY" >> "$FA_DIR/secrets/known_hosts"
    log_info "Pinned GitHub Ed25519 host key in $FA_DIR/secrets/known_hosts"
fi

# ---------------------------------------------------------------------------
# 12. Host SSH client config (for git fetch from AIO shell)
# ---------------------------------------------------------------------------
# The container uses GIT_SSH_COMMAND env var, but the host shell (where the
# operator runs git fetch / git pull) also needs the deploy key. We append a
# Host github.com block to ~/.ssh/config without destroying any existing entries.
SSH_DIR="$FA_USER_HOME/.ssh"
if [[ ! -d "$SSH_DIR" ]]; then
    mkdir -p "$SSH_DIR"
    chmod 700 "$SSH_DIR"
fi
if ! grep -q "^Host github.com$" "$SSH_DIR/config" 2>/dev/null; then
    {
        echo ""
        echo "Host github.com"
        echo "    HostName github.com"
        echo "    User git"
        echo "    IdentityFile $FA_DIR/secrets/github_deploy_key"
        echo "    IdentitiesOnly yes"
        echo "    UserKnownHostsFile $FA_DIR/secrets/known_hosts"
    } >> "$SSH_DIR/config"
    chmod 600 "$SSH_DIR/config"
    log_info "Added github.com block to $SSH_DIR/config"
else
    log_warn "$SSH_DIR/config already contains Host github.com — skipping auto-config"
    log_warn "Verify it points to $FA_DIR/secrets/github_deploy_key if git fetch fails"
fi
# Ensure restrictive permissions regardless of whether we created or appended.
chmod 600 "$SSH_DIR/config"

# ---------------------------------------------------------------------------
# 13. Unattended upgrades + auto-reboot
# ---------------------------------------------------------------------------
log_info "Enabling unattended security updates..."

sudo tee /etc/apt/apt.conf.d/20auto-upgrades > /dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

sudo tee /etc/apt/apt.conf.d/50unattended-upgrades-fa > /dev/null <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF

# ---------------------------------------------------------------------------
# 14. Weekly Docker prune (idempotent)
# ---------------------------------------------------------------------------
log_info "Adding weekly Docker image cleanup cron job..."
CRON_LINE="0 3 * * 0 /usr/bin/docker image prune -f > /dev/null 2>&1"
if ! (sudo crontab -l 2>/dev/null || true) | grep -qF "$CRON_LINE"; then
    (sudo crontab -l 2>/dev/null || true; echo "$CRON_LINE") | sudo crontab -
fi

# ---------------------------------------------------------------------------
# 15. systemd user service
# ---------------------------------------------------------------------------
log_info "Installing systemd user service from scripts/fa.service (single source of truth)..."

mkdir -p "$FA_USER_HOME/.config/systemd/user"
# Install from the version-controlled template in the cloned repo (single source
# of truth — no inline duplicate to drift out of sync), rewriting
# WorkingDirectory to the resolved $FA_DIR so a non-default FA_DIR still works.
# We read from the clone (step 9), NOT from the script's own directory, so this
# works whether the script was run from the repo or downloaded standalone to /tmp.
SERVICE_SRC="$FA_DIR/repo/First-Agent-dev/scripts/fa.service"
if [[ -f "$SERVICE_SRC" ]]; then
    sed "s|^WorkingDirectory=.*|WorkingDirectory=$FA_DIR/repo/First-Agent-dev|" \
        "$SERVICE_SRC" > "$FA_USER_HOME/.config/systemd/user/fa.service"
else
    log_error "Service template not found in repo: $SERVICE_SRC"
    log_error "Repo clone may have failed — re-run after fixing the clone."
    exit 1
fi

# daemon-reload may fail if D-Bus user session is not available (e.g. running via sudo in a bare terminal).
# We attempt it; if it fails we print a clear instruction instead of aborting.
if DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u "$FA_USER")/bus" sudo -u "$FA_USER" systemctl --user daemon-reload 2>/dev/null; then
    log_info "systemd user daemon reloaded."
else
    log_warn "systemctl --user daemon-reload failed (D-Bus session not available)."
    log_warn "After this script finishes, run manually as $FA_USER:"
    log_warn "  systemctl --user daemon-reload"
fi

sudo loginctl enable-linger "$FA_USER" 2>/dev/null || true
log_info "Service installed. Enable with: systemctl --user enable fa.service"

# ---------------------------------------------------------------------------
# 16. Backup script + credentials template
# ---------------------------------------------------------------------------
log_info "Installing backup script..."

# Install the version-controlled backup script from the repo (single source of
# truth — no inline duplicate to drift out of sync). The repo is guaranteed
# present at this point because step 9 cloned it above.
BACKUP_SRC="$FA_DIR/repo/First-Agent-dev/scripts/backup-fa.sh"
if [[ -f "$BACKUP_SRC" ]]; then
    cp "$BACKUP_SRC" "$FA_DIR/scripts/backup-fa.sh"
    chmod +x "$FA_DIR/scripts/backup-fa.sh"
else
    log_error "Backup script not found in repo: $BACKUP_SRC"
    log_error "Repo clone may have failed — re-run after fixing the clone."
    exit 1
fi

BACKUP_ENV="$FA_DIR/secrets/backup.env"
if [[ ! -f "$BACKUP_ENV" ]]; then
    cat > "$BACKUP_ENV" <<'EOF'
B2_KEY_ID=CHANGEME
B2_APPLICATION_KEY=CHANGEME
B2_BUCKET=CHANGEME
EOF
    chmod 600 "$BACKUP_ENV"
    log_warn "Backup credentials template created at $BACKUP_ENV. EDIT IT with real values."
fi

# ---------------------------------------------------------------------------
# 17. Summary
# ---------------------------------------------------------------------------
log_info "====================================="
log_info "Setup complete! Next steps:"
log_info "====================================="
echo ""
echo "1. Run: sudo tailscale up --ssh"
echo "2. Add deploy key to GitHub (public key shown above) — WRITE access"
echo "3. Verify SSH:          ssh -T git@github.com   (expect 'successfully authenticated')"
echo "4. Enable branch protection on 'main' — agent pushes to 'agent/*'"
echo "5. Log out and back in for docker group membership"
echo "6. Edit .env.fa:        micro $FA_DIR/repo/First-Agent-dev/.env.fa"
echo "7. Edit models.yaml:    micro $FA_DIR/state/models.yaml"
echo "8. Start FA:            bash scripts/fa-post-setup.sh"
echo ""
echo "FA workspace:   $FA_DIR/repo/First-Agent-dev"
echo "FA state:       $FA_DIR/state"
echo "FA secrets:     $FA_DIR/secrets"
echo "FA backup:      $FA_DIR/scripts/backup-fa.sh"
echo "FA service:     $FA_USER_HOME/.config/systemd/user/fa.service"
