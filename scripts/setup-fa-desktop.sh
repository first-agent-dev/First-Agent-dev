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
DOCKER_GPG_TMP="$(mktemp)"
curl --fail --location --show-error --silent \
    --retry 5 --retry-all-errors --connect-timeout 15 --max-time 120 \
    -o "$DOCKER_GPG_TMP" https://download.docker.com/linux/ubuntu/gpg
sudo install -m 0644 "$DOCKER_GPG_TMP" /etc/apt/keyrings/docker.asc
rm -f "$DOCKER_GPG_TMP"
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
TAILSCALE_INSTALL_TMP="$(mktemp)"
curl --fail --location --show-error --silent \
    --retry 5 --retry-all-errors --connect-timeout 15 --max-time 180 \
    -o "$TAILSCALE_INSTALL_TMP" https://tailscale.com/install.sh
sudo sh "$TAILSCALE_INSTALL_TMP"
rm -f "$TAILSCALE_INSTALL_TMP"
log_warn "Tailscale installed. Run: sudo tailscale up --ssh"
log_warn "Then authenticate with your Tailscale account."

# ---------------------------------------------------------------------------
# 8. FA workspace directories
# ---------------------------------------------------------------------------
log_info "Creating FA workspace at $FA_DIR..."
sudo mkdir -p "$FA_DIR"/{repo,state,secrets,backup,routing}
# Ownership MUST match the container's runtime uid:gid. The container runs as the
# hardcoded numeric 1000:1000 (Dockerfile `useradd -u 1000 fa` +
# docker-compose `user: "1000:1000"`). Chowning to the host *username* only works
# when that user happens to be uid 1000 — on a host where the operator is a
# different uid, the bind-mounted state/secrets would be unreadable by the
# container (proxy can't read keys, agent can't write state). Pin to 1000:1000.
FA_UID="$(id -u "$FA_USER")"
if [[ "$FA_UID" != "1000" ]]; then
    log_warn "Host user '$FA_USER' is uid $FA_UID, but the container runs as uid 1000."
    log_warn "Chowning $FA_DIR to 1000:1000 so the container can access bind mounts."
fi
sudo chown -R 1000:1000 "$FA_DIR"
sudo chmod 700 "$FA_DIR/state"
sudo chmod 700 "$FA_DIR/secrets"
sudo chmod 750 "$FA_DIR/routing"

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

# Seed the secrets file from template if still absent.
if [[ ! -f "$SECRETS_ENV" ]]; then
    TEMPLATE="$FA_DIR/repo/First-Agent-dev/knowledge/templates/fa.env.template"
    if [[ -f "$TEMPLATE" ]]; then
        cp "$TEMPLATE" "$SECRETS_ENV"
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
    ENV_TEMPLATE="$FA_DIR/repo/First-Agent-dev/.env.fa.template"
    if [[ -f "$ENV_TEMPLATE" ]]; then
        cp "$ENV_TEMPLATE" "$ENV_FA"
    else
        cat > "$ENV_FA" <<'EOF'
# First-Agent NON-SECRET runtime controls (loaded by Docker Compose env_file).
# API KEYS do NOT go here — they live in /srv/first-agent/secrets/fa.env (ADR-12).
# Optional one-shot auto-run controls:
# FA_AUTO_RUN=0
# FA_TASK=...
# FA_ROLE=coder
# FA_RUN_ID=my-run-id
EOF
    fi
    chmod 600 "$ENV_FA"
    log_warn "Created $ENV_FA for non-secret controls. API keys go in $SECRETS_ENV."
fi

NORMALIZE_ENV="$FA_DIR/repo/First-Agent-dev/scripts/fa-normalize-env.sh"
if [[ -f "$NORMALIZE_ENV" ]]; then
    env \
        REPO_DIR="$FA_DIR/repo/First-Agent-dev" \
        ENV_FA="$ENV_FA" \
        SECRETS_ENV="$SECRETS_ENV" \
        BACKUP_DIR="$FA_DIR/secrets" \
        bash "$NORMALIZE_ENV"
fi

ROUTING_DIR="$FA_DIR/routing"
ROUTING_MODELS_FILE="$ROUTING_DIR/models.yaml"
# SUNSET (remove after 2026-12-01, once all hosts run the unified routing file):
# one-time migration inputs from the pre-unification layouts. They are only read
# when routing/models.yaml does not yet exist; after migration they are ignored.
LEGACY_STATE_MODELS="$FA_DIR/state/models.yaml"
LEGACY_PROXY_MODELS="$FA_DIR/proxy/models.yaml"
EXAMPLE_MODELS="$FA_DIR/repo/First-Agent-dev/knowledge/templates/models.yaml.example"

ensure_routing_models() {
    sudo mkdir -p "$ROUTING_DIR"
    sudo chown 1000:1000 "$ROUTING_DIR"
    sudo chmod 750 "$ROUTING_DIR"

    if [[ ! -f "$ROUTING_MODELS_FILE" ]]; then
        if [[ -f "$LEGACY_STATE_MODELS" ]]; then
            sudo cp "$LEGACY_STATE_MODELS" "$ROUTING_MODELS_FILE"
            log_info "Migrated legacy routing config: $LEGACY_STATE_MODELS → $ROUTING_MODELS_FILE"
        elif [[ -f "$LEGACY_PROXY_MODELS" ]]; then
            sudo cp "$LEGACY_PROXY_MODELS" "$ROUTING_MODELS_FILE"
            log_info "Migrated legacy routing config: $LEGACY_PROXY_MODELS → $ROUTING_MODELS_FILE"
        elif [[ -f "$EXAMPLE_MODELS" ]]; then
            sudo cp "$EXAMPLE_MODELS" "$ROUTING_MODELS_FILE"
            log_warn "Template models.yaml created at $ROUTING_MODELS_FILE. EDIT IT to configure provider chains."
        else
            sudo tee "$ROUTING_MODELS_FILE" >/dev/null <<'EOF'
coder:
  model: "deepseek-v3"
  family: "deepseek"
  chain:
    - provider: openrouter
      slug: "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
EOF
            log_warn "Fallback models.yaml created at $ROUTING_MODELS_FILE. EDIT IT to configure provider chains."
        fi
    fi

    sudo chown 1000:1000 "$ROUTING_MODELS_FILE"
    sudo chmod 640 "$ROUTING_MODELS_FILE"
    log_info "Routing source ready: $ROUTING_MODELS_FILE (mounted read-only into both containers)."
}

ensure_routing_models

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
# Ownership + mode normalization (CRITICAL — runs AFTER every secret file is
# created). The global chown earlier cannot cover files created later, and those
# were written by the operator's shell (no sudo) → owned by the operator's uid.
# The containers run as the NUMERIC uid 1000, and ssh refuses a private key not
# owned by the running user. So force the container uid + tight modes on every
# secret, regardless of who created it. This is the fix for the whole class of
# "proxy unhealthy / git push fails when the host operator is not uid 1000".
# ---------------------------------------------------------------------------
sudo chown -R 1000:1000 "$FA_DIR/secrets" 2>/dev/null || true
sudo chmod 700 "$FA_DIR/secrets"
for _f in fa.env fa_proxy_token github_deploy_key known_hosts \
          .env.fa.pre-secret-migration.bak backup.env; do
    [[ -e "$FA_DIR/secrets/$_f" ]] && sudo chmod 600 "$FA_DIR/secrets/$_f"
done
[[ -e "$FA_DIR/secrets/github_deploy_key.pub" ]] && sudo chmod 644 "$FA_DIR/secrets/github_deploy_key.pub"
log_info "Normalized secret ownership to uid 1000 + 0600 modes."

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
# 16. Backup credentials template + host CLI wrapper
# ---------------------------------------------------------------------------
log_info "Preparing backup credentials template..."

# The repo copy is the single source of truth for the backup script:
#   $FA_DIR/repo/First-Agent-dev/scripts/backup-fa.sh
# Do NOT create a second host-side copy under /srv/first-agent/scripts/.
BACKUP_SRC="$FA_DIR/repo/First-Agent-dev/scripts/backup-fa.sh"
if [[ ! -f "$BACKUP_SRC" ]]; then
    log_error "Backup script not found in repo: $BACKUP_SRC"
    log_error "Repo clone may have failed — re-run after fixing the clone."
    exit 1
fi
chmod +x "$BACKUP_SRC"

# Install host-side fa CLI wrapper (unified operator interface).
FA_WRAPPER="$FA_DIR/repo/First-Agent-dev/scripts/fa"
if [[ -f "$FA_WRAPPER" ]]; then
    chmod +x "$FA_WRAPPER"
    sudo ln -sf "$FA_WRAPPER" /usr/local/bin/fa
    log_info "fa CLI wrapper installed: fa → $FA_WRAPPER"
else
    log_warn "scripts/fa not found — host shortcut not installed (will be available after fa-post-setup.sh)."
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
echo "7. Edit models.yaml:    micro $FA_DIR/routing/models.yaml"
echo "8. Start FA:            bash scripts/fa-post-setup.sh"
echo ""
echo "FA workspace:   $FA_DIR/repo/First-Agent-dev"
echo "FA state:       $FA_DIR/state"
echo "FA routing:     $FA_DIR/routing/models.yaml"
echo "FA secrets:     $FA_DIR/secrets"
echo "FA backup:      $FA_DIR/repo/First-Agent-dev/scripts/backup-fa.sh"
echo "FA service:     $FA_USER_HOME/.config/systemd/user/fa.service"
